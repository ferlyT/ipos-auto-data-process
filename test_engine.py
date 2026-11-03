"""
Unit and integration test for AutoProcessorEngine simulation mode and Calibration logic.
Verifies multi-year loop, month step transitions, annual closing trigger, tab parsing, and calibration.
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config
from engine import AutoProcessorEngine, MONTH_NAMES, REL_OFFSETS_BULANAN
from vision import get_default_scaled_coordinates

def test_engine_simulation():
    print("Testing Engine in Simulation Mode...")
    logs = []
    statuses = []
    progress_history = []
    finished_result = {}

    def on_log(msg):
        logs.append(msg)

    def on_status(st):
        statuses.append(st)

    def on_prog(cur, total, pct):
        progress_history.append((cur, total, pct))

    def on_finished(ok, msg):
        finished_result["ok"] = ok
        finished_result["msg"] = msg

    engine = AutoProcessorEngine(
        on_log=on_log,
        on_status=on_status,
        on_progress=on_prog,
        on_finished=on_finished,
        simulation=True
    )

    # Test 1 Year (2024): 12 months + 1 annual = 13 steps
    engine.run_loop(start_year=2024, end_year=2024, do_annual=True)

    assert finished_result.get("ok") is True, f"Failed: {finished_result}"
    assert len(progress_history) == 13, f"Expected 13 progress steps, got {len(progress_history)}"
    
    last_step = progress_history[-1]
    assert last_step[0] == 13 and last_step[1] == 13 and last_step[2] == 100.0, f"Last step mismatch: {last_step}"
    
    print("[PASS] Test 1 Year (2024) with Annual Process: 13/13 steps completed.")

    # Test Emergency Stop in separate thread
    print("Testing Emergency Stop signal...")
    stopped_result = {}
    engine_stop = AutoProcessorEngine(
        on_log=lambda m: None,
        on_status=lambda s: None,
        on_progress=lambda c, t, p: None,
        on_finished=lambda ok, msg: stopped_result.update({"ok": ok, "msg": msg}),
        simulation=True
    )

    # Start loop in background and stop after 0.1s
    engine_stop.start(2020, 2030, True)
    time.sleep(0.15)
    engine_stop.stop()
    
    # Wait for worker thread to stop
    if engine_stop._worker_thread:
        engine_stop._worker_thread.join(timeout=3.0)

    assert stopped_result.get("ok") is False, "Stop signal should mark result ok=False"
    print("[PASS] Emergency Stop test succeeded.")

    # Test Active Tab & iPos title parsing
    print("Testing Active Tab parsing from iPos window titles...")
    t1 = "Neraca - i P o s 4.0.9.0, User : ADMIN, Lokasi : UTM, Host : 127.0.0.1, Database : bafnov2026"
    res1 = AutoProcessorEngine.parse_ipos_title(t1)
    assert res1["is_ipos"] is True, "Failed to identify iPos window"
    assert res1["active_tab"] == "Neraca", f"Expected tab 'Neraca', got {res1['active_tab']}"
    assert res1["database"] == "bafnov2026", f"Expected database 'bafnov2026', got {res1['database']}"
    assert res1["user"] == "ADMIN", f"Expected user 'ADMIN', got {res1['user']}"

    t2 = "Menu Utama - i P o s 4.0.9.0, User : ADMIN, Lokasi : UTM, Host : 127.0.0.1, Database : bafnov2026"
    res2 = AutoProcessorEngine.parse_ipos_title(t2)
    assert res2["active_tab"] == "Menu Utama"

    t3 = "Laporan Penjualan - iPos 4.0"
    res3 = AutoProcessorEngine.parse_ipos_title(t3)
    assert res3["active_tab"] == "Laporan Penjualan"
    print("[PASS] Active Tab parsing test succeeded.")

    # Test Month Selection & Calibration Offsets
    print("Testing Month Selection naming & calibration offsets...")
    assert MONTH_NAMES[0] == "Januari", f"Month 1 should be 'Januari', got {MONTH_NAMES[0]}"
    assert MONTH_NAMES[1] == "Februari", f"Month 2 should be 'Februari', got {MONTH_NAMES[1]}"
    assert len(MONTH_NAMES) == 12

    # Verify dropdown_bulan offset relative to bulanan dialog
    assert "dropdown_bulan" in REL_OFFSETS_BULANAN
    dx, dy = REL_OFFSETS_BULANAN["dropdown_bulan"]
    assert dx == 219 and dy == 274, f"Unexpected dropdown_bulan relative offset: {dx}, {dy}"

    # Verify default scaled coordinates include bulanan_dropdown_bulan
    defs = get_default_scaled_coordinates()
    assert "bulanan_dropdown_bulan" in defs
    print("[PASS] Month Selection & Calibration offset tests succeeded.")

    print("\nALL AUTOMATED ENGINE & CALIBRATION TESTS PASSED!")

if __name__ == "__main__":
    test_engine_simulation()
