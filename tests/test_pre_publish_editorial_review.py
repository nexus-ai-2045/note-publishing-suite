from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pre_publish_check.py"
SPEC = importlib.util.spec_from_file_location("nps_pre_publish_check_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


ARTICLE = "n1a7ad7c01e80"
CONVERSATION = "conversation-current"
TEXT = "# 記事\n\n結論を後半で明かす構成を保持する本文です。\n"


def receipt(text: str = TEXT, **changes: object) -> dict[str, object]:
    _, body = check.split_frontmatter(text)
    value: dict[str, object] = {
        "schema_version": check.EDITORIAL_REVIEW_SCHEMA,
        "article_id": ARTICLE,
        "conversation_id": CONVERSATION,
        "status": "review_required",
        "actor": "user",
        "draft_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "issue_codes": ["missing_early_takeaway"],
        "reason": "本人が物語構成として先出しを不採用",
        "evidence_ref": "runtime://current-human-receipt",
        "observed_at": "2026-10-06T17:00:00+09:00",
    }
    value.update(changes)
    return value


def apply(tmp_path: Path, text: str = TEXT, value: dict[str, object] | None = None):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(value or receipt(text), ensure_ascii=False), encoding="utf-8")
    return check.apply_editorial_review(
        check.collect_issues(text), path, text,
        article_id=ARTICLE, conversation_id=CONVERSATION,
    )


def test_without_receipt_keeps_inspection_error():
    issues = check.apply_editorial_review(
        check.collect_issues(TEXT), None, TEXT,
        article_id=ARTICLE, conversation_id=CONVERSATION,
    )
    assert any(i["code"] == "missing_early_takeaway" and i["severity"] == "error" for i in issues)


def test_valid_receipt_marks_only_editorial_issue_review_required(tmp_path: Path):
    issues = apply(tmp_path)
    assert any(i["code"] == "missing_early_takeaway" and i["severity"] == "review_required" for i in issues)
    assert not any(i["code"] == "invalid_editorial_review_receipt" for i in issues)


@pytest.mark.parametrize("changes", [
    {"draft_sha256": "0" * 64},
    {"body_sha256": "1" * 64},
    {"article_id": "other"},
    {"conversation_id": "old"},
    {"reason": ""},
    {"evidence_ref": ""},
    {"observed_at": "2026-10-06T17:00:00"},
])
def test_invalid_binding_or_receipt_metadata_stays_error(tmp_path: Path, changes: dict[str, object]):
    issues = apply(tmp_path, value=receipt(**changes))
    assert any(i["code"] == "invalid_editorial_review_receipt" and i["severity"] == "error" for i in issues)
    assert not any(i["code"] == "missing_early_takeaway" and i["severity"] == "review_required" for i in issues)


def test_issue_scope_cannot_release_another_error(tmp_path: Path):
    text = TEXT + "\nsk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
    issues = apply(tmp_path, text=text, value=receipt(text, issue_codes=["missing_early_takeaway", "secret_like_value"]))
    assert any(i["code"] == "invalid_editorial_review_receipt" for i in issues)
    assert any(i["code"] == "secret_like_value" and i["severity"] == "error" for i in issues)


def test_secret_error_remains_when_receipt_is_valid(tmp_path: Path):
    text = TEXT + "\nsk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
    issues = apply(tmp_path, text=text)
    assert any(i["code"] == "secret_like_value" and i["severity"] == "error" for i in issues)
    assert any(i["code"] == "missing_early_takeaway" and i["severity"] == "review_required" for i in issues)


def test_duplicate_json_key_and_nan_are_rejected(tmp_path: Path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"reason":"a","reason":"b"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        check.load_editorial_review_receipt(duplicate)
    nan = tmp_path / "nan.json"
    nan.write_text('{"observed_at":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="constant"):
        check.load_editorial_review_receipt(nan)


def test_cli_review_required_keeps_exit_one(tmp_path: Path):
    path = tmp_path / "draft.md"
    path.write_text(TEXT, encoding="utf-8")
    receipt_path = tmp_path / "review.json"
    receipt_path.write_text(json.dumps(receipt()), encoding="utf-8")
    command = [
        sys.executable, str(Path(check.__file__)), str(path), "--json",
        "--article-id", ARTICLE, "--conversation-id", CONVERSATION,
        "--prepublish-review-receipt", str(receipt_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["overall"] == "review_required"


def test_cli_secret_remains_error_exit_one(tmp_path: Path):
    text = TEXT + "\nsk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
    path = tmp_path / "secret-draft.md"
    path.write_text(text, encoding="utf-8")
    receipt_path = tmp_path / "review-secret.json"
    receipt_path.write_text(json.dumps(receipt(text)), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, str(Path(check.__file__)), str(path), "--json",
            "--article-id", ARTICLE, "--conversation-id", CONVERSATION,
            "--prepublish-review-receipt", str(receipt_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["overall"] == "error"
    assert any(issue["code"] == "secret_like_value" and issue["severity"] == "error" for issue in payload["issues"])
