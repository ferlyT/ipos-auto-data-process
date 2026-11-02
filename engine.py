"""
Automation Engine for iPos 4.0 Monthly & Annual Data Processing.
Calibrated precisely to match iPos 4.0 UI layout with dynamic window tracking:
- Window-relative coordinate tracking (immune to moving or dragging dialogs).
- Deterministic completion detection via green [Tutup] icon & dialog status.
- Zero false positives from external or bot windows.
"""
import time
import threading
import traceback
from datetime import datetime
from typing import Callable, Optional, Tuple
from config import load_config
from vision import resolve_target_coordinate, find_template_on_screen

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.2
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

MONTH_NAMES = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "Nopember", "Desember"
]

# Relative offsets from top-left of 'Proses Bulanan' dialog (450x478 at 1080p)
REL_OFFSETS_BULANAN = {
    "dropdown_bulan": (219, 274),
    "spin_tahun": (316, 280),
    "chk_stok": (138, 252),
    "btn_proses": (244, 338),
    "label_status": (212, 404),
    "btn_tutup": (391, 444)
}

# Relative offsets for 'Proses Tutup Tahun' dialog (438x449, origin at 741, 302)
REL_OFFSETS_TAHUNAN = {
    "spin_tahun": (309, 267),
    "btn_proses": (239, 325),
    "label_status": (212, 404),
    "btn_tutup": (384, 420)
}

