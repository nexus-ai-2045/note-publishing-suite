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


def test_required_fields_reject_invalid_types(tmp_path):
    for field in ("task_id", "owner", "input", "expected_output", "done_when", "stop_when", "status", "evidence", "residual"):
        for value in (False, {}, [False], "   "):
            data = valid_packet()
            data[field] = value
            packet = tmp_path / "packet.json"
            packet.write_text(json.dumps(data), encoding="utf-8")
            result = run_check(packet)
            assert result.returncode == 1, (field, value, result.stdout)
            assert json.loads(result.stdout)["ok"] is False


def test_unhashable_status_fails_closed(tmp_path):
    data = valid_packet()
    data["status"] = []
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(data), encoding="utf-8")
    result = run_check(packet)
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_text_output_reports_remaining_work(tmp_path):
    data = valid_packet()
    data["residual"] = ["人間レビュー"]
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(packet)], text=True, capture_output=True)
    assert result.returncode == 0
    assert "residual_work_zero=false" in result.stdout


def test_required_postpublication_cannot_close_with_missing_review_or_measurement(tmp_path):
    review = tmp_path / 'review.json'
    metric = tmp_path / 'metric.json'
    review.write_text(json.dumps({'postpublication_complete': True, 'published_entry': {'note_id': 'n123'}}))
    metric.write_text(json.dumps({'status': 'observed', 'registered_note_ids': ['n123'], 'continuous_collection_status': 'ok'}))
    packet = valid_packet()
    packet['status'] = 'closed'
    packet['postpublication'] = {'required': True, 'note_ids': ['n123'], 'review_receipts': [str(review)],
        'measurement_receipt': str(metric), 'continuous_measurement_required': True}
    path = tmp_path / 'packet.json'
    path.write_text(json.dumps(packet))
    assert run_check(path).returncode == 0
    review.write_text(json.dumps({'postpublication_complete': False, 'published_entry': {'note_id': 'n123'}}))
    assert run_check(path).returncode != 0
    review.write_text(json.dumps({'postpublication_complete': True, 'published_entry': {'note_id': 'n123'}}))
    metric.write_text(json.dumps({'status': 'observed', 'registered_note_ids': ['nother'], 'continuous_collection_status': 'ok'}))
    assert run_check(path).returncode != 0
    metric.unlink()
    assert run_check(path).returncode != 0


def test_postpublication_receipt_shapes_fail_closed_with_json_diagnostics(tmp_path):
    cases = [
        ('review', [], '公開後点検receiptはJSONオブジェクト'),
        ('review', None, '公開後点検receiptはJSONオブジェクト'),
        ('published_entry', [], 'published_entryはJSONオブジェクト'),
        ('published_entry', None, 'published_entryはJSONオブジェクト'),
        ('measurement', [], '計測receiptはJSONオブジェクト'),
        ('measurement', None, '計測receiptはJSONオブジェクト'),
        ('note_id', [], 'note_idが不足または不正'),
        ('registered_note_ids', None, '公開後点検と計測登録の対象が一致しません'),
        ('registered_note_ids', [{}], '公開後点検と計測登録の対象が一致しません'),
    ]
    for field, value, diagnostic in cases:
        reviewed = {'postpublication_complete': True, 'published_entry': {'note_id': 'n123'}}
        measured = {'status': 'observed', 'registered_note_ids': ['n123'], 'continuous_collection_status': 'ok'}
        if field == 'review':
            reviewed = value
        elif field == 'published_entry':
            reviewed['published_entry'] = value
        elif field == 'note_id':
            reviewed['published_entry']['note_id'] = value
        elif field == 'measurement':
            measured = value
        else:
            measured[field] = value
        review = tmp_path / 'review.json'
        metric = tmp_path / 'metric.json'
        review.write_text(json.dumps(reviewed))
        metric.write_text(json.dumps(measured))
        packet = valid_packet()
        packet.update(status='closed', postpublication={
            'required': True, 'note_ids': ['n123'], 'review_receipts': [str(review)],
            'measurement_receipt': str(metric), 'continuous_measurement_required': True})
        path = tmp_path / 'packet.json'
        path.write_text(json.dumps(packet))
        result = run_check(path)
        assert result.returncode == 1, (field, value, result.stdout, result.stderr)
        payload = json.loads(result.stdout)
        assert payload['ok'] is False
        assert any(diagnostic in cause for cause in payload['stop_causes']), payload
        assert 'Traceback' not in result.stderr
