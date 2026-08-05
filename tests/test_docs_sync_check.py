from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    name = "docs_sync_check"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/docs_sync_check.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_contract_is_embedded_and_valid():
    module = load_module()
    contract = module.load_contract(ROOT / "package.yaml")
    assert contract["version"] == 1
    assert contract["generated"][0]["output"] == "README.rendered.html"


def test_generated_readme_is_in_sync_without_repository_write():
    module = load_module()
    before = (ROOT / "README.rendered.html").read_bytes()
    issues, patch = module.check_generated(
        ROOT, module.load_contract(ROOT / "package.yaml")
    )
    after = (ROOT / "README.rendered.html").read_bytes()
    assert issues == []
    assert patch == ""
    assert after == before


def test_generated_readme_drift_produces_patch(tmp_path: Path):
    module = load_module()
    (tmp_path / "scripts").mkdir()
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    shutil.copy2(ROOT / "scripts/render_readme.py", tmp_path / "scripts/render_readme.py")
    (tmp_path / "README.rendered.html").write_text("stale\n", encoding="utf-8")
    contract = {
        "generated": [
            {
                "source": "README.md",
                "output": "README.rendered.html",
                "renderer": "scripts/render_readme.py",
            }
        ]
    }
    issues, patch = module.check_generated(tmp_path, contract)
    assert issues == [{"code": "generated_drift", "path": "README.rendered.html"}]
    assert "--- a/README.rendered.html" in patch
    assert "+++ b/README.rendered.html" in patch


def test_missing_document_review_is_detected():
    module = load_module()
    contract = {
        "path_rules": [
            {"patterns": ["scripts/**"], "docs": ["README.md", "CHANGELOG.md"]}
        ]
    }
    issues = module.check_handwritten_docs({"scripts/new.py"}, contract, "")
    assert issues[0]["code"] == "missing_doc_review"


def test_specific_no_update_reason_satisfies_review():
    module = load_module()
    contract = {
        "path_rules": [
            {"patterns": ["scripts/**"], "docs": ["README.md", "CHANGELOG.md"]}
        ]
    }
    review = "ドキュメント同期:\n- [x] 更新不要。理由: 内部テストだけの変更で利用方法は変わらない"
    assert module.check_handwritten_docs({"scripts/test_only.py"}, contract, review) == []


def test_actual_document_change_satisfies_review_without_reason():
    module = load_module()
    contract = {
        "path_rules": [
            {"patterns": ["scripts/**"], "docs": ["README.md", "CHANGELOG.md"]}
        ]
    }
    changed = {"scripts/new.py", "CHANGELOG.md"}
    assert module.check_handwritten_docs(changed, contract, "") == []


def test_missing_required_document_is_detected(tmp_path: Path):
    module = load_module()
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    contract = {"required_docs": ["README.md", "SECURITY.md"]}
    assert module.check_required_docs(tmp_path, contract) == [
        {"code": "missing_required_doc", "path": "SECURITY.md"}
    ]


def test_placeholder_reason_is_rejected():
    module = load_module()
    assert module.no_update_reason("- [x] 更新不要。理由: <1行>") is None


def test_contract_invalid_when_manifest_is_missing(tmp_path: Path):
    module = load_module()
    package = tmp_path / "package.yaml"
    package.write_text("name: fixture\n", encoding="utf-8")
    try:
        module.load_contract(package)
    except module.ContractError as exc:
        assert "missing docs_sync_contract" in str(exc)
    else:
        raise AssertionError("ContractError was not raised")


def test_result_schema_is_json_serializable():
    result = {
        "ok": False,
        "state": "generated_drift",
        "issues": [{"code": "generated_drift", "path": "README.rendered.html"}],
        "repository_modified": False,
    }
    assert json.loads(json.dumps(result))["state"] == "generated_drift"
