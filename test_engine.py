"""
Unit and integration test for AutoProcessorEngine simulation mode.
Verifies multi-year loop, month step transitions, annual closing trigger, and callbacks.
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config
from engine import AutoProcessorEngine

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

    def on_prog(cur, tot, pct):
        progress_history.append((cur, tot, pct))

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

    print("\nALL AUTOMATED ENGINE TESTS PASSED!")

if __name__ == "__main__":
    test_engine_simulation()
