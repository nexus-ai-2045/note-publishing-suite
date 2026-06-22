#!/usr/bin/env python3
"""Package contract tests for note-publishing-suite."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_render_readme_module():
    spec = importlib.util.spec_from_file_location(
        "render_readme", ROOT / "scripts" / "render_readme.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_github_identity_guard_module():
    spec = importlib.util.spec_from_file_location(
        "github_identity_guard", ROOT / "scripts" / "github_identity_guard.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_provenance_leak_check_module():
    module_name = "provenance_leak_check"
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "scripts" / "provenance_leak_check.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_required_files_exist():
    required = [
        "SKILL.md",
        "package.yaml",
        "README.md",
        "CHANGELOG.md",
        "PUBLIC_RELEASE_CHECKLIST.md",
        "issue-drafts.md",
        "issue-packet.json",
        "references/note-editor-capability-inventory.md",
        "references/note-editor-pdca-orchestration.md",
        "references/note-article-provenance-design.md",
        "references/note-editor-live-constraint-boundaries.md",
        "references/note-image-upload-automation-boundary.md",
        "skills/note-idea-intake/SKILL.md",
        "skills/note-draft-production/SKILL.md",
        "skills/note-prepublish-qa/SKILL.md",
        "skills/note-editor-prepublish/SKILL.md",
        "skills/note-editor-ops/SKILL.md",
        "skills/note-official-guidance-intake/SKILL.md",
        "skills/note-editor-constraint-debug/SKILL.md",
        "skills/note-publication-gate/SKILL.md",
        "skills/note-postpublish-ledger/SKILL.md",
        "scripts/note_preview.py",
        "scripts/pre_publish_check.py",
        "scripts/note_fact_check.py",
        "scripts/note_diff_check.py",
        "scripts/fetch_note_body.js",
        "scripts/post_publish.py",
        "scripts/engagement_tracker.py",
        "scripts/render_readme.py",
        "scripts/provenance_leak_check.py",
        "scripts/provenance_label_check.py",
        "scripts/github_identity_guard.py",
        "scripts/japanese_closeout_language_check.py",
        "scripts/note_image_upload_boundary_check.py",
        "scripts/note_editor_prepublish_verify.py",
        "scripts/review_draft.py",
        "scripts/run_local_draft_qa_proof.py",
        "scripts/bump_package_version.py",
        "scripts/check_version_bump.py",
        "scripts/verify_public_package.sh",
        "tests/test_review_draft_cli.py",
        "data/note_editor_prepublish_observation.fixture.json",
        "data/github_identity_guard_policy.example.json",
        "data/note_drafts.json",
        "data/published_notes.json",
        "content/drafts/sample-note-prepublish-fixture.md",
        "content/drafts/caramel-provenance-label-fixture.md",
    ]
    missing = [item for item in required if not (ROOT / item).exists()]
    assert not missing


def test_public_package_version_is_current_commit_target():
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    package_version_match = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", package, re.MULTILINE)
    assert package_version_match
    package_version = package_version_match.group(1)
    assert f"パッケージ版: `{package_version}`" in readme
    assert f"## {package_version}" in changelog
    assert "changelog: CHANGELOG.md" in package
    assert changelog.index(f"## {package_version}") < changelog.index("## 0.2.0")
    assert "verify:local" in readme


def test_verifier_runtime_requirements_are_honest():
    docs = {
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        "README.rendered.html": (ROOT / "README.rendered.html").read_text(
            encoding="utf-8"
        ),
        "PUBLIC_READY.md": (ROOT / "PUBLIC_READY.md").read_text(encoding="utf-8"),
    }
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")

    for name, text in docs.items():
        for claim in [
            "Python が無い",
            "Python を前提にせず",
            "Python を必須にせず",
        ]:
            assert claim not in text, name

    assert "POSIX sh、Python、git" in docs["README.md"]
    assert "この verifier は Python と git も" in docs["README.md"]
    assert "使って各 checker を実行する" in docs["README.md"]
    assert "requires:" in package
    assert "POSIX sh" in package
    assert "Python" in package
    assert "git" in package


def test_package_version_bump_guard_contract_present():
    script = (ROOT / "scripts/check_version_bump.py").read_text(encoding="utf-8")
    bump_script = (ROOT / "scripts/bump_package_version.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for needle in [
        "requires_version_bump",
        "VERSION_METADATA_FILES",
        "GITHUB_BASE_REF",
        "VERSION_BUMP_BASE_REF",
        "failed_package_changed_without_version_bump",
    ]:
        assert needle in script, needle
    assert "fetch-depth: 0" in workflow
    assert "python scripts/check_version_bump.py" in workflow
    assert "scripts/check_version_bump.py" in package
    for needle in [
        "bump_version",
        "README.rendered.html",
        "insert_changelog_section",
        "version_bump=ok",
    ]:
        assert needle in bump_script, needle
    assert "scripts/bump_package_version.py" in package
    assert "自動採番" in readme


def test_fetch_note_body_contract_present():
    script = (ROOT / "scripts/fetch_note_body.js").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for needle in [
        "loadPlaywright",
        "application/ld+json",
        "articleBody",
        "Playwright が見つかりません",
    ]:
        assert needle in script, needle
    assert "scripts/fetch_note_body.js" in package
    assert "scripts/fetch_note_body.js" in readme


def test_render_readme_supports_roadmap_table():
    render_readme = load_render_readme_module()
    html = render_readme.render(
        "# Roadmap\n\n"
        "| lane | purpose |\n"
        "| --- | --- |\n"
        "| Product / UX | readable flow |\n"
        "| Creative production / distribution | reviewable assets |\n"
    )

    assert '<div class="table-wrap"><table>' in html
    assert "<th>lane</th>" in html
    assert "<td>Product / UX</td>" in html
    assert "<td>Creative production / distribution</td>" in html


def test_publication_gate_contract_present():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    assert "human_review_required: true" in package
    assert "explicit_current_conversation_approval_required: true" in package
    assert "公開ボタン、投稿ボタン、予約確定ボタンを押す手前で停止" in skill


def test_public_release_checklist_matches_current_public_gate():
    checklist = (ROOT / "PUBLIC_RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    for needle in [
        "python -m pytest scripts/test_skill_integration.py tests -q",
        "tests/test_review_draft_cli.py",
        "python scripts/note_image_upload_boundary_check.py --json",
        "sh scripts/verify_public_package.sh",
        "リポジトリ公開範囲",
        "Note 公開、予約投稿、SNS 共有、外部告知",
    ]:
        assert needle in checklist, needle


def test_note_editor_embed_contract_present():
    docs = {
        "editor_skill": (
            ROOT / "skills/note-editor-prepublish/SKILL.md"
        ).read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "issue_drafts": (ROOT / "issue-drafts.md").read_text(encoding="utf-8"),
    }

    for name, text in docs.items():
        assert "単独行" in text, name
        assert "Enter" in text, name
        assert "手動境界" in text, name


def test_note_editor_dynamic_ui_contract_present():
    skill = (ROOT / "skills/note-editor-prepublish/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "動的" in skill
    assert "固定座標" in skill
    assert "DOM" in skill
    assert "ラベル" in skill
    assert "Undo" in skill
    assert "同期しない" in skill


def test_note_editor_ops_autofire_and_function_contract_present():
    parent = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    editor = (ROOT / "skills/note-editor-prepublish/SKILL.md").read_text(
        encoding="utf-8"
    )
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
        encoding="utf-8"
    )

    for name, text in {
        "parent": parent,
        "package": package,
        "readme": readme,
        "editor": editor,
    }.items():
        assert "note-editor-ops" in text, name

    for needle in [
        "自動発火",
        "Browser attach",
        "Publication gate",
        "Link card embed",
        "DOM verification",
        "Undo recovery",
        "Local checker ratchet",
        "Post-publish ledger",
        "単独行",
        "Enter",
        "figure",
        "data-src",
        "href",
        "固定座標",
        "同期しない",
        "手動境界",
        "published_notes",
        "note_drafts",
    ]:
        assert needle in ops, needle


def test_note_editor_capability_inventory_contract_present():
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
        encoding="utf-8"
    )
    inventory = (
        ROOT / "references/note-editor-capability-inventory.md"
    ).read_text(encoding="utf-8")

    for name, text in {
        "package": package,
        "readme": readme,
        "ops": ops,
    }.items():
        assert "note-editor-capability-inventory.md" in text, name

    for needle in [
        "公式ソース",
        "足りていない棚卸し",
        "画面サイズ / responsive 軸",
        "カーソル / selection 軸",
        "Browser surface 軸",
        "AI surface 軸",
        "推奨環境",
        "埋め込み",
        "viewport size",
        "scroll position",
        "cursor",
        "selection",
        "DOM 構造",
        "固定 selector",
        "nth-child",
        "候補要素",
        "再列挙",
        "overflow menu",
        "DOM path",
        "in-app Browser",
        "Chrome extension",
        "Codex main",
        "Spark",
        "human supervised",
    ]:
        assert needle in inventory, needle


def test_official_guidance_source_registry_contract_present():
    inventory = (
        ROOT / "references/note-editor-capability-inventory.md"
    ).read_text(encoding="utf-8")
    official = (
        ROOT / "skills/note-official-guidance-intake/SKILL.md"
    ).read_text(encoding="utf-8")
    editor = (
        ROOT / "skills/note-editor-prepublish/SKILL.md"
    ).read_text(encoding="utf-8")
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
        encoding="utf-8"
    )
    draft = (ROOT / "skills/note-draft-production/SKILL.md").read_text(
        encoding="utf-8"
    )
    gate = (ROOT / "skills/note-publication-gate/SKILL.md").read_text(
        encoding="utf-8"
    )

    for needle in [
        "last_official_guidance_intake: 2026-06-16",
        "https://www.help-note.com/hc/ja/articles/360008947573",
        "https://www.help-note.com/hc/ja/articles/360019596133",
        "https://www.help-note.com/hc/ja/articles/360017021253",
        "https://www.help-note.com/hc/ja/articles/360011358913",
        "https://note.com/info/n/n7b62e94e08c8",
        "https://note.com/info/n/n10cb85ca3ca8",
        "confirmed_on",
        "公式未確認 / local policy",
        "固定時刻",
        "公式扱いしない",
        "local observation",
        "needs measurement",
    ]:
        assert needle in inventory, needle

    for needle in [
        "公式扱いの最低条件",
        "source URL",
        "confirmed_on",
        "公式ソースが固定時刻を示していない場合",
        "DOM selector",
        "local checker",
    ]:
        assert needle in official, needle

    for name, text in {
        "editor": editor,
        "ops": ops,
    }.items():
        for needle in [
            "公式ヘルプ",
            "local policy",
            "DOM 判定",
            "公式ヘルプの記述として扱わない",
        ]:
            assert needle in text, name

    for needle in [
        "公式ソースで確認済み",
        "local policy",
        "local observation",
        "公式推奨としては扱わない",
    ]:
        assert needle in draft, needle

    for needle in [
        "固定の「おすすめ公開時刻」は公式未確認",
        "公式メンテナンス告知",
    ]:
        assert needle in gate, needle


def test_note_editor_pdca_orchestration_contract_present():
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
        encoding="utf-8"
    )
    pdca = (ROOT / "references/note-editor-pdca-orchestration.md").read_text(
        encoding="utf-8"
    )

    for name, text in {
        "package": package,
        "readme": readme,
        "ops": ops,
    }.items():
        assert "note-editor-pdca-orchestration.md" in text, name

    for needle in [
        "Goal",
        "Plan",
        "Do",
        "Check",
        "Act",
        "1 cycle",
        "1 action",
        "work packet",
        "attach",
        "viewport map",
        "cursor prep",
        "embed one URL",
        "footer sweep",
        "publish gate",
        "Spark / worker",
        "read-only",
        "Main agent",
        "公開 gate",
        "Undo",
        "stopline",
    ]:
        assert needle in pdca, needle


def test_note_editor_live_constraint_boundaries_contract_present():
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    parent = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    constraints = (
        ROOT / "skills/note-editor-constraint-debug/SKILL.md"
    ).read_text(encoding="utf-8")
    ops = (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
        encoding="utf-8"
    )
    inventory = (
        ROOT / "references/note-editor-capability-inventory.md"
    ).read_text(encoding="utf-8")
    boundaries = (
        ROOT / "references/note-editor-live-constraint-boundaries.md"
    ).read_text(encoding="utf-8")

    for name, text in {
        "package": package,
        "parent": parent,
        "readme": readme,
        "constraints": constraints,
        "ops": ops,
        "inventory": inventory,
    }.items():
        assert "note-editor-live-constraint-boundaries.md" in text, name

    for needle in [
        "figure[data-src]",
        "iframe.note-embed",
        "table-of-contents",
        "toc",
        "H2",
        "H3",
        "Shift+Enter",
        "<br>",
        "Control+Z",
        "復旧を保証しない",
        "公開、投稿、予約確定、SNS 共有",
    ]:
        assert needle in boundaries, needle


def test_note_article_provenance_design_contract_present():
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    parent = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    draft_skill = (
        ROOT / "skills/note-draft-production/SKILL.md"
    ).read_text(encoding="utf-8")
    editor_skill = (
        ROOT / "skills/note-editor-prepublish/SKILL.md"
    ).read_text(encoding="utf-8")
    design = (
        ROOT / "references/note-article-provenance-design.md"
    ).read_text(encoding="utf-8")
    fixture_draft = (
        ROOT / "content/drafts/sample-note-prepublish-fixture.md"
    ).read_text(encoding="utf-8")

    for name, text in {
        "package": package,
        "parent": parent,
        "readme": readme,
        "draft_skill": draft_skill,
        "editor_skill": editor_skill,
    }.items():
        assert "note-article-provenance-design.md" in text, name

    for needle in [
        "production_candidate",
        "exploratory_draft",
        "editor_fixture",
        "continuation_article",
        "source_pack",
        "source_database",
        "series_plot",
        "article_plot",
        "skeleton",
        "wall_bang",
        "stance_brief",
        "source_mode",
        "based_on",
        "allowed_use",
        "not_allowed",
        "editor_test_allowed",
        "plot / skeleton は evidence ではない",
        "ファクト抽出はここを優先する",
        "事実断定の根拠にしない",
    ]:
        assert needle in design, needle

    for needle in [
        "article_lane: editor_fixture",
        "source_mode: fixture_only",
        "based_on:",
        "allowed_use:",
        "not_allowed:",
        "editor_test_allowed: true",
        "Note editor 操作検証",
        "公開候補扱い",
    ]:
        assert needle in fixture_draft, needle


def test_provenance_leak_checker_contract_present():
    script = (ROOT / "scripts/provenance_leak_check.py").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (
        ROOT / "data/provenance_leak_policy.example.json"
    ).read_text(encoding="utf-8")

    for needle in [
        "provenance_leak_policy.local.json",
        "denylist",
        "windows_user_path",
        "posix_user_path",
        "git_prompt_artifact",
        "runtime_memory_label",
        "external_actions_performed",
        "publication_actions_performed",
    ]:
        assert needle in script, needle

    for needle in [
        "scripts/provenance_leak_check.py --scope changed",
        "data/provenance_leak_policy.local.json",
        "公開パッケージへ直書きしない",
    ]:
        assert needle in readme, needle

    assert "scripts/provenance_leak_check.py" in package
    assert "data/provenance_leak_policy.local.json" in gitignore
    assert "example-owner/private-repo" in example

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/provenance_leak_check.py"),
            "--scope",
            "all",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout


def test_provenance_leak_changed_files_resolves_monorepo_paths(monkeypatch, tmp_path: Path):
    module = load_provenance_leak_check_module()
    git_root = tmp_path / "repo"
    package_root = git_root / "public" / "note-publishing-suite"
    changed = package_root / "README.md"
    changed.parent.mkdir(parents=True)
    changed.write_text("# changed\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", package_root)

    class Result:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = 0

    def fake_run(args, **_kwargs):
        if args[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return Result(str(git_root))
        if args[:3] == ["git", "diff", "--name-only"]:
            return Result("public/note-publishing-suite/README.md\n")
        raise AssertionError(args)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.git_changed_files() == [changed]


def test_provenance_label_checker_contract_present(tmp_path: Path):
    script = (ROOT / "scripts/provenance_label_check.py").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    design = (
        ROOT / "references/note-article-provenance-design.md"
    ).read_text(encoding="utf-8")

    for needle in [
        "source_pack_locked_with_user_speech_priority",
        "user-said",
        "external-fact",
        "assistant-organized",
        "hold",
        "source_hint_mismatch",
        "external_actions_performed",
        "publication_actions_performed",
    ]:
        assert needle in script, needle

    for name, text in {
        "readme": readme,
        "package": package,
        "design": design,
    }.items():
        assert "scripts/provenance_label_check.py" in text, name
        assert "source_pack_locked_with_user_speech_priority" in text, name

    clean = ROOT / "content/drafts/caramel-provenance-label-fixture.md"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/provenance_label_check.py"),
            str(clean),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["labels_seen"] == [
        "assistant-organized",
        "external-fact",
        "hold",
        "user-said",
    ]

    broken = tmp_path / "broken-provenance.md"
    broken.write_text(
        "---\n"
        "title: broken\n"
        "source_mode: source_pack_locked_with_user_speech_priority\n"
        "---\n\n"
        "<!-- provenance-label: external-fact; source: user_speech_notes -->\n"
        "# Caramel 完全解説\n\n"
        "ユーザー曰く、この仕様は確定している。\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/provenance_label_check.py"),
            str(broken),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 1
    assert "source_hint_mismatch" in result.stdout
    assert "user_speech_inside_external_fact" in result.stdout


def test_github_identity_guard_contract_present():
    script = (ROOT / "scripts/github_identity_guard.py").read_text(
        encoding="utf-8"
    )
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (
        ROOT / "data/github_identity_guard_policy.example.json"
    ).read_text(encoding="utf-8")

    for needle in [
        "EXPECTED_REPOSITORY",
        "nexus-ai-2045/note-publishing-suite",
        "EXPECTED_GIT_NAME",
        "nexus_ai",
        "EXPECTED_GIT_EMAIL",
        "nexus.ai.2045@gmail.com",
        "ALLOWED_GITHUB_COMMITTER",
        "noreply@github.com",
        "DEFAULT_LOCAL_POLICY",
        "github_identity_guard_policy.local.json",
        "load_local_policy",
        "forbidden_accounts",
        "forbidden_emails",
        "forbidden_terms",
        "allowed_paths",
        "check_head_identity",
        "check_remote",
        "check_forbidden_text",
        "external_actions_performed",
        "publication_actions_performed",
    ]:
        assert needle in script, needle

    assert "scripts/github_identity_guard.py" in package
    assert "data/github_identity_guard_policy.example.json" in package
    assert "data/github_identity_guard_policy.local.json" in gitignore
    assert "example-private-account" in example
    assert "Run GitHub identity guard" in workflow

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/github_identity_guard.py"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout
    assert "local_identity_policy_loaded" in result.stdout
    assert "forbidden_identity_term_count" in result.stdout


def test_local_identity_policy_is_ignored_and_not_tracked():
    policy = "data/github_identity_guard_policy.local.json"

    ignored = subprocess.run(
        ["git", "check-ignore", policy],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert ignored.returncode == 0, ignored.stdout + ignored.stderr

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", policy],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert tracked.returncode != 0, tracked.stdout + tracked.stderr


def copy_public_package_fixture(destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name in {".git", ".pytest_cache", "__pycache__"}
            or name.endswith(".pyc")
            or name in {
                "github_identity_guard_policy.local.json",
                "provenance_leak_policy.local.json",
            }
        }

    shutil.copytree(ROOT, destination, ignore=ignore)


def run_git(cwd: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def initialize_standalone_public_repo_fixture(path: Path, message: str) -> None:
    run_git(path, "init")
    run_git(path, "checkout", "-B", "main")
    run_git(path, "config", "--local", "user.name", "nexus_ai")
    run_git(path, "config", "--local", "user.email", "nexus.ai.2045@gmail.com")
    run_git(
        path,
        "remote",
        "add",
        "origin",
        "https://github.com/nexus-ai-2045/note-publishing-suite.git",
    )
    run_git(path, "add", "-A")
    run_git(path, "commit", "-m", message)


def run_identity_guard(cwd: Path, env: dict[str, str] | None = None) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "scripts/github_identity_guard.py", "--json"],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_github_identity_guard_embedded_and_standalone_clone_lanes(tmp_path: Path):
    standalone = tmp_path / "note-publishing-suite-standalone"
    copy_public_package_fixture(standalone)
    initialize_standalone_public_repo_fixture(
        standalone,
        "standalone clone verification fixture",
    )

    standalone_env = {
        **os.environ,
        "GITHUB_REPOSITORY": "nexus-ai-2045/note-publishing-suite",
    }
    standalone_result = run_identity_guard(standalone, standalone_env)
    assert standalone_result["ok"] is True
    assert standalone_result["mode"] == "standalone_repository"
    assert standalone_result["external_actions_performed"] == []
    assert standalone_result["publication_actions_performed"] == []

    embedded_parent = tmp_path / "nexus_ai"
    embedded = embedded_parent / "public" / "note-publishing-suite"
    copy_public_package_fixture(embedded)
    run_git(embedded_parent, "init")

    embedded_result = run_identity_guard(embedded)
    assert embedded_result["ok"] is True
    assert embedded_result["mode"] == "embedded_copy_text_scan_only"
    assert embedded_result["external_actions_performed"] == []
    assert embedded_result["publication_actions_performed"] == []


def test_public_package_verifier_runs_from_standalone_clone_fixture(tmp_path: Path):
    standalone = tmp_path / "note-publishing-suite-verifier"
    copy_public_package_fixture(standalone)
    initialize_standalone_public_repo_fixture(
        standalone,
        "standalone verifier fixture",
    )

    env = {
        **os.environ,
        "NOTE_PUBLISHING_SUITE_STANDALONE_VERIFIER_DEPTH": "1",
    }
    if shutil.which("sh"):
        command = ["sh", "scripts/verify_public_package.sh", "--json"]
    else:
        command = [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/verify_public_package.ps1",
            "-Json",
        ]
    result = subprocess.run(
        command,
        cwd=standalone,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["verification_lanes"] == ["embedded_copy", "standalone_clone"]
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []


def test_github_identity_guard_local_policy_blocks_identity_leaks(tmp_path: Path):
    guard = load_github_identity_guard_module()
    policy = tmp_path / "github_identity_guard_policy.local.json"
    policy.write_text(
        """{
  "version": 1,
  "forbidden_accounts": ["fixture-private-account"],
  "forbidden_emails": ["fixture-private@example.invalid"],
  "forbidden_terms": ["fixture-private-identity-fragment"],
  "allowed_paths": []
}
""",
        encoding="utf-8",
    )
    leak = tmp_path / "identity-leak-fixture.txt"
    leak.write_text("fixture-private-account\n", encoding="utf-8")
    forbidden_terms, allowed_paths = guard.load_local_policy(policy)
    errors: list[dict[str, str]] = []
    original_iter_text_files = guard.iter_text_files
    guard.iter_text_files = lambda: [leak]
    try:
        guard.check_forbidden_text(errors, forbidden_terms, allowed_paths)
    finally:
        guard.iter_text_files = original_iter_text_files

    assert errors == [
        {
            "check": "text_scan",
            "message": f"{leak} contains forbidden identity term",
        }
    ]


def test_japanese_closeout_language_gate_contract_present():
    script = (ROOT / "scripts/japanese_closeout_language_check.py").read_text(
        encoding="utf-8"
    )
    parent = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    package = (ROOT / "package.yaml").read_text(encoding="utf-8")

    for needle in [
        "output_language_gate",
        "user_visible_language: japanese",
        "cli_status_translation_required: true",
        "japanese_closeout_language_gate",
    ]:
        assert needle in package, needle

    for needle in [
        "日本語完了報告ゲート",
        "ready for review",
        "下書き解除済み",
        "open PR",
        "未マージPR",
        "MERGED",
        "マージ済み",
        "mergeable",
        "マージ可能",
        "output_language_gate",
    ]:
        assert needle in parent, needle

    for needle in [
        "構造バグ",
        "出力ゲート",
        "下書き解除済み",
        "未マージPR",
        "マージ済み",
        "マージ可能",
        "コマンド、ファイルパス、URL、SHA",
    ]:
        assert needle in readme, needle

    for needle in [
        "REQUIRED_TERMS",
        "FORBIDDEN_RAW_STATUS_TERMS",
        "external_actions_performed",
        "publication_actions_performed",
    ]:
        assert needle in script, needle

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/japanese_closeout_language_check.py"),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"ok": true' in result.stdout


def test_guarantee_ratchet_contract_present():
    docs = {
        "parent_skill": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "editor_skill": (
            ROOT / "skills/note-editor-prepublish/SKILL.md"
        ).read_text(encoding="utf-8"),
    }

    assert "Guarantee Ratchet" in docs["parent_skill"]
    assert "保証ラチェット" in docs["readme"]
    assert "再発防止" in docs["parent_skill"]
    assert "contract test" in docs["parent_skill"]
    assert "検査器" in docs["readme"]
    assert "再発防止" in docs["editor_skill"]
    assert "Closeout Evidence" in docs["editor_skill"]


def test_note_image_upload_boundary_contract_present():
    docs = {
        "parent_skill": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "editor_skill": (
            ROOT / "skills/note-editor-prepublish/SKILL.md"
        ).read_text(encoding="utf-8"),
        "ops_skill": (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
            encoding="utf-8"
        ),
        "package": (ROOT / "package.yaml").read_text(encoding="utf-8"),
    }

    for name, text in docs.items():
        assert "note-image-upload-automation-boundary" in text, name
        assert "note_image_upload_boundary_check.py" in text, name


def test_practical_open_issues_are_skills():
    docs = {
        "parent_skill": (ROOT / "SKILL.md").read_text(encoding="utf-8"),
        "package": (ROOT / "package.yaml").read_text(encoding="utf-8"),
        "readme": (ROOT / "README.md").read_text(encoding="utf-8"),
        "official": (
            ROOT / "skills/note-official-guidance-intake/SKILL.md"
        ).read_text(encoding="utf-8"),
        "constraints": (
            ROOT / "skills/note-editor-constraint-debug/SKILL.md"
        ).read_text(encoding="utf-8"),
        "live_constraints": (
            ROOT / "references/note-editor-live-constraint-boundaries.md"
        ).read_text(encoding="utf-8"),
        "ops": (ROOT / "skills/note-editor-ops/SKILL.md").read_text(
            encoding="utf-8"
        ),
    }

    for name, text in docs.items():
        assert "note-official-guidance-intake" in text, name
        assert "note-editor-constraint-debug" in text, name

    for needle in [
        "一次情報",
        "公式ソース",
        "作文禁止",
        "references/note-editor-capability-inventory.md",
        "未確認を公式扱いしない",
        "公開 gate",
    ]:
        assert needle in docs["official"], needle

    for needle in [
        "埋め込み",
        "目次",
        "Shift+Enter",
        "実測",
        "再現手順",
        "手動境界",
        "note-editor-ops",
    ]:
        assert needle in docs["constraints"], needle

    for needle in [
        "publication_action: none",
        "local observation",
        "figure[data-src]",
        "iframe.note-embed",
        "table-of-contents",
        "toc",
        "H2",
        "H3",
        "Undo 復旧を guarantee しない",
    ]:
        assert needle in docs["live_constraints"], needle


def test_public_package_paths_are_repo_relative():
    docs = {
        "issue_drafts": (ROOT / "issue-drafts.md").read_text(encoding="utf-8"),
        "issue_packet": (ROOT / "issue-packet.json").read_text(encoding="utf-8"),
    }

    for name, text in docs.items():
        assert ".agents/skills/note-publishing-suite" not in text, name
        assert "SKILL.md" in text, name
        assert "package.yaml" in text, name
        assert "skills/*/SKILL.md" in text, name


def test_note_diff_check_has_public_url_guard():
    script = (ROOT / "scripts/note_diff_check.py").read_text(encoding="utf-8")

    for needle in [
        "validate_public_http_url",
        "unsupported_url_scheme",
        "local_host_blocked",
        "private_or_local_ip_blocked",
        "external_fetch_performed",
    ]:
        assert needle in script, needle


def test_public_safe_fixture_runs_through_qa_lane():
    draft = ROOT / "content/drafts/sample-note-prepublish-fixture.md"
    preview = draft.with_suffix(".preview.html")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/note_preview.py"), str(draft), "-o", str(preview)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert preview.exists()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pre_publish_check.py"), str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"overall": "warning"' in result.stdout

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/note_fact_check.py"), "local", str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    assert '"finding_count":' in result.stdout

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/note_diff_check.py"), "Unknown", str(draft), "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    assert '"overall": "skipped"' in result.stdout
    assert '"reason": "note_url_unknown"' in result.stdout


def test_local_draft_qa_proof_records_stop_before_publish(tmp_path):
    draft = ROOT / "content/drafts/sample-note-prepublish-fixture.md"
    evidence = tmp_path / "qa-proof.json"
    preview = tmp_path / "qa-proof.preview.html"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_local_draft_qa_proof.py"),
            str(draft),
            "--preview",
            str(preview),
            "--output",
            str(evidence),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert preview.exists()
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["overall"] == "stopped_before_publish"
    assert payload["qa_lane"] == "return_to_draft"
    assert payload["pre_publish_overall"] == "warning"
    assert payload["diff_check"]["overall"] == "skipped"
    assert "human_review_required" in payload["publication_gate"]["stop_causes"]
    assert payload["external_actions_performed"] == []
    assert payload["publication_actions_performed"] == []


def test_script_help_smoke():
    for script in [
        "note_preview.py",
        "pre_publish_check.py",
        "note_fact_check.py",
        "note_diff_check.py",
        "post_publish.py",
        "engagement_tracker.py",
        "render_readme.py",
        "provenance_leak_check.py",
        "provenance_label_check.py",
        "github_identity_guard.py",
        "japanese_closeout_language_check.py",
        "note_image_upload_boundary_check.py",
        "note_editor_prepublish_verify.py",
        "review_draft.py",
            "run_local_draft_qa_proof.py",
            "bump_package_version.py",
            "check_version_bump.py",
    ]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--help"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr
