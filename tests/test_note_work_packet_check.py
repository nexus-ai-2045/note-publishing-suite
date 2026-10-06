from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/note_work_packet_check.py"


def run_check(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def valid_packet() -> dict[str, object]:
    return {
        "schema_version": "note-work-packet/v1",
        "task_id": "note-magazine-a1",
        "parent_task_id": "note-orchestrator",
        "meta_label": "note",
        "fde_label": "content-operations",
        "owner": "note-editor-prepublish",
        "chain_from": "note-editor-prepublish",
        "return_to": "note-orchestrator",
        "objective": "マガジン対象を確認する",
        "input": ["draft-url"],
        "expected_output": ["観測結果"],
        "done_when": ["対象と結果を記録する"],
        "stop_when": ["対象不明なら停止する"],
        "status": "collected",
        "evidence": ["observation.json"],
        "residual": [],
        "next_action": "親へ返却する",
    }


def test_valid_packet_passes(tmp_path: Path):
    evidence = tmp_path / "observation.json"
    evidence.write_text("{}", encoding="utf-8")
    packet_data = valid_packet()
    packet_data["evidence_paths"] = [str(evidence)]
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(packet_data), encoding="utf-8")
    result = run_check(packet)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["residual_work_zero"] is True


def test_closed_packet_without_evidence_fails(tmp_path: Path):
    data = valid_packet()
    data.update(status="closed", evidence=[])
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(data), encoding="utf-8")
    result = run_check(packet)
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert "accepted/closed packet requires evidence" in payload["stop_causes"]


def test_unknown_packet_requires_return_action(tmp_path: Path):
    data = valid_packet()
    data.update(status="unknown", next_action="")
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(data), encoding="utf-8")
    result = run_check(packet)
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert "next_action must be present and non-empty" in payload["stop_causes"]


def test_missing_evidence_path_fails_closed(tmp_path: Path):
    data = valid_packet()
    data["evidence_paths"] = [str(tmp_path / "missing.json")]
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(data), encoding="utf-8")
    result = run_check(packet)
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert "evidence path does not exist" in payload["stop_causes"][0]
