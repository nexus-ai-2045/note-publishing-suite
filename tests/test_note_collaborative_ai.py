"""選択入力の範囲・read-only実行・異常応答を外部通信なしで検査する。"""
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("writing_ai", Path(__file__).parents[1] / "scripts/note_collaborative_ai.py")
ai = importlib.util.module_from_spec(spec); spec.loader.exec_module(ai)


def test_only_selected_article_and_theme_are_sent():
    theme = {"title": "テーマ", "messages": [{"id": "m1", "role": "user", "text": "問い"}],
             "sources": [{"id": "s1", "text": "資料", "path": "/private/path"}],
             "articles": [{"id": "one", "draft": "本文"}, {"id": "two", "draft": "別記事の私的本文"}]}
    raw = json.dumps(ai.build_context(theme, "one", "draft", "全文にする"), ensure_ascii=False)
    assert "別記事の私的本文" not in raw and "/private/path" not in raw
    assert "問い" in raw and "資料" in raw


def test_readonly_cli_uses_schema_and_stdin_not_shell(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda name: "/safe/codex")
    def runner(command, **options):
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "--ephemeral" in command and command[-1] == "-"
        assert "shell_tool" in command and "apps" in command and "plugins" in command
        assert "chronicle" in command
        assert "shell" not in options
        assert "問い" in options["input"]
        assert Path(command[command.index("-C") + 1]) == options["cwd"]
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"reply": "考えよう", "draft": "", "sections": [], "changes": []}))
        return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed"}\n')
    result = ai.generate({"mode": "chat", "instruction": "問い"}, runner=runner)
    assert result["reply"] == "考えよう"


def test_timeout_never_returns_partial_result(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda name: "/safe/codex")
    def runner(command, **options):
        raise subprocess.TimeoutExpired(command, 1)
    with pytest.raises(ai.GenerationError, match="現稿"):
        ai.generate({"mode": "chat"}, runner=runner)


@pytest.mark.parametrize("data", [{}, {"reply": "x", "draft": "", "sections": [], "changes": []},
                                   {"reply": "x", "draft": 5, "sections": [], "changes": []}])
def test_invalid_or_empty_draft_is_rejected(data):
    with pytest.raises(ai.GenerationError): ai.validate_result(data, "draft")


def test_connector_names_disabled_without_copying_auth_values(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text('[mcp_servers.sample]\ncommand="test"\n[mcp_servers.sample.env]\nTOKEN="artificial-private-value"\n')
    options = ai.isolated_cli_options()
    assert 'mcp_servers.sample.enabled=false' in options
    assert "artificial-private-value" not in str(options)


def test_unexpected_tool_event_rejects_otherwise_valid_answer(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda name: "/safe/codex")
    def runner(command, **options):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"reply": "返答", "draft": "", "sections": [], "changes": []}))
        return SimpleNamespace(returncode=0, stdout='{"type":"item.completed","item":{"type":"command_execution"}}\n{"type":"turn.completed"}\n')
    with pytest.raises(ai.GenerationError, match="文章生成以外"):
        ai.generate({"mode": "chat"}, runner=runner)
