# services/ingest/tests/eval/test_classifier.py
"""
Test suite verifying status classification for agent 3x evaluation runs.
Guarantees timeouts and empty responses are properly isolated as ERROR
instead of being falsely classified as logical FAILED.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure services/ingest is in sys.path
services_dir = Path(__file__).resolve().parents[2]
if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))

from tests.eval.run_golden import classify_agent_runs


def test_classify_all_passed():
    runs: List[Dict[str, Any]] = [
        {"status": "PASSED"},
        {"status": "PASSED"},
        {"status": "PASSED"},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "PASSED"
    assert reason == ""


def test_classify_h02_timeout_is_error():
    # H02: Passed run 1, timed out in runs 2 and 3
    runs: List[Dict[str, Any]] = [
        {"status": "PASSED"},
        {"status": "ERROR", "error": "Timeout expired after 120s"},
        {"status": "ERROR", "error": "Timeout expired after 120s"},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "ERROR"
    assert "Timeout expired after 120s" in reason
    assert "2/3 rodadas" in reason


def test_classify_n04_single_timeout_is_error():
    # N04: Abstained in runs 1 and 3, timed out in run 2
    runs: List[Dict[str, Any]] = [
        {"status": "PASSED"},
        {"status": "ERROR", "error": "LLM call timed out after 30000ms"},
        {"status": "PASSED"},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "ERROR"
    assert "timed out after 30000ms" in reason
    assert "1/3 rodadas" in reason


def test_classify_n03_empty_response_is_error():
    # N03: Abstained in runs 1 and 3, returned empty response in run 2
    runs: List[Dict[str, Any]] = [
        {"status": "PASSED"},
        {"status": "ERROR", "error": "Empty final response from agent"},
        {"status": "PASSED"},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "ERROR"
    assert "Empty final response from agent" in reason


def test_classify_h03_logical_failure_is_failed():
    # H03: Omitted The Doppler Effect in all 3 runs (0 errors)
    runs: List[Dict[str, Any]] = [
        {"status": "FAILED", "reasons": ["Missing expected trophies: The Doppler Effect"]},
        {"status": "FAILED", "reasons": ["Missing expected trophies: The Doppler Effect"]},
        {"status": "FAILED", "reasons": ["Missing expected trophies: The Doppler Effect"]},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "FAILED"
    assert "The Doppler Effect" in reason
    assert "0/3 tentativas" in reason


def test_classify_mixed_pass_and_fail_without_error_is_failed():
    # 2 passes, 1 logical fail (no timeout/network error)
    runs: List[Dict[str, Any]] = [
        {"status": "PASSED"},
        {"status": "PASSED"},
        {"status": "FAILED", "reasons": ["RAG Triad low score: Faithfulness=0.65"]},
    ]
    status, reason = classify_agent_runs(runs)
    assert status == "FAILED"
    assert "2/3 tentativas" in reason
