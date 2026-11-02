"""
Vision and Coordinate Detection Module for iPos 4.0 Auto Processor.
Supports multi-scale template matching with bot-window exclusion masking
to automatically locate iPos controls anywhere on screen.
"""
import os
import ctypes
from typing import Optional, Tuple, Dict

try:
    import cv2
    import numpy as np
    import pyautogui
    HAS_VISION = True
except ImportError:
    HAS_VISION = False

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

def get_screen_resolution() -> Tuple[int, int]:
    """Get current monitor resolution (Width, Height)."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

def get_default_scaled_coordinates() -> dict:
    w, h = get_screen_resolution()
    sx = w / 1920.0
    sy = h / 1080.0

    return {
        "tab_proses_data": (int(621 * sx), int(43 * sy)),
        "ribbon_bulanan": (int(22 * sx), int(94 * sy)),
        "ribbon_tahunan": (int(68 * sx), int(85 * sy)),
        "bulanan_dropdown_bulan": (int(955 * sx), int(553 * sy)),
        "bulanan_spin_tahun": (int(1052 * sx), int(559 * sy)),
        "bulanan_chk_perbaikan_stok": (int(874 * sx), int(531 * sy)),
        "bulanan_btn_proses": (int(980 * sx), int(617 * sy)),
        "bulanan_label_status": (int(947 * sx), int(682 * sy)),
        "bulanan_btn_tutup": (int(1127 * sx), int(723 * sy)),
        "tahunan_spin_tahun": (int(1050 * sx), int(569 * sy)),
        "tahunan_btn_proses": (int(980 * sx), int(627 * sy)),
        "tahunan_btn_tutup": (int(1125 * sx), int(722 * sy)),
        "modal_btn_yes": (int(1038 * sx), int(587 * sy)),
        "modal_btn_no": (int(1091 * sx), int(638 * sy)),
        "popup_btn_ok": (int(960 * sx), int(570 * sy))
    }

def find_template_on_screen(
    template_name: str,
    threshold: float = 0.72,
    exclude_rect: Optional[Tuple[int, int, int, int]] = None
) -> Optional[Tuple[int, int]]:
    """
    Finds template on screen while completely masking out exclude_rect (e.g. Bot UI window).
    """
    if not HAS_VISION:
        return None

    tpl_path = os.path.join(ASSETS_DIR, template_name)
    if not os.path.exists(tpl_path):
        return None

    try:
        tpl = cv2.imread(tpl_path)
        if tpl is None:
            return None

        screen = pyautogui.screenshot()
        screen_bgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

        # Mask out excluded window area (Bot window)
        if exclude_rect:
            bx, by, bw, bh = exclude_rect
            bx1 = max(0, bx)
            by1 = max(0, by)
            bx2 = min(screen_bgr.shape[1], bx + bw)
            by2 = min(screen_bgr.shape[0], by + bh)
            if bx2 > bx1 and by2 > by1:
                screen_bgr[by1:by2, bx1:bx2] = 0

        best_val = -1
        best_loc = None

        for scale in [1.875, 1.75, 1.5, 1.25, 1.0, 0.8, 2.0]:
            tw = int(tpl.shape[1] * scale)
            th = int(tpl.shape[0] * scale)
            if tw >= screen_bgr.shape[1] or th >= screen_bgr.shape[0]:
                continue

            resized = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(screen_bgr, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val = max_val
                best_loc = (max_loc[0] + tw // 2, max_loc[1] + th // 2)

        if best_val >= threshold and best_loc:
            return best_loc
    except Exception:
        pass

    return None

def auto_detect_bulanan_controls(exclude_rect: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict[str, Tuple[int, int]]]:
    """
    Finds the 'Proses Bulanan' dialog anywhere on screen by finding the 'Periode :' anchor or header,
    and returns dynamically calculated coordinates for all controls.
    """
    # 1. Search for 'Periode :' label
    loc_periode = find_template_on_screen("label_periode.png", threshold=0.75, exclude_rect=exclude_rect)
    if loc_periode:
        px, py = loc_periode
        return {
            "bulanan_dropdown_bulan": (px + 60, py),
            "bulanan_spin_tahun": (px + 145, py),
            "bulanan_chk_perbaikan_stok": (px + 10, py + 28),
            "bulanan_btn_proses": (px + 50, py + 80),
            "bulanan_btn_tutup": (px + 205, py + 160)
        }

    # 2. Search for header 'PROSES BULANAN'
    loc_hdr = find_template_on_screen("header_bulanan.png", threshold=0.75, exclude_rect=exclude_rect)
    if loc_hdr:
        hx, hy = loc_hdr
        return {
            "bulanan_dropdown_bulan": (hx - 38, hy + 172),
            "bulanan_spin_tahun": (hx + 68, hy + 172),
            "bulanan_chk_perbaikan_stok": (hx - 86, hy + 201),
            "bulanan_btn_proses": (hx - 34, hy + 274),
            "bulanan_btn_tutup": (hx + 141, hy + 388)
        }

    return None

def auto_detect_tahunan_controls(exclude_rect: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict[str, Tuple[int, int]]]:
    """
    Finds the 'Proses Tutup Tahun' dialog anywhere on screen.
    """
    loc_hdr = find_template_on_screen("header_tahunan.png", threshold=0.75, exclude_rect=exclude_rect)
    if loc_hdr:
        hx, hy = loc_hdr
        return {
            "tahunan_spin_tahun": (hx + 89, hy + 217),
            "tahunan_btn_proses": (hx + 19, hy + 275),
            "tahunan_btn_tutup": (hx + 164, hy + 370)
        }
    return None

def resolve_target_coordinate(
    target_key: str,
    template_name: Optional[str] = None,
    user_coords: Optional[dict] = None,
    exclude_rect: Optional[Tuple[int, int, int, int]] = None
) -> Tuple[int, int]:
    """
    Hierarchical coordinate resolver:
    1. Check user custom calibrated coordinates from config.json (if set & calibrated)
    2. Auto-detect dialog controls dynamically via anchor vision matching
    3. Monitor-resolution scaled default coordinates
    """
    # 1. Custom user calibration
    if user_coords and target_key in user_coords and user_coords[target_key]:
        c = user_coords[target_key]
        return (c[0], c[1])

    # 2. Dynamic visual auto-detection
    if target_key.startswith("bulanan_"):
        detected = auto_detect_bulanan_controls(exclude_rect)
        if detected and target_key in detected:
            return detected[target_key]
    elif target_key.startswith("tahunan_"):
        detected = auto_detect_tahunan_controls(exclude_rect)
        if detected and target_key in detected:
            return detected[target_key]

    # 3. Direct template match
    if template_name:
        loc = find_template_on_screen(template_name, exclude_rect=exclude_rect)
        if loc:
            return loc

    # 4. Scaled baseline
    defaults = get_default_scaled_coordinates()
    return defaults.get(target_key, (960, 540))
