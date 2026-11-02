"""
Interactive Coordinate Calibration & Inspector Tool for iPos 4.0 Auto Processor.
Allows the user to:
1. Inspect pre-calibrated coordinates.
2. Click 'Arahkan' to smoothly move mouse cursor to verify where it points.
3. Click 'Ambil' to record exact coordinate under mouse cursor.
4. Click 'Uji Pilih Januari' to test selecting month in iPos live!
"""
import time
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
from config import load_config, save_config
from vision import get_default_scaled_coordinates

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
        self.root.geometry("660x630")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.cfg = load_config()
        self.coords = self.cfg.get("coords", {})

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

        btn_test_jan = ttk.Button(frame_test, text="▶ Uji Pilih 'Januari'", command=lambda: self.test_select_month(1))
        btn_test_jan.pack(side="left", padx=4)

        btn_test_feb = ttk.Button(frame_test, text="▶ Uji Pilih 'Februari'", command=lambda: self.test_select_month(2))
        btn_test_feb.pack(side="left", padx=4)

        lbl_test_hint = ttk.Label(frame_test, text="(Pastikan dialog iPos sedang terbuka)", font=("Segoe UI", 8, "italic"))
        lbl_test_hint.pack(side="left", padx=5)

        # Bottom buttons
        frame_bottom = ttk.Frame(root)
        frame_bottom.pack(fill="x", padx=15, pady=8)

        btn_reset = ttk.Button(frame_bottom, text="↺ Reset ke Default", command=self.reset_to_defaults)
        btn_reset.pack(side="left")

        btn_save = ttk.Button(frame_bottom, text="💾 Simpan Pengaturan", command=self.save_all)
        btn_save.pack(side="right", padx=5)

    def move_mouse_to(self, key: str):
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
        val = self.coords.get("bulanan_dropdown_bulan")
        if not val:
            defaults = get_default_scaled_coordinates()
            val = defaults.get("bulanan_dropdown_bulan")

        if not val:
            messagebox.showwarning("Peringatan", "Koordinat dropdown bulan belum diset!")
            return

        month_name = "Januari" if target_month_idx == 1 else "Februari"
        self.label_instruct.config(text=f"Menguji pemilihan {month_name} di ({val[0]}, {val[1]})...")
        self.root.update()

        # 1. Klik tepat pada combobox bulan untuk fokus
        pyautogui.click(val[0], val[1])
        time.sleep(0.3)

        # 2. Reset paksa ke Januari dari bulan default apa pun (Roll-up 15x ke atas)
        for _ in range(15):
            pyautogui.press('up')
            time.sleep(0.02)
        time.sleep(0.15)

        # 3. Turun ke bulan target (Down) sebanyak (target_month_idx - 1) kali
        for _ in range(target_month_idx - 1):
            pyautogui.press('down')
            time.sleep(0.06)
        time.sleep(0.15)

        # 4. Kunci pilihan dengan Enter (jangan Tab agar tidak lompat ke Tahun)
        pyautogui.press('enter')
        time.sleep(0.2)

        self.label_instruct.config(text=f"Pengujian selesai. Periksa apakah dropdown berubah jadi {month_name}.")
        messagebox.showinfo("Uji Selesai", f"Perintah pilih '{month_name}' telah dikirim ke ({val[0]}, {val[1]}). Periksa dropdown iPos Anda.")

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
