#!/usr/bin/env python3
"""topic_status_check の契約テスト。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_topic_status_check_passes_on_package_ledger():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/topic_status_check.py"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["residual_work_zero"] is True
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []
    assert set(payload["axes_required"]) == {
        "axis-1",
        "axis-2",
        "axis-3",
        "axis-4",
        "axis-5",
        "axis-6",
    }


def test_ledger_marks_fixture_todo_as_non_product():
    text = (ROOT / "references/topic-consolidation-ledger.md").read_text(
        encoding="utf-8"
    )
    assert "fixture" in text
    assert "製品残務ではない" in text
    assert "SAFE_REMOVE_CANDIDATE" in text
