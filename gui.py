"""
Main GUI Floating Application for iPos 4.0 Auto Processor Bot.
Built with Tkinter (Always-on-Top), supports multi-year range, real-time logging,
live progress bar, and Emergency Stop hotkeys.
"""
import sys
import os
import time
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config
from engine import AutoProcessorEngine
from calibration import CalibrationApp

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

class MainBotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Proses Data iPos 4.0")
        self.root.geometry("640x660")
        self.root.minsize(580, 600)
        self.root.attributes("-topmost", True)

        self.cfg = load_config()
        self.engine = None
        self.is_paused = False

        # Timer & Stopwatch variables
        self.start_time = None
        self.elapsed_offset = 0.0
        self.timer_running = False
        self._timer_after_id = None

        self._build_ui()
        self._setup_hotkeys()

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg="#1e293b", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="iPos 4.0 • Auto Data Closing Assistant",
            font=("Segoe UI", 13, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        )
        title.pack(anchor="w", padx=16, pady=(10, 2))

        sub = tk.Label(
            header,
            text="Otomasi Siklus Lengkap: Proses Bulanan (Jan-Des) & Proses Tahunan",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1e293b"
        )
        sub.pack(anchor="w", padx=16)

        # Main content
        content = ttk.Frame(self.root, padding=12)
        content.pack(fill="both", expand=True)

        # 1. Parameter Frame
        param_frame = ttk.LabelFrame(content, text=" 1. Rentang Periode & Opsi Eksekusi ", padding=10)
        param_frame.pack(fill="x", pady=(0, 10))

        current_year = datetime.datetime.now().year

        row1 = ttk.Frame(param_frame)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="Tahun Awal:", width=14).pack(side="left")
        self.spin_start_year = ttk.Spinbox(row1, from_=2000, to=2099, width=10)
        self.spin_start_year.set(current_year - 1)
        self.spin_start_year.pack(side="left", padx=(0, 20))

        ttk.Label(row1, text="Tahun Akhir:", width=14).pack(side="left")
        self.spin_end_year = ttk.Spinbox(row1, from_=2000, to=2099, width=10)
        self.spin_end_year.set(current_year)
        self.spin_end_year.pack(side="left")

        row2 = ttk.Frame(param_frame)
        row2.pack(fill="x", pady=(6, 2))

        self.var_annual = tk.BooleanVar(value=self.cfg.get("auto_annual_after_december", True))
        chk_annual = ttk.Checkbutton(
            row2,
            text="Jalankan Proses Tahunan setiap selesai bulan Desember",
            variable=self.var_annual
        )
        chk_annual.pack(side="left")

        row3 = ttk.Frame(param_frame)
        row3.pack(fill="x", pady=(2, 2))

        self.var_perbaikan_stok = tk.BooleanVar(value=self.cfg.get("check_perbaikan_stok", False))
        chk_stok = ttk.Checkbutton(
            row3,
            text="Centang opsi 'Perbaikan Stok' (Hanya pada bulan & tahun aktif saat ini)",
            variable=self.var_perbaikan_stok
        )
        chk_stok.pack(side="left")

        row4 = ttk.Frame(param_frame)
        row4.pack(fill="x", pady=(4, 0))

        self.var_sim = tk.BooleanVar(value=False)
        chk_sim = ttk.Checkbutton(
            row4,
            text="Mode Simulasi (Dry-run tanpa klik mouse nyata)",
            variable=self.var_sim
        )
        chk_sim.pack(side="left")

        btn_calib = ttk.Button(row4, text="⚙ Kalibrasi Posisi UI", command=self.open_calibration)
        btn_calib.pack(side="right")

        # 2. Status & Progress Card
        status_frame = ttk.LabelFrame(content, text=" 2. Status & Progres Otomasi ", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))

        self.lbl_status = tk.Label(
            status_frame,
            text="STATUS: SIAP (Klik Mulai untuk Menjalankan Otomasi)",
            font=("Segoe UI", 10, "bold"),
            fg="#0f766e",
            bg="#f0fdf4",
            relief="solid",
            bd=1,
            padx=10,
            pady=6
        )
        self.lbl_status.pack(fill="x", pady=(0, 8))

        progress_row = ttk.Frame(status_frame)
        progress_row.pack(fill="x", pady=2)

        self.progress_bar = ttk.Progressbar(progress_row, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_pct = ttk.Label(progress_row, text="0%", font=("Segoe UI", 9, "bold"), width=6)
        self.lbl_pct.pack(side="right")

        step_row = ttk.Frame(status_frame)
        step_row.pack(fill="x", pady=(4, 0))

        self.lbl_step = ttk.Label(step_row, text="Tahapan: 0 dari 0 selesai", font=("Segoe UI", 8), foreground="#64748b")
        self.lbl_step.pack(side="left")

        self.lbl_timer = ttk.Label(
            step_row,
            text="Waktu Berjalan: 00:00:00",
            font=("Segoe UI", 8, "bold"),
            foreground="#0369a1"
        )
        self.lbl_timer.pack(side="right")

        # 3. Control Buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill="x", pady=(0, 10))

        self.btn_start = tk.Button(
            btn_frame,
            text="▶ MULAI OTOMASI",
            font=("Segoe UI", 10, "bold"),
            bg="#16a34a",
            fg="white",
            activebackground="#15803d",
            padx=16,
            pady=6,
            command=self.start_automation
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_pause = tk.Button(
            btn_frame,
            text="⏸ JEDA",
            font=("Segoe UI", 10),
            bg="#f59e0b",
            fg="white",
            state="disabled",
            padx=12,
            pady=6,
            command=self.toggle_pause
        )
        self.btn_pause.pack(side="left", padx=(0, 8))

        self.btn_stop = tk.Button(
            btn_frame,
            text="⏹ HENTIKAN (ESC/F12)",
            font=("Segoe UI", 10, "bold"),
            bg="#dc2626",
            fg="white",
            state="disabled",
            padx=12,
            pady=6,
            command=self.stop_automation
        )
        self.btn_stop.pack(side="left")

        lbl_failsafe = ttk.Label(
            btn_frame,
            text="Emergency Stop: Tekan F12 atau ESC kapan saja",
            font=("Segoe UI", 8, "italic"),
            foreground="#dc2626"
        )
        lbl_failsafe.pack(side="right", pady=6)

        # 4. Activity Terminal Log
        log_frame = ttk.LabelFrame(content, text=" 3. Terminal Log Aktivitas ", padding=6)
        log_frame.pack(fill="both", expand=True)

        self.txt_log = scrolledtext.ScrolledText(
            log_frame,
            height=9,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#38bdf8",
            font=("Consolas", 9)
        )
        self.txt_log.pack(fill="both", expand=True)

        self.append_log("Bot Auto-Proses Data iPos 4.0 siap digunakan.")
        self.append_log("Bot otomatis mencari iPos 4.0 yang aktif dan mengaktifkan Tab 'Proses Data'.")

    def _setup_hotkeys(self):
        if HAS_KEYBOARD:
            try:
                keyboard.add_hotkey("f12", self.on_hotkey_emergency_stop)
                keyboard.add_hotkey("esc", self.on_hotkey_emergency_stop)
            except Exception as e:
                self.append_log(f"Peringatan: Gagal register global hotkey: {e}")

    def on_hotkey_emergency_stop(self):
        if self.engine and self.engine.is_running:
            self.root.after(0, self.stop_automation)

    # =========================================================================
    # Timelapse / Stopwatch Timer Methods
    # =========================================================================
    def _start_timer(self):
        self.start_time = time.time()
        self.elapsed_offset = 0.0
        self.timer_running = True
        self.lbl_timer.config(text="Waktu Berjalan: 00:00:00")
        self._tick_timer()

    def _pause_timer(self):
        if self.timer_running and self.start_time:
            self.elapsed_offset += time.time() - self.start_time
            self.start_time = None
            self.timer_running = False

    def _resume_timer(self):
        if not self.timer_running:
            self.start_time = time.time()
            self.timer_running = True
            self._tick_timer()

    def _stop_timer(self) -> str:
        final_str = "00:00:00"
        if self.timer_running and self.start_time:
            total_sec = self.elapsed_offset + (time.time() - self.start_time)
            final_str = self._format_duration(total_sec)
        elif self.elapsed_offset > 0:
            final_str = self._format_duration(self.elapsed_offset)

        self.timer_running = False
        self.start_time = None
        if self._timer_after_id:
            try:
                self.root.after_cancel(self._timer_after_id)
            except Exception:
                pass
            self._timer_after_id = None
        return final_str

    def _format_duration(self, seconds: float) -> str:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _tick_timer(self):
        if self.timer_running and self.start_time:
            total_sec = self.elapsed_offset + (time.time() - self.start_time)
            self.lbl_timer.config(text=f"Waktu Berjalan: {self._format_duration(total_sec)}")
            self._timer_after_id = self.root.after(500, self._tick_timer)

    def append_log(self, text: str):
        def _do():
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)
        self.root.after(0, _do)

    def set_status_text(self, text: str, alert_type: str = "info"):
        def _do():
            bg_colors = {
                "info": ("#f0fdf4", "#0f766e"),
                "running": ("#eff6ff", "#1d4ed8"),
                "paused": ("#fefce8", "#b45309"),
                "error": ("#fef2f2", "#b91c1c")
            }
            bg, fg = bg_colors.get(alert_type, ("#f0fdf4", "#0f766e"))
            self.lbl_status.config(text=f"STATUS: {text}", bg=bg, fg=fg)
        self.root.after(0, _do)

    def update_progress(self, cur: int, total: int, pct: float):
        def _do():
            self.progress_bar["value"] = pct
            self.lbl_pct.config(text=f"{pct:.1f}%")
            self.lbl_step.config(text=f"Tahapan: {cur} dari {total} selesai")
        self.root.after(0, _do)

    def open_calibration(self):
        calib_win = tk.Toplevel(self.root)
        CalibrationApp(calib_win)

    def start_automation(self):
        try:
            start_y = int(self.spin_start_year.get())
            end_y = int(self.spin_end_year.get())
        except ValueError:
            messagebox.showerror("Error Input", "Tahun Awal dan Akhir harus berupa angka valid!")
            return

        if start_y > end_y:
            messagebox.showerror("Error Input", "Tahun Awal tidak boleh lebih besar dari Tahun Akhir!")
            return

        do_annual = self.var_annual.get()
        chk_stok = self.var_perbaikan_stok.get()
        sim_mode = self.var_sim.get()

        # UI State update (Eksekusi Instan Satu-Klik)
        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal", text="⏸ JEDA")
        self.btn_stop.config(state="normal")
        self.is_paused = False
        self.progress_bar["value"] = 0
        self.lbl_pct.config(text="0%")

        self.set_status_text("MENJALANKAN OTOMASI...", "running")
        self.append_log(f"--- MEMULAI SESI OTOMASI: {start_y} s.d. {end_y} ---")

        bot_rect = (
            self.root.winfo_rootx(),
            self.root.winfo_rooty(),
            self.root.winfo_width(),
            self.root.winfo_height()
        )

        self.engine = AutoProcessorEngine(
            on_log=self.append_log,
            on_status=self.handle_status_change,
            on_progress=self.update_progress,
            on_finished=self.on_engine_finished,
            simulation=sim_mode,
            check_perbaikan_stok=chk_stok,
            bot_window_rect=bot_rect
        )
        self._start_timer()
        self.engine.start(start_y, end_y, do_annual)

    def handle_status_change(self, text: str):
        if "DIJEDA" in text:
            self.is_paused = True
            self.btn_pause.config(text="▶ LANJUTKAN")
            self.set_status_text(text, "paused")
            self._pause_timer()
        else:
            if self.is_paused and ("MELANJUTKAN" in text or "BERJALAN" in text):
                self.is_paused = False
                self.btn_pause.config(text="⏸ JEDA")
                self._resume_timer()
            self.set_status_text(text, "running" if not self.is_paused else "paused")

    def toggle_pause(self):
        if not self.engine:
            return
        if not self.is_paused:
            self.engine.pause()
            self.is_paused = True
            self.btn_pause.config(text="▶ LANJUTKAN")
            self.set_status_text("DIJEDA (PAUSED)", "paused")
            self._pause_timer()
        else:
            self.engine.resume()
            self.is_paused = False
            self.btn_pause.config(text="⏸ JEDA")
            self.set_status_text("MELANJUTKAN KEMBALI...", "running")
            self._resume_timer()

    def stop_automation(self):
        if self.engine and self.engine.is_running:
            self.engine.stop()
            self.set_status_text("MENGHENTIKAN...", "error")
            dur = self._stop_timer()
            self.lbl_timer.config(text=f"Berhenti: {dur}")

    def on_engine_finished(self, success: bool, message: str):
        def _do():
            dur_str = self._stop_timer()
            self.btn_start.config(state="normal")
            self.btn_pause.config(state="disabled", text="⏸ JEDA")
            self.btn_stop.config(state="disabled")
            self.is_paused = False

            self.lbl_timer.config(text=f"Total: {dur_str}")
            self.append_log(f"--- TOTAL WAKTU EKSEKUSI: {dur_str} ---")

            if success:
                self.set_status_text("SELESAI DENGAN SUKSES (100%)", "info")
                messagebox.showinfo("Otomasi Selesai", f"Semua proses bulanan dan tahunan telah berhasil dijalankan!\nTotal Waktu: {dur_str}")
            else:
                self.set_status_text("OTOMASI DIHENTIKAN", "error")
        self.root.after(0, _do)

if __name__ == "__main__":
    tk_root = tk.Tk()
    app = MainBotApp(tk_root)
    tk_root.mainloop()
