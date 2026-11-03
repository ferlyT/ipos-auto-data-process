"""
Interactive Coordinate Calibration & Inspector Tool for iPos 4.0 Auto Processor.
Allows the user to:
1. Inspect pre-calibrated coordinates.
2. Click 'Arahkan' to smoothly move mouse cursor to verify where it points.
3. Click 'Ambil' to record exact coordinate under mouse cursor.
4. Click 'Uji Pilih Januari' / 'Uji Pilih Februari' to test selecting month in iPos live!
"""
import time
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui

from config import load_config, save_config
from vision import get_default_scaled_coordinates
from engine import AutoProcessorEngine, MONTH_NAMES

TARGET_KEYS = [
    ("tab_proses_data", "1. Tab Ribbon 'Proses Data'"),
    ("ribbon_bulanan", "2. Ribbon 'Proses Bulanan'"),
    ("ribbon_tahunan", "3. Ribbon 'Proses Tahunan'"),
    ("bulanan_dropdown_bulan", "4. Dropdown Bulan (Bulanan)"),
    ("bulanan_spin_tahun", "5. Input Tahun (Bulanan)"),
    ("bulanan_chk_perbaikan_stok", "6. Checkbox 'Perbaikan Stok'"),
    ("bulanan_btn_proses", "7. Tombol [ Proses ] (Bulanan)"),
    ("bulanan_btn_tutup", "8. Tombol [ Tutup ] (Bulanan)"),
    ("tahunan_spin_tahun", "9. Input Tahun (Tahunan)"),
    ("tahunan_btn_proses", "10. Tombol [ Proses ] (Tahunan)"),
    ("tahunan_btn_tutup", "11. Tombol [ Tutup ] (Tahunan)"),
    ("modal_btn_yes", "12. Tombol [ Yes ] Modal Konfirmasi"),
    ("popup_btn_ok", "13. Tombol OK Popup Selesai")
]

class CalibrationApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pengecekan & Kalibrasi Koordinat iPos 4.0")
        # Position window docked on left side so it never obscures centered iPos dialogs
        self.root.geometry("660x650+20+60")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.cfg = load_config()
        self.coords = self.cfg.get("coords", {})

        # Engine helper for automatic dialog detection, focusing, and safe clicks
        self.engine = AutoProcessorEngine(
            on_log=self._on_engine_log,
            on_status=lambda s: None,
            on_progress=lambda c, t, p: None,
            on_finished=lambda ok, msg: None,
            simulation=False
        )

        # Header instructions
        self.label_instruct = ttk.Label(
            root,
            text="Jika posisi jendela iPos Anda digeser (misal di kanan monitor):\nKlik tombol [Ambil] untuk mencatat koordinat elemen di posisi baru Anda.",
            font=("Segoe UI", 9),
            justify="center"
        )
        self.label_instruct.pack(pady=6)

        # Table frame
        frame_table = ttk.Frame(root)
        frame_table.pack(fill="both", expand=True, padx=15, pady=2)

        self.coord_vars = {}
        defaults = get_default_scaled_coordinates()

        for key, label in TARGET_KEYS:
            row = ttk.Frame(frame_table)
            row.pack(fill="x", pady=1)

            lbl = ttk.Label(row, text=label, width=30, anchor="w", font=("Segoe UI", 8))
            lbl.pack(side="left")

            val = self.coords.get(key)
            if not val and key in defaults:
                val = defaults[key]
                val_str = f"({val[0]}, {val[1]})"
            elif val:
                val_str = f"({val[0]}, {val[1]})"
            else:
                val_str = "(Belum diset)"

            var = tk.StringVar(value=val_str)
            self.coord_vars[key] = var

            lbl_val = ttk.Label(row, textvariable=var, width=15, foreground="#15803d", font=("Consolas", 8, "bold"))
            lbl_val.pack(side="left", padx=4)

            # Move mouse to coordinate button
            btn_test = ttk.Button(row, text="Arahkan", width=8, command=lambda k=key: self.move_mouse_to(k))
            btn_test.pack(side="right", padx=(2, 0))

            # Re-record coordinate button
            btn_rec = ttk.Button(row, text="Ambil", width=7, command=lambda k=key: self.capture_coordinate(k))
            btn_rec.pack(side="right")

        # Test action bar
        frame_test = ttk.LabelFrame(root, text=" Pengujian Aksi Langsung ke iPos ", padding=8)
        frame_test.pack(fill="x", padx=15, pady=4)

        btn_test_jan = ttk.Button(
            frame_test,
            text="▶ Uji Pilih 'Januari'",
            command=lambda: self.test_select_month(1)
        )
        btn_test_jan.pack(side="left", padx=4)

        btn_test_feb = ttk.Button(
            frame_test,
            text="▶ Uji Pilih 'Februari'",
            command=lambda: self.test_select_month(2)
        )
        btn_test_feb.pack(side="left", padx=4)

        lbl_sep = ttk.Separator(frame_test, orient="vertical")
        lbl_sep.pack(side="left", fill="y", padx=8)

        # Dropdown test for any other month
        self.selected_test_month = tk.StringVar(value="Maret")
        combo_months = ttk.Combobox(
            frame_test,
            textvariable=self.selected_test_month,
            values=MONTH_NAMES,
            state="readonly",
            width=11
        )
        combo_months.pack(side="left", padx=4)

        btn_test_custom = ttk.Button(
            frame_test,
            text="▶ Uji Bulan",
            command=self._test_selected_combo_month
        )
        btn_test_custom.pack(side="left", padx=2)

        lbl_test_hint = ttk.Label(
            frame_test,
            text="(Otomatis buka & fokus iPos)",
            font=("Segoe UI", 8, "italic"),
            foreground="#555555"
        )
        lbl_test_hint.pack(side="left", padx=5)

        # Bottom buttons
        frame_bottom = ttk.Frame(root)
        frame_bottom.pack(fill="x", padx=15, pady=8)

        btn_reset = ttk.Button(frame_bottom, text="↺ Reset ke Default", command=self.reset_to_defaults)
        btn_reset.pack(side="left")

        btn_save = ttk.Button(frame_bottom, text="💾 Simpan Pengaturan", command=self.save_all)
        btn_save.pack(side="right", padx=5)

    def _on_engine_log(self, msg: str):
        self.label_instruct.config(text=msg)
        try:
            self.root.update()
        except Exception:
            pass

    def _test_selected_combo_month(self):
        m_str = self.selected_test_month.get()
        if m_str in MONTH_NAMES:
            idx = MONTH_NAMES.index(m_str) + 1
            self.test_select_month(idx)

    def move_mouse_to(self, key: str):
        # Cek apakah kontrol dialog dapat dihitung secara dinamis dari dialog aktif
        val = None
        if "bulanan" in key:
            ctl = key.replace("bulanan_", "").replace("chk_perbaikan_stok", "chk_stok")
            if self.engine.get_dialog_rect("bulanan"):
                val = self.engine.get_control_coord(ctl, "bulanan")
        elif "tahunan" in key:
            ctl = key.replace("tahunan_", "")
            if self.engine.get_dialog_rect("tahunan"):
                val = self.engine.get_control_coord(ctl, "tahunan")

        if not val:
            val = self.coords.get(key)
        if not val:
            defaults = get_default_scaled_coordinates()
            val = defaults.get(key)

        if val:
            self.label_instruct.config(text=f"Mengarahkan mouse ke {key}: ({val[0]}, {val[1]})...")
            self.root.update()
            pyautogui.moveTo(val[0], val[1], duration=0.4)
            self.label_instruct.config(text=f"Mouse berada di {key}: ({val[0]}, {val[1]}).")

    def capture_coordinate(self, key: str):
        self.label_instruct.config(text="Arahkan mouse ke posisi elemen target...")
        self.root.update()

        for i in range(3, 0, -1):
            self.label_instruct.config(text=f"Merekam posisi dalam {i} detik... Siapkan kursor di tombol/input target!")
            self.root.update()
            time.sleep(1)

        x, y = pyautogui.position()
        self.coords[key] = [x, y]
        self.coord_vars[key].set(f"({x}, {y})")
        self.label_instruct.config(text=f"Terekam untuk '{key}': ({x}, {y})")

    def test_select_month(self, target_month_idx: int):
        month_name = MONTH_NAMES[target_month_idx - 1] if 1 <= target_month_idx <= len(MONTH_NAMES) else f"Bulan {target_month_idx}"
        
        self.label_instruct.config(text=f"Menghubungkan ke iPos 4.0 untuk menguji pemilihan '{month_name}'...")
        self.root.update()

        # 1. Cek apakah jendela iPos 4.0 terdeteksi
        ipos_hwnd = self.engine.find_ipos_window()
        if not ipos_hwnd:
            messagebox.showerror(
                "iPos Tidak Ditemukan",
                "Program iPos 4.0 tidak terdeteksi sedang berjalan di Windows.\n\n"
                "Silakan buka aplikasi iPos 4.0 terlebih dahulu sebelum melakukan pengujian!"
            )
            return

        # 2. Bawa iPos ke depan dan fokuskan
        self.engine.focus_ipos_window()
        time.sleep(0.3)

        # 3. Cek apakah dialog 'Proses Bulanan' sudah terbuka di layar
        rect = self.engine.get_dialog_rect("bulanan")
        if not rect:
            self.label_instruct.config(text="Membuka dialog 'Proses Bulanan' di iPos...")
            self.root.update()

            # Tutup dialog tahunan jika sedang terbuka agar tidak tumpang-tindih
            if self.engine.get_dialog_rect("tahunan"):
                self.engine.close_dialog("tahunan")
                time.sleep(0.5)

            opened = self.engine.open_dialog_bulanan()
            if not opened:
                messagebox.showwarning(
                    "Peringatan",
                    "Gagal membuka dialog 'Proses Bulanan' secara otomatis.\n\n"
                    "Pastikan aplikasi iPos 4.0 aktif dan tab Ribbon 'Proses Data' dapat diakses."
                )
                return
            rect = self.engine.get_dialog_rect("bulanan")

        # 4. Ambil koordinat dropdown bulan (secara dinamis mengikuti posisi dialog terkini)
        pt = self.engine.get_control_coord("dropdown_bulan", "bulanan")
        if not pt:
            pt = self.coords.get("bulanan_dropdown_bulan")
        if not pt:
            messagebox.showwarning("Peringatan", "Koordinat dropdown bulan tidak ditemukan!")
            return

        # Sinkronkan koordinat dinamis ke tabel tampilan & config lokal
        self.coords["bulanan_dropdown_bulan"] = [pt[0], pt[1]]
        if "bulanan_dropdown_bulan" in self.coord_vars:
            self.coord_vars["bulanan_dropdown_bulan"].set(f"({pt[0]}, {pt[1]})")

        self.label_instruct.config(text=f"Mengarahkan kursor & memilih '{month_name}' pada koordinat ({pt[0]}, {pt[1]})...")
        self.root.update()

        # 5. Fokuskan kembali iPos & klik combobox bulan (DevExpress mouseDown/mouseUp)
        self.engine.focus_ipos_window()
        time.sleep(0.2)
        self.engine.safe_click(pt[0], pt[1], f"Dropdown Bulan ({month_name})")
        time.sleep(0.35)

        # 6. Reset paksa ke posisi 'Januari' (Roll-up 15x ke atas)
        for _ in range(15):
            pyautogui.press('up')
            time.sleep(0.04)
        time.sleep(0.15)

        # 7. Turun ke bulan target (Januari: 0x, Februari: 1x, Maret: 2x, dst.)
        for _ in range(target_month_idx - 1):
            pyautogui.press('down')
            time.sleep(0.08)
        time.sleep(0.15)

        # 8. Kunci pilihan dengan Enter
        pyautogui.press('enter')
        time.sleep(0.25)

        self.label_instruct.config(text=f"Uji Berhasil! Bulan '{month_name}' telah terpilih pada dialog Proses Bulanan.")
        self.root.update()

        messagebox.showinfo(
            "Uji Berhasil",
            f"Perintah pemilihan '{month_name}' sukses dikirim ke ({pt[0]}, {pt[1]}).\n\n"
            f"Periksa combobox Bulan pada dialog 'Proses Bulanan' di iPos 4.0:\n"
            f"Status combobox sekarang menampilkan '{month_name}'."
        )

    def reset_to_defaults(self):
        defaults = get_default_scaled_coordinates()
        for key, _ in TARGET_KEYS:
            self.coords[key] = list(defaults.get(key, [0, 0]))
            self.coord_vars[key].set(f"({self.coords[key][0]}, {self.coords[key][1]})")
        self.save_all()

    def save_all(self):
        self.cfg["coords"] = self.coords
        self.cfg["calibrated"] = True
        save_config(self.cfg)
        messagebox.showinfo("Sukses", "Koordinat berhasil disimpan ke config.json!")

if __name__ == "__main__":
    r = tk.Tk()
    app = CalibrationApp(r)
    r.mainloop()
