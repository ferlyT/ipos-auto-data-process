"""
Configuration module for iPos 4.0 Auto Processor Bot.
Handles persistent settings, coordinates, hotkeys, and timing.
"""
import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "emergency_hotkey": "f12",
    "expected_process_duration_sec": 30,      # Perkiraan waktu proses per bulan (~30 detik)
    "min_wait_before_check_sec": 15,          # Waktu tunggu minimal sebelum cek penyelesaian
    "settle_delay_sec": 1.5,                  # Jeda stabilisasi antar bulan
    "popup_poll_interval_sec": 1.0,           # Interval polling status
    "max_wait_minutes_per_month": 45,         # Timeout pengaman
    "auto_annual_after_december": True,
    "check_perbaikan_stok": False,
    "window_title_keywords": ["Proses Bulanan", "Proses Tahunan", "Proses Data", "iPos", "Program iPos"],
    "calibrated": True,
    "coords": {
        "tab_proses_data": [595, 43],             # Tab 'Proses Data' di Menu Atas
        "ribbon_bulanan": [40, 85],               # Tombol Ribbon 'Proses Bulanan'
        "ribbon_tahunan": [110, 85],              # Tombol Ribbon 'Proses Tahunan'
        "bulanan_dropdown_bulan": [922, 502],     # Dropdown Bulan di Proses Bulanan
        "bulanan_spin_tahun": [1028, 502],        # Input Tahun di Proses Bulanan
        "bulanan_chk_perbaikan_stok": [874, 531], # Checkbox Perbaikan Stok
        "bulanan_btn_proses": [926, 604],         # Tombol [ Proses ] Bulanan
        "bulanan_label_status": [947, 682],       # Label status 'Proses Selesai'
        "bulanan_btn_tutup": [1101, 718],         # Tombol [ Tutup ] Bulanan
        "tahunan_spin_tahun": [1028, 516],        # Input Tahun di Proses Tahunan
        "tahunan_btn_proses": [926, 615],         # Tombol [ Proses ] Tahunan
        "tahunan_btn_tutup": [1101, 718],         # Tombol [ Tutup ] Tahunan
        "modal_btn_yes": [1009, 638],             # Tombol [ Yes ] Modal Konfirmasi
        "modal_btn_no": [1091, 638],              # Tombol [ No ] Modal Konfirmasi
        "popup_btn_ok": [960, 570]                # Tombol OK Popup Selesai
    }
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                if "coords" in data:
                    merged["coords"] = {**DEFAULT_CONFIG["coords"], **data["coords"]}
                return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"Gagal menyimpan config: {e}")