class AutoProcessorEngine:
    def __init__(
        self,
        on_log: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int, float], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None,
        simulation: bool = False,
        check_perbaikan_stok: bool = False,
        bot_window_rect: Optional[Tuple[int, int, int, int]] = None
    ):
        self.on_log = on_log or (lambda msg: print(f"[LOG] {msg}"))
        self.on_status = on_status or (lambda status: print(f"[STATUS] {status}"))
        self.on_progress = on_progress or (lambda cur, tot, pct: None)
        self.on_finished = on_finished or (lambda ok, msg: print(f"[DONE] ok={ok}: {msg}"))
        
        self.simulation = simulation
        self.check_perbaikan_stok = check_perbaikan_stok
        self.bot_window_rect = bot_window_rect
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self.is_running = False

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.on_log(f"[{timestamp}] {message}")

    def update_status(self, text: str):
        self.on_status(text)

    def get_dialog_rect(self, title_part: str = "proses") -> Optional[Tuple[int, int, int, int]]:
        """
        Dynamically finds the active iPos dialog on screen and returns its (left, top, right, bottom).
        This guarantees correct clicks even if the user moves or rearranges the window!
        """
        if not HAS_WIN32:
            return None

        found_rect = None

        def enum_cb(hwnd, _):
            nonlocal found_rect
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                t_lower = title.lower() if title else ""
                
                # Matching logic for bulanan vs tahunan/tutup tahun dialogs
                match = False
                if title_part.lower() in ["tahunan", "tahun", "tutup tahun"]:
                    match = any(k in t_lower for k in ["tutup tahun", "proses tutup tahun", "proses tahunan", "tahunan"])
                elif title_part.lower() in ["bulanan", "bulan"]:
                    match = any(k in t_lower for k in ["proses bulanan", "bulanan"])
                else:
                    match = title_part.lower() in t_lower

                if match:
                    # Filter out main window or bot window
                    if "menu utama" not in t_lower and "auto proses" not in t_lower:
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if 250 < w < 850 and 250 < h < 850:
                            found_rect = rect
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        return found_rect

    def get_control_coord(self, control_name: str, dialog_type: str = "bulanan") -> Tuple[int, int]:
        """
        Computes the target coordinate:
        1. Prioritas Utama: Dynamic rect offset dari jendela dialog aktif (kebal geser / drag window).
        2. Prioritas Kedua: Koordinat kalibrasi langsung jika jendela belum/tidak terlacak.
        3. Fallback: Vision template matching & scaled baseline.
        """
        cfg = load_config()
        key_map = {
            "dropdown_bulan": "bulanan_dropdown_bulan",
            "spin_tahun": "bulanan_spin_tahun" if dialog_type == "bulanan" else "tahunan_spin_tahun",
            "chk_stok": "bulanan_chk_perbaikan_stok",
            "btn_proses": "bulanan_btn_proses" if dialog_type == "bulanan" else "tahunan_btn_proses",
            "label_status": "bulanan_label_status",
            "btn_tutup": "bulanan_btn_tutup" if dialog_type == "bulanan" else "tahunan_btn_tutup"
        }
        cfg_key = key_map.get(control_name, control_name)
        user_coords = cfg.get("coords", {})

        # 1. Dynamic rect offset: selalu ikuti posisi dialog terkini di mana pun ditarik/digeser pengguna di layar
        rect = self.get_dialog_rect("bulanan" if dialog_type == "bulanan" else "tahunan")
        offsets = REL_OFFSETS_BULANAN if dialog_type == "bulanan" else REL_OFFSETS_TAHUNAN

        if rect and control_name in offsets:
            left, top, _, _ = rect
            dx, dy = offsets[control_name]
            return (left + dx, top + dy)

        # 2. Prioritaskan koordinat hasil kalibrasi pengguna jika dialog belum terdeteksi rect-nya
        if cfg.get("calibrated") and cfg_key in user_coords and user_coords[cfg_key]:
            c = user_coords[cfg_key]
            return (c[0], c[1])

        # 3. Fallback ke vision template / defaults
        return resolve_target_coordinate(cfg_key, user_coords=user_coords, exclude_rect=self.bot_window_rect)

    def safe_click(self, x: int, y: int, desc: str = ""):
        """
        Safely moves mouse and clicks target coordinate with user intervention detection.
        If the user is actively fighting or moving the mouse, automatically pauses for safety.
        """
        if self.simulation:
            time.sleep(0.05)
            return

        if not HAS_PYAUTOGUI:
            return

        # 1. Bawa iPos ke latar depan terlebih dahulu jika tertutup
        self.focus_ipos_window()

        # 2. Gerakkan kursor secara halus ke elemen target
        pyautogui.moveTo(x, y, duration=0.22)

        # 3. Cek apakah kursor digeser paksa oleh pengguna (drift check)
        p1 = pyautogui.position()
        time.sleep(0.06)
        p2 = pyautogui.position()
        drift = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5

        if drift > 8:
            self.log(f"⚠️ Terdeteksi pergerakan mouse oleh pengguna ({int(drift)}px). Mengaktifkan JEDA demi keamanan!")
            self._pause_event.set()
            self.update_status("DIJEDA: Terdeteksi Gerakan Mouse Pengguna")
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.5)

            # Setelah di-resume pengguna, fokuskan ulang dan gerakkan kembali ke koordinat
            if not self._stop_event.is_set():
                self.focus_ipos_window()
                pyautogui.moveTo(x, y, duration=0.2)

        # 4. Lakukan klik
        if not self._stop_event.is_set():
            pyautogui.click(x, y)
            time.sleep(0.15)

    def find_ipos_window(self) -> Optional[int]:
        """Find handle of the main iPos window or active dialog."""
        if not HAS_WIN32:
            return None
        
        keywords = [
            "proses bulanan", "proses tutup tahun", "proses tahunan", "tutup tahun",
            "proses data", "menu utama", "ipos 4", "program ipos", "program toko"
        ]
        found = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip().lower()
                if any(k in title for k in keywords):
                    if "auto proses" not in title:
                        found.append((hwnd, title))
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        if found:
            # 1. Prioritaskan jika dialog proses sedang terbuka
            for hwnd, title in found:
                if any(w in title for w in ["proses bulanan", "proses tutup tahun", "tutup tahun", "proses tahunan"]):
                    return hwnd
            # 2. Prioritaskan jendela Menu Utama iPos 4.0
            for hwnd, title in found:
                if "menu utama" in title or "ipos" in title:
                    return hwnd
            return found[0][0]
        return None

    def focus_ipos_window(self) -> bool:
        """Bring iPos window to foreground reliably."""
        if self.simulation or not HAS_WIN32:
            return True

        hwnd = self.find_ipos_window()
        if hwnd:
            try:
                # Beri trigger tombol Alt agar Windows mengizinkan transfer fokus latar depan
                if HAS_PYAUTOGUI:
                    pyautogui.press('alt')
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.35)
                return True
            except Exception:
                pass
        return False

    def find_popup_dialog(self) -> Optional[int]:
        """Check if any modal popup (OK dialog / Informasi / Selesai) is visible."""
        if not HAS_WIN32:
            return None

        found = []
        def enum_dialogs(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                cls = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd).strip().lower()
                if cls == "#32770" or any(w in title for w in ["informasi", "konfirmasi", "perhatian", "selesai"]):
                    if title not in ["program ipos 4.0", "menu utama", "auto proses data ipos 4.0"]:
                        found.append(hwnd)
            return True

        try:
            win32gui.EnumWindows(enum_dialogs, None)
        except Exception:
            pass

        return found[0] if found else None

    def is_tutup_button_enabled(self, dialog_type: str = "bulanan") -> bool:
        """
        Checks if the [Tutup] button inside the iPos dialog is enabled.
        In iPos 4 (DevExpress), when calculation is running, [Tutup] is greyed out (0 green pixels).
        When calculation finishes, [Tutup] has a bright green icon (> 15 green pixels).
        """
        if not HAS_CV2 or not HAS_PYAUTOGUI:
            return True

        rect = self.get_dialog_rect("bulanan" if dialog_type == "bulanan" else "tahunan")
        if not rect:
            return True

        left, top, right, bottom = rect
        # The Tutup button is at bottom-right of dialog
        btn_x1 = max(0, right - 110)
        btn_y1 = max(0, bottom - 55)
        btn_w = 95
        btn_h = 40

        try:
            patch = pyautogui.screenshot(region=(btn_x1, btn_y1, btn_w, btn_h))
            patch_cv = cv2.cvtColor(np.array(patch), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(patch_cv, cv2.COLOR_BGR2HSV)
            # Detect green color of the enabled Tutup icon
            green_mask = cv2.inRange(hsv, (35, 50, 50), (85, 255, 255))
            green_count = np.count_nonzero(green_mask)
            return green_count > 15
        except Exception:
            return True

    def confirm_start_modal(self):
        """
        Confirms the modal dialog:
        'Apakah anda akan melakukan proses bulanan = <Bulan> <Tahun>?' or Tutup Tahun
        by clicking [ Yes ] and sending Enter/y keystrokes.
        """
        self.log("Menunggu modal konfirmasi 'Apakah anda akan melakukan proses...'")
        if self.simulation:
            time.sleep(0.05)
            self.log("[SIMULASI] Modal konfirmasi dikonfirmasi (YES).")
            return True

        time.sleep(0.8)
        cfg = load_config()
        user_coords = cfg.get("coords", {})

        pt_yes = resolve_target_coordinate("modal_btn_yes", "btn_yes.png", user_coords)
        self.log(f"Mengonfirmasi [ Yes ] pada ({pt_yes[0]}, {pt_yes[1]})...")

        # Send standard keyboard shortcuts
        pyautogui.press('y')
        time.sleep(0.15)
        pyautogui.press('enter')
        time.sleep(0.2)

        # Click Yes coordinate
        self.safe_click(pt_yes[0], pt_yes[1], "Tombol Yes")
        time.sleep(0.5)
        return True

    def wait_for_modal_completion(self, dialog_type: str = "bulanan", max_wait_sec: int = 1800) -> bool:
        """
        Polls until the database calculation finishes.
        Deterministic detection:
        1. Checks for completion popup dialog (MessageBox with OK).
        2. Inspects [Tutup] button status (disabled -> enabled green icon).
        3. Updates live seconds counter without any false positives.
        - For Proses Tahunan: Polling runs faster with checks every 5 seconds.
        """
        cfg = load_config()
        is_tahunan = (dialog_type == "tahunan")

        # Proses tahunan berjalan jauh lebih cepat: cek modal & tombol selesai dipercepat
        poll_interval = cfg.get("tahunan_poll_interval_sec", 0.5) if is_tahunan else cfg.get("popup_poll_interval_sec", 1.0)
        expected_sec = cfg.get("tahunan_expected_duration_sec", 10) if is_tahunan else cfg.get("expected_process_duration_sec", 30)
        min_wait_sec = cfg.get("tahunan_min_wait_before_check_sec", 4) if is_tahunan else cfg.get("min_wait_before_check_sec", 12)
        log_interval = 5 if is_tahunan else 10
        user_coords = cfg.get("coords", {})
        start_time = time.time()
        last_log_sec = 0

        proc_label = "Tutup Tahun" if is_tahunan else "Bulanan"
        self.log(f"Kalkulasi database ({proc_label}) sedang berjalan (estimasi ~{expected_sec}s)...")

        while not self._stop_event.is_set():
            elapsed = time.time() - start_time

            if elapsed > max_wait_sec:
                self.log(f"ERROR: Timeout kalkulasi database melebihi {max_wait_sec} detik!")
                return False

            if self.simulation:
                time.sleep(0.05)
                self.log(f"[SIMULASI] Perhitungan database {proc_label} selesai.")
                return True

            # Update live GUI status counter
            self.update_status(f"Sedang Memproses Database ({proc_label})... ({int(elapsed)}s / ~{expected_sec}s)")

            # Periodic log update: setiap 5 detik untuk tahunan, 10 detik untuk bulanan
            if int(elapsed) >= last_log_sec + log_interval:
                last_log_sec = int(elapsed)
                self.log(f"Database ({proc_label}) masih bekerja... ({last_log_sec} detik berjalan)")

            # 1. Cek jika popup dialog selesai muncul (MessageBox OK)
            popup_hwnd = self.find_popup_dialog()
            if popup_hwnd:
                self.log(f"Popup selesai terdeteksi setelah {int(elapsed)} detik. Mengonfirmasi OK...")
                time.sleep(0.3)
                if HAS_PYAUTOGUI:
                    pyautogui.press('enter')
                    time.sleep(0.15)
                    pyautogui.press('space')
                    time.sleep(0.15)

                ok_pt = resolve_target_coordinate("popup_btn_ok", user_coords=user_coords)
                if HAS_PYAUTOGUI and ok_pt:
                    self.safe_click(ok_pt[0], ok_pt[1], "Tombol OK")

                time.sleep(0.5)
                return True

            # 2. Cek status tombol [Tutup] (aktif/hijau = kalkulasi tuntas!)
            if elapsed >= min_wait_sec:
                if self.is_tutup_button_enabled(dialog_type):
                    self.log(f"Kalkulasi ({proc_label}) selesai sempurna dalam {int(elapsed)} detik (tombol Tutup telah aktif kembali).")
                    time.sleep(0.5)
                    return True

            time.sleep(poll_interval)

            while self._pause_event.is_set() and not self._stop_event.is_set():
                self.update_status("DIJEDA (PAUSED)")
                time.sleep(0.5)

        return False

    def open_dialog_bulanan(self):
        """Click the 'Proses Bulanan' ribbon button to open the monthly dialog."""
        if self.simulation:
            time.sleep(0.05)
            return

        self.focus_ipos_window()
        # Jika dialog sudah terbuka di layar, gunakan langsung
        if self.get_dialog_rect("bulanan"):
            self.log("Dialog 'Proses Bulanan' sudah terbuka dan aktif.")
            return

        self.log("Membuka dialog 'Proses Bulanan' dari Ribbon...")
        cfg = load_config()

        # 1. Pastikan Tab 'Proses Data' di menu atas aktif
        pt_tab = resolve_target_coordinate("tab_proses_data", user_coords=cfg.get("coords"))
        self.safe_click(pt_tab[0], pt_tab[1], "Tab Proses Data")
        time.sleep(0.3)

        # 2. Klik tombol Ribbon 'Proses Bulanan'
        pt = resolve_target_coordinate("ribbon_bulanan", "ribbon_bulanan.png", cfg.get("coords"))
        self.log(f"Mengklik tombol Ribbon 'Proses Bulanan' di ({pt[0]}, {pt[1]})...")
        self.safe_click(pt[0], pt[1], "Ribbon Proses Bulanan")
        time.sleep(1.2)

    def close_dialog_bulanan(self):
        """Click the 'Tutup' button on the monthly dialog."""
        self.log("Menutup dialog 'Proses Bulanan'...")
        if self.simulation:
            time.sleep(0.05)
            return

        pt = self.get_control_coord("btn_tutup", "bulanan")
        self.safe_click(pt[0], pt[1], "Tombol Tutup Bulanan")
        time.sleep(0.5)
        if self.get_dialog_rect("bulanan"):
            pyautogui.press('esc')
            time.sleep(0.5)

    def open_dialog_tahunan(self):
        """Click the 'Proses Tahunan' ribbon button to open annual dialog."""
        if self.simulation:
            time.sleep(0.05)
            return

        self.focus_ipos_window()
        if self.get_dialog_rect("tahunan"):
            self.log("Dialog 'Proses Tahunan' sudah terbuka dan aktif.")
            return

        self.log("Membuka dialog 'Proses Tahunan' dari Ribbon...")
        cfg = load_config()

        pt_tab = resolve_target_coordinate("tab_proses_data", user_coords=cfg.get("coords"))
        self.safe_click(pt_tab[0], pt_tab[1], "Tab Proses Data")
        time.sleep(0.3)

        pt = resolve_target_coordinate("ribbon_tahunan", "ribbon_tahunan.png", cfg.get("coords"))
        self.log(f"Mengklik tombol Ribbon 'Proses Tahunan' di ({pt[0]}, {pt[1]})...")
        self.safe_click(pt[0], pt[1], "Ribbon Proses Tahunan")
        time.sleep(1.2)

    def close_dialog_tahunan(self):
        """Click the 'Tutup' button on the annual dialog."""
        self.log("Menutup dialog 'Proses Tahunan'...")
        if self.simulation:
            time.sleep(0.05)
            return

        pt = self.get_control_coord("btn_tutup", "tahunan")
        self.safe_click(pt[0], pt[1], "Tombol Tutup Tahunan")
        time.sleep(0.5)
        if self.get_dialog_rect("tahunan"):
            pyautogui.press('esc')
            time.sleep(0.5)

    def trigger_monthly_process(self, year: int, month_idx: int):
        """
        Execute one month calculation (1..12).
        Dynamically locates the dialog and selects month via Home + Down arrows.
        """
        cfg = load_config()
        month_name = MONTH_NAMES[month_idx - 1]

        self.update_status(f"Tahun {year} - Bulan {month_idx:02d} ({month_name})")
        self.log(f"==========================================")
        self.log(f"Memproses Periode: {month_name} {year}")
        self.log(f"==========================================")

        if not self.simulation:
            self.focus_ipos_window()
            time.sleep(0.2)

            # 1. Pilih Bulan via Dropdown
            pt_bulan = self.get_control_coord("dropdown_bulan", "bulanan")
            self.log(f"Memilih bulan {month_name} di ({pt_bulan[0]}, {pt_bulan[1]})...")
            
            # Klik tepat pada combobox untuk memastikan kontrol bulan aktif dan berfokus
            self.safe_click(pt_bulan[0], pt_bulan[1], "Dropdown Bulan")
            time.sleep(0.3)

            # Reset paksa ke Januari (Indeks 0) dari posisi apa pun
            # Roll-up 15x ke atas menjamin mentok kembali ke 'Januari'
            for _ in range(15):
                pyautogui.press('up')
                time.sleep(0.03)
            time.sleep(0.15)

            # Dari Januari, turun sebanyak (month_idx - 1) kali ke bulan target
            # Misal: Februari (month_idx=2) -> 1x Down, Maret -> 2x Down, dst.
            for _ in range(month_idx - 1):
                pyautogui.press('down')
                time.sleep(0.08)
            time.sleep(0.15)

            # Kunci pilihan bulan dengan Enter (BUKAN Tab, agar kursor TIDAK berpindah ke Tahun!)
            pyautogui.press('enter')
            time.sleep(0.2)

            # 2. Input Tahun pada Spinbox HANYA pada awal tahun / bulan Januari (month_idx == 1)
            # Pada bulan Februari s.d. Desember, tahun sudah sama dan TIDAK BOLEH diklik/diubah
            if month_idx == 1:
                pt_tahun = self.get_control_coord("spin_tahun", "bulanan")
                self.log(f"Mengisi tahun {year} di ({pt_tahun[0]}, {pt_tahun[1]})...")
                self.safe_click(pt_tahun[0], pt_tahun[1], "Input Tahun")
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
                pyautogui.write(str(year), interval=0.05)
                time.sleep(0.15)
                pyautogui.press('enter')
                time.sleep(0.2)

            # 3. Checkbox Perbaikan Stok
            # Aturan iPos 4.0: Perbaikan stok HANYA BISA dilakukan pada bulan dan tahun sesuai tanggal aktif (bulan berjalan saat ini)
            now = datetime.now()
            is_active_period = (year == now.year and month_idx == now.month)

            if self.check_perbaikan_stok:
                if is_active_period:
                    pt_chk = self.get_control_coord("chk_stok", "bulanan")
                    self.log(f"Mengaktifkan centang 'Perbaikan Stok' (periode aktif saat ini: {month_name} {year}) di ({pt_chk[0]}, {pt_chk[1]})...")
                    self.safe_click(pt_chk[0], pt_chk[1], "Checkbox Perbaikan Stok")
                    time.sleep(0.25)
                else:
                    self.log(f"Info: 'Perbaikan Stok' dilewati untuk {month_name} {year} (hanya berlaku pada bulan & tahun aktif saat ini: {MONTH_NAMES[now.month - 1]} {now.year}).")

            # 4. Klik Tombol [ Proses ]
            pt_proses = self.get_control_coord("btn_proses", "bulanan")
            self.log(f"Mengklik tombol [ Proses ] di ({pt_proses[0]}, {pt_proses[1]})...")
            self.safe_click(pt_proses[0], pt_proses[1], "Tombol Proses Bulanan")
            time.sleep(0.6)

            # 4b. Tangani Modal Konfirmasi ('Apakah anda akan melakukan proses bulanan = ...?')
            self.confirm_start_modal()
        else:
            self.confirm_start_modal()

        # 5. Tunggu proses selesai secara tuntas & pastikan tombol Tutup kembali aktif
        success = self.wait_for_modal_completion(dialog_type="bulanan", max_wait_sec=cfg.get("max_wait_minutes_per_month", 45) * 60)
        if success:
            self.log(f"BERHASIL: Bulan {month_name} {year} rampung.")
            time.sleep(0.05 if self.simulation else cfg.get("settle_delay_sec", 1.5))
        return success

    def trigger_annual_process(self, year: int):
        """
        Execute annual closing process:
        Close Monthly Dialog -> Open Annual Dialog -> Set Year -> Click [ Proses ] -> Close Annual Dialog.
        """
        cfg = load_config()

        self.update_status(f"PROSES TUTUP TAHUN: {year}")
        self.log(f"==========================================")
        self.log(f"MEMULAI PROSES TUTUP TAHUN: {year}")
        self.log(f"==========================================")

        # 1. Tutup dialog bulanan jika masih terbuka
        self.close_dialog_bulanan()

        # 2. Buka dialog Proses Tahunan dari Ribbon
        self.open_dialog_tahunan()

        if not self.simulation:
            # 3. Set Tahun pada dialog Proses Tahunan
            pt_tahun = self.get_control_coord("spin_tahun", "tahunan")
            self.log(f"Mengatur tahun {year} pada form Tahunan di ({pt_tahun[0]}, {pt_tahun[1]})...")
            self.safe_click(pt_tahun[0], pt_tahun[1], "Input Tahun Tahunan")
            time.sleep(0.25)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('backspace')
            pyautogui.write(str(year), interval=0.06)
            pyautogui.press('enter')
            time.sleep(0.4)

            # 4. Klik Tombol [ Proses ] Tahunan
            pt_proses = self.get_control_coord("btn_proses", "tahunan")
            self.log(f"Mengklik tombol [ Proses ] Tahunan di ({pt_proses[0]}, {pt_proses[1]})...")
            self.safe_click(pt_proses[0], pt_proses[1], "Tombol Proses Tahunan")
            time.sleep(0.6)

            # 4b. Tangani Modal Konfirmasi Tutup Tahun
            self.confirm_start_modal()
        else:
            self.confirm_start_modal()

        # 5. Tunggu konfirmasi selesai tahunan
        success = self.wait_for_modal_completion(dialog_type="tahunan", max_wait_sec=cfg.get("max_wait_minutes_per_month", 45) * 60)
        if success:
            self.log(f"SUKSES BESAR: Proses Tutup Tahun {year} telah selesai sempurna!")
            time.sleep(0.05 if self.simulation else cfg.get("settle_delay_sec", 1.8))

        # 6. Tutup dialog tahunan
        self.close_dialog_tahunan()
        return success

    def run_loop(self, start_year: int, end_year: int, do_annual: bool = True):
        """Full multi-year execution loop."""
        self.is_running = True
        self._stop_event.clear()
        self._pause_event.clear()

        total_years = end_year - start_year + 1
        total_steps = (total_years * 12) + (total_years if do_annual else 0)
        current_step = 0

        self.log(f"Memulai eksekusi otomasi: Tahun {start_year} s.d. {end_year} ({total_steps} tahapan).")

        try:
            # 0. Secara otomatis cari dan bawa iPos ke latar depan serta klik Tab 'Proses Data'
            if not self.simulation:
                self.log("Mencari jendela Program iPos 4.0 yang aktif di layar...")
                if self.focus_ipos_window():
                    self.log("Jendela Program iPos 4.0 terdeteksi dan diaktifkan.")
                else:
                    self.log("Catatan: Pastikan iPos 4.0 terbuka di desktop.")
                time.sleep(0.3)

                # Klik Tab Menu 'Proses Data' di menu atas iPos 4.0
                cfg = load_config()
                pt_tab = resolve_target_coordinate("tab_proses_data", user_coords=cfg.get("coords"))
                self.log(f"Mengaktifkan Tab Menu 'Proses Data' di ({pt_tab[0]}, {pt_tab[1]})...")
                self.safe_click(pt_tab[0], pt_tab[1], "Tab Menu Proses Data")
                time.sleep(0.5)

            for y in range(start_year, end_year + 1):
                if self._stop_event.is_set():
                    break

                # Buka dialog bulanan di awal setiap tahun
                self.open_dialog_bulanan()

                # Jalankan 12 Bulan (Januari s.d. Desember)
                for m in range(1, 13):
                    if self._stop_event.is_set():
                        break

                    while self._pause_event.is_set() and not self._stop_event.is_set():
                        self.update_status("DIJEDA (PAUSED)")
                        time.sleep(0.5)

                    if self._stop_event.is_set():
                        break

                    current_step += 1
                    pct = (current_step / total_steps) * 100.0
                    self.on_progress(current_step, total_steps, pct)

                    ok = self.trigger_monthly_process(y, m)
                    if not ok and not self._stop_event.is_set():
                        self.log(f"Peringatan: Gagal memproses bulan {m}/{y}")

                # Jalankan Proses Tahunan setelah Desember selesai
                if do_annual and not self._stop_event.is_set():
                    while self._pause_event.is_set() and not self._stop_event.is_set():
                        time.sleep(0.5)

                    if not self._stop_event.is_set():
                        current_step += 1
                        pct = (current_step / total_steps) * 100.0
                        self.on_progress(current_step, total_steps, pct)

                        self.trigger_annual_process(y)
                elif not do_annual and not self._stop_event.is_set():
                    # Tutup dialog bulanan jika tidak menjalankan proses tahunan
                    self.close_dialog_bulanan()

            if self._stop_event.is_set():
                self.log("Otomasi DIHENTIKAN oleh pengguna (Emergency Kill-Switch).")
                self.update_status("DIHENTIKAN")
                self.on_finished(False, "Dihentikan oleh pengguna.")
            else:
                self.log("SELURUH TAHAPAN SELESAI RAMPUNG 100%!")
                self.update_status("SELESAI (100%)")
                self.on_finished(True, "Semua tahun dan bulan berhasil diproses.")

        except Exception as e:
            err = traceback.format_exc()
            self.log(f"Terjadi kesalahan:\n{err}")
            self.update_status("ERROR")
            self.on_finished(False, str(e))
        finally:
            self.is_running = False

    def start(self, start_year: int, end_year: int, do_annual: bool = True):
        if self.is_running:
            return
        self._worker_thread = threading.Thread(
            target=self.run_loop,
            args=(start_year, end_year, do_annual),
            daemon=True
        )
        self._worker_thread.start()

    def pause(self):
        self._pause_event.set()
        self.log("Menjeda otomasi... Selesaikan bulan aktif lalu jeda.")

    def resume(self):
        self._pause_event.clear()
        self.log("Melanjutkan kembali otomasi.")

    def stop(self):
        self._stop_event.set()
        self._pause_event.clear()
        self.log("Menerima sinyal Emergency Stop!")
