#!/usr/bin/env python3
"""ローカル限定の共同執筆セッション保存層。外部サービスへ接続しない。"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_LOADER = importlib.util.spec_from_file_location("_nps_loader", Path(__file__).with_name("nps_script_loader.py"))
if _LOADER is None or _LOADER.loader is None:
    raise ImportError("cannot load NPS script loader")
_BOOT = importlib.util.module_from_spec(_LOADER)
_LOADER.loader.exec_module(_BOOT)
_WORKFLOW = _BOOT.load_script("note_workflow_gate")
_FEEDBACK = _BOOT.load_script("note_feedback")

SCHEMA = "nps-collaborative-session/v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_LOCAL = threading.RLock()


class SessionError(ValueError):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".session-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _safe(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SessionError(f"{label} is invalid", "invalid_id")
    return value


def _inside(root: Path, path: Path) -> Path:
    return _local_file(root, str(path))


def _local_file(root: Path, value: str) -> Path:
    """Resolve a workspace-relative file while rejecting symlink components."""
    lexical = Path(value) if Path(value).is_absolute() else root / value
    lexical = Path(os.path.abspath(str(lexical)))
    if not lexical.is_relative_to(root.absolute()):
        raise SessionError("保存先が許可したworkspaceの外です", "path_outside_workspace")
    current = root.absolute()
    for component in lexical.relative_to(current).parts:
        current = current / component
        if current.is_symlink():
            raise SessionError("symlinkを経由するpathは使えません", "symlink_path")
    return lexical


class SessionStore:
    """テーマごとの JSON 状態と記事別 Markdown を原子的に保存する。"""

    def __init__(self, settings: Path, profile_id: str | None = None):
        self.settings = Path(settings).expanduser().absolute()
        self.profile_id = profile_id
        self._workspace: Path | None = None
        self._dirs: dict[str, Path] = {}
        self._settings_hash: str | None = None

    def preflight(self) -> dict[str, Any]:
        expected, dirs = _WORKFLOW.read_workspace_settings(self.settings, self.profile_id or "__nps_theme__")
        config = json.loads(self.settings.read_text(encoding="utf-8"))
        workspace = Path(config["workspace_root"])
        workspace = (self.settings.parent / workspace if not workspace.is_absolute() else workspace).resolve()
        self._workspace, self._dirs = workspace, {k: Path(v).resolve() for k, v in dirs.items()}
        self._settings_hash = _sha(self.settings.read_bytes())
        for key, path in self._dirs.items():
            if not path.is_relative_to(workspace):
                raise SessionError("保存先が選んだworkspaceの外です", "storage_outside_workspace")
            raw = Path(config["storage"][key])
            _local_file(workspace, str(raw if raw.is_absolute() else workspace / raw))
        return {"ok": True, "storage": {k: str(v) for k, v in self._dirs.items()},
                "capabilities": {"external_calls": False, "atomic_writes": True, "cas": True},
                "settings_sha256": expected["settings_sha256"]}

    def _ensure(self) -> None:
        if self._workspace is None:
            self.preflight()
        elif _sha(self.settings.read_bytes()) != self._settings_hash:
            raise SessionError("保存先設定が変わりました。設定を確認して再起動してください", "settings_changed")

    def generation_references(self, article_id: str | None) -> dict:
        """採用settingsが許可した文体・過去参照を実内容とhashで返す。"""
        self._ensure()
        expected, _ = _WORKFLOW.read_workspace_settings(self.settings, self.profile_id or article_id or "__nps_theme__")
        references = []
        for path, digest in expected["reference_hashes"].items():
            raw = Path(path).read_bytes()
            if _sha(raw) != digest:
                raise SessionError("参照資料が読取り中に変わりました", "reference_changed")
            references.append({"name": Path(path).name, "sha256": digest, "text": raw.decode("utf-8")})
        binding = self._profile_binding(article_id)
        learning = []
        if self._feedback.exists():
            for directory in sorted(self._feedback.iterdir()):
                if directory.name.startswith("nps-") and directory.is_dir() and (directory / "feedback.json").is_file():
                    _local_file(self._feedback, str(directory))
                    record, verification = _FEEDBACK.read_feedback_record(self._dirs, directory.name)
                    for entry in record["entries"]:
                        if entry.get("scope") == "future" and entry["decision"] == "adopted" and entry.get("profile_binding") == binding:
                            learning.append({"before": entry["before"], "after": entry["after"], "intent": entry["reason"], "target": entry.get("target", "draft"),
                                             "evidence_ref": entry["evidence_ref"], "record_sha256": verification["record_sha256"]})
        return {"profile_id": self.profile_id, "references": references, "learning_examples": learning,
                "linebreak_policy": expected.get("linebreak_policy"),
                "history_required": expected.get("history_learning_policy", {}).get("required", False)}

    def _profile_binding(self, article_id: str | None) -> str:
        expected, _ = _WORKFLOW.read_workspace_settings(self.settings, self.profile_id or article_id or "__nps_theme__")
        return _sha(_json({"profile_id": self.profile_id, "references": expected["reference_hashes"]}))

    def read_preferences(self) -> dict:
        path = _inside(self._feedback, self._feedback / "_themes" / "preferences.json")
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(data, dict) or data.get("model") is not None and not isinstance(data["model"], str):
            raise SessionError("保存した接続設定の形式が不正です", "invalid_preferences")
        return data

    def save_preferences(self, model: str | None) -> None:
        with self._locked(write=True):
            path = _inside(self._feedback, self._feedback / "_themes" / "preferences.json")
            _atomic(path, _json({"model": model}))

    @property
    def _feedback(self) -> Path:
        self._ensure(); return self._dirs["feedback"]

    def _theme_path(self, theme_id: str) -> Path:
        theme_id = _safe(theme_id, "theme_id")
        return _inside(self._feedback, self._feedback / "_themes" / theme_id / "session.json")

    @contextmanager
    def _locked(self, write: bool = False):
        with _LOCAL:
            if not write:
                yield
                return
            lock_path = _inside(self._feedback, self._feedback / "_themes" / ".writer.lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+b") as stream:
                if os.name == "nt":
                    import msvcrt
                    if stream.tell() == 0:
                        stream.write(b"0"); stream.flush()
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _read(self, theme_id: str) -> dict[str, Any]:
        path = self._theme_path(theme_id)
        if path.with_name("transaction.json").exists():
            raise SessionError("保存が中断されています。recover操作で直近の正常版へ戻してください", "recovery_required")
        if not path.is_file():
            raise SessionError("テーマが見つかりません", "not_found")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SessionError("テーマの保存内容を読めません", "corrupt_state") from exc
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA or value.get("id") != theme_id:
            raise SessionError("テーマの保存内容が一致しません", "corrupt_state")
        conversation = value.get("conversation_ref")
        if conversation:
            snapshot = _local_file(self._workspace, conversation["path"])
            raw = snapshot.read_bytes()
            if _sha(raw) != conversation["sha256"] or json.loads(raw)["messages"] != value["messages"]:
                raise SessionError("保存対話と作業状態が一致しません", "conversation_corrupt")
        for source in value.get("sources", []):
            snapshot = self._source_path(theme_id, source["id"])
            if not snapshot.is_file() or _sha(snapshot.read_bytes()) != source["sha256"]:
                raise SessionError("保存原資料が変更されています", "source_corrupt")
        return value

    def _public(self, state: dict[str, Any]) -> dict[str, Any]:
        out = copy.deepcopy(state)
        out.pop("_expected_disk_hashes", None)
        source_hash = _sha(_json({"messages": state["messages"], "sources": state["sources"]}))
        by_id = {a["id"]: a for a in state["articles"]}
        for proposal in out.get("proposals", []):
            article = by_id.get(proposal["article_id"])
            if proposal["status"] == "pending" and (article is None
                    or proposal["base_revision"] != article["revision"]
                    or proposal.get("source_hash") != source_hash
                    or _sha(article["draft"].encode()) != article["_draft_sha256"]):
                proposal["status"] = "stale"
                proposal["stale_reason"] = "提案後に本文・構成・対話が更新されました"
        for article in out.get("articles", []):
            article.pop("_undo", None); article.pop("_redo", None); article.pop("_draft_sha256", None)
        out.pop("_feedback", None)
        return out

    def list_themes(self) -> list[dict[str, Any]]:
        self._ensure(); root = self._feedback / "_themes"
        if not root.is_dir(): return []
        result = []
        for path in sorted(root.iterdir()):
            if path.is_dir() and _ID.fullmatch(path.name) and (path / "session.json").is_file():
                state = self._read(path.name); result.append({"id": state["id"], "title": state["title"], "revision": state["revision"]})
        return result

    def create_theme(self, title: str, theme_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        self._ensure()
        if not isinstance(title, str) or not title.strip() or "\n" in title:
            raise SessionError("空でない題名を入力してください", "invalid_title")
        theme_id = _safe(theme_id or "theme-" + uuid.uuid4().hex[:12], "theme_id")
        state = {"schema_version": SCHEMA, "id": theme_id, "title": title.strip(), "revision": 0,
                 "messages": [], "sources": [], "articles": [], "proposals": [], "comments": [], "_feedback": [], "_created": True}
        with self._locked(write=not dry_run):
            if self._theme_path(theme_id).exists():
                raise SessionError("同じテーマが既にあります", "already_exists")
            if not dry_run:
                self._commit(state)
        return self._public(state)

    def get_theme(self, theme_id: str) -> dict[str, Any]:
        with self._locked():
            state = self._read(theme_id)
            conflicts = []
            for article in state.get("articles", []):
                path = self._draft_path(theme_id, article["id"])
                if path.exists() and article.get("_draft_sha256") != _sha(path.read_bytes()):
                    conflicts.append({"article_id": article["id"], "kind": "external_edit", "path": str(path)})
                article["draft"] = path.read_bytes().decode("utf-8") if path.exists() else article.get("draft", "")
                article["observed_draft_sha256"] = _sha(article["draft"].encode())
            out = self._public(state); out["conflicts"] = conflicts
            return out

    def _draft_path(self, theme_id: str, article_id: str) -> Path:
        record = self._theme_path(theme_id)
        if record.exists():
            state = json.loads(record.read_text(encoding="utf-8"))
            selected = next((a for a in state.get("articles", []) if a["id"] == article_id), None)
            if selected and selected.get("draft_path"):
                return _inside(self._dirs["drafts"], self._dirs["drafts"] / selected["draft_path"])
        return _inside(self._dirs["drafts"], self._dirs["drafts"] / "_themes" / _safe(theme_id, "theme_id") / f"{_safe(article_id, 'article_id')}.md")

    def _source_path(self, theme_id: str, source_id: str) -> Path:
        return _inside(self._dirs["sources"], self._dirs["sources"] / "_themes" / _safe(theme_id, "theme_id") / f"{_safe(source_id, 'source_id')}.snapshot")

    def _import_source(self, state, theme_id, raw_path, kind, writes, dry, source_id=None):
        if not isinstance(raw_path, str):
            raise SessionError("素材のファイルpathを指定してください")
        source = _local_file(self._workspace, raw_path)
        if not source.is_file():
            raise SessionError("素材は通常のローカルファイルを指定してください", "invalid_source")
        data = source.read_bytes()
        if len(data) > 300_000:
            raise SessionError("素材が大きすぎます。対象を分けてください", "source_too_large")
        sid = _safe(source_id or _sha(data)[:16], "source_id")
        dest = self._source_path(theme_id, sid)
        if dest.exists() and dest.read_bytes() != data:
            raise SessionError("保存済み原資料と内容が衝突しています", "source_collision")
        if any(row["id"] == sid for row in state["sources"]):
            return False
        state["sources"].append({"id": sid, "path": str(source.relative_to(self._workspace)),
                                 "text": data.decode("utf-8"), "sha256": _sha(data), "kind": kind})
        if not dry: writes.append((dest, data))
        return True

    def _commit(self, state: dict[str, Any], *, writes: list[tuple[Path, bytes]] = (), deletes: list[Path] = ()) -> None:
        backups: dict[Path, bytes | None] = {}
        state_path = self._theme_path(state["id"])
        journal = state_path.with_name("transaction.json")
        planned = dict(writes)
        for raw_path, expected in state.pop("_expected_disk_hashes", {}).items():
            path = _local_file(self._workspace, raw_path)
            if not path.is_file() or _sha(path.read_bytes()) != expected:
                raise SessionError("保存準備中に原稿が変わりました。編集内容は保持して再比較してください", "external_edit")
        conversation = _json({"schema_version": "nps-theme-conversation/v1",
                              "theme_id": state["id"], "messages": state["messages"]})
        conversation_sha = _sha(conversation)
        conversation_path = self._source_path(state["id"], "conversation-" + conversation_sha[:40]).with_suffix(".conversation.json")
        if conversation_path.exists() and conversation_path.read_bytes() != conversation:
            raise SessionError("保存済み対話の内容が一致しません", "conversation_corrupt")
        planned[conversation_path] = conversation
        state["conversation_ref"] = {"path": str(conversation_path.relative_to(self._workspace)), "sha256": conversation_sha}
        planned[state_path] = _json(state)
        all_writes = list(planned.items())
        for path, _ in all_writes:
            _local_file(self._workspace, str(path))
            backups.setdefault(path, path.read_bytes() if path.exists() else None)
        for path in deletes:
            _local_file(self._workspace, str(path))
            backups.setdefault(path, path.read_bytes() if path.exists() else None)
        _atomic(journal, _json({"backups": [
            {"path": str(path.relative_to(self._workspace)),
             "value": None if old is None else base64.b64encode(old).decode("ascii")}
            for path, old in backups.items()]}))
        try:
            for path, data in all_writes:
                _atomic(path, data)
            for path in deletes:
                if path.exists(): path.unlink()
            for path, data in all_writes:
                if path.read_bytes() != data:
                    raise SessionError("保存後の読戻しが一致しません", "save_readback_mismatch")
        except Exception:
            for path, old in backups.items():
                if old is None:
                    if path.exists(): path.unlink()
                else: _atomic(path, old)
            journal.unlink(missing_ok=True)
            raise
        journal.unlink()

    def _recovery_plan(self, theme_id: str) -> list[tuple[Path, bytes | None]]:
        journal = _local_file(self._workspace, str(self._theme_path(theme_id).with_name("transaction.json")))
        if not journal.exists():
            return []
        record = json.loads(journal.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or not isinstance(record.get("backups"), list):
            raise SessionError("復旧記録の形式が不正です", "invalid_recovery")
        plan, seen = [], set()
        current = json.loads(self._theme_path(theme_id).read_text(encoding="utf-8"))
        registered_drafts = {_inside(self._dirs["drafts"], self._dirs["drafts"] / a["draft_path"])
                             for a in current.get("articles", []) if a.get("draft_path")}
        for row in record["backups"]:
            if not isinstance(row, dict) or set(row) != {"path", "value"} or not isinstance(row["path"], str):
                raise SessionError("復旧項目の形式が不正です", "invalid_recovery")
            path = _local_file(self._workspace, row["path"])
            own_feedback = path.is_relative_to(self._feedback) and len(path.relative_to(self._feedback).parts) > 1 and path.relative_to(self._feedback).parts[0].startswith(f"nps-{len(theme_id)}-{theme_id}-")
            owned = (path == self._theme_path(theme_id)
                     or path.is_relative_to(self._dirs["drafts"] / "_themes" / theme_id)
                     or path.is_relative_to(self._dirs["sources"] / "_themes" / theme_id)
                     or path in registered_drafts
                     or own_feedback)
            if path in seen or not owned or path == journal:
                raise SessionError("重複または別テーマを対象とする復旧記録です", "invalid_recovery")
            value = row["value"]
            if value is not None and not isinstance(value, str):
                raise SessionError("復旧bytesの形式が不正です", "invalid_recovery")
            decoded = None if value is None else base64.b64decode(value, validate=True)
            plan.append((path, decoded)); seen.add(path)
        return plan

    def _recover(self, theme_id: str) -> None:
        plan = self._recovery_plan(theme_id)
        previous = {path: path.read_bytes() if path.exists() else None for path, _ in plan}
        try:
            for path, data in plan:
                if data is None: path.unlink(missing_ok=True)
                else: _atomic(path, data)
        except Exception:
            for path, old in previous.items():
                if old is None: path.unlink(missing_ok=True)
                else: _atomic(path, old)
            raise
        journal = self._theme_path(theme_id).with_name("transaction.json")
        journal.unlink(missing_ok=True)

    def _feedback_writes(self, state: dict, article: dict, entries: list[dict], before: str) -> list:
        """既存feedback writerで候補を組み、同じ保存transactionへ参加させる。"""
        article_id = self.feedback_article_id(state["id"], article["id"])
        current = article["draft"]
        live = _inside(self._feedback, self._feedback / article_id)
        with tempfile.TemporaryDirectory(prefix="nps-feedback-") as temporary:
            stage = Path(temporary)
            dirs = {name: stage / name for name in ("feedback", "sources", "drafts")}
            for directory in dirs.values(): directory.mkdir()
            if live.exists():
                previous, _ = _FEEDBACK.read_feedback_record(self._dirs, article_id)
                replacing = {entry["evidence_ref"] for entry in entries}
                entries = [entry for entry in previous["entries"]
                           if entry.get("scope") == "future" and entry["decision"] == "adopted"
                           and entry["evidence_ref"] not in replacing] + entries
                for old in live.rglob("*"):
                    checked = _local_file(self._feedback, str(old))
                    if checked.is_file():
                        target = dirs["feedback"] / article_id / old.relative_to(live)
                        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(checked.read_bytes())
            source = dirs["sources"] / "conversation.json"
            source.write_bytes(_json({"theme_id": state["id"], "messages": state["messages"],
                                      "sources": state["sources"]}))
            prior = dirs["sources"] / "prior.md"
            prior.write_text(before, encoding="utf-8")
            draft = dirs["drafts"] / "current.md"; draft.write_text(current, encoding="utf-8")
            _FEEDBACK.record_feedback(dirs, article_id, source, draft, prior, entries,
                                      conversation_id="nps-theme:" + state["id"],
                                      allow_empty_working_drafts=True)
            return [(_inside(self._feedback, self._feedback / path.relative_to(dirs["feedback"])), path.read_bytes())
                    for path in dirs["feedback"].rglob("*") if path.is_file()]

    @staticmethod
    def feedback_article_id(theme_id: str, article_id: str) -> str:
        # Length-prefixing is injective even when either ID contains separators.
        return f"nps-{len(theme_id)}-{theme_id}-{article_id}"

    def mutate(self, theme_id: str, action: str, payload: dict[str, Any] | None, expected_revision: int | None, dry_run: bool = False) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SessionError("操作内容はJSON objectで指定してください")
        with self._locked(write=not dry_run):
            if action == "recover":
                if dry_run:
                    return {"id": theme_id, "dry_run": True, "writes_performed": False,
                            "recovery_targets": [str(path.relative_to(self._workspace)) for path, _ in self._recovery_plan(theme_id)]}
                self._recover(theme_id)
                return self.get_theme(theme_id)
            state = self._read(theme_id)
            if type(expected_revision) is not int or expected_revision != state["revision"]:
                raise SessionError("対話または原稿が更新されています。最新状態を取得してください", "stale")
            if action not in {"add_message", "add_source", "create_article", "open_article", "add_comment", "reload_draft", "resolve_draft"}:
                targets = {payload.get("article_id")} | {p.get("article_id") for p in payload.get("proposals", []) if isinstance(p, dict)}
                for article in state["articles"]:
                    if article["id"] not in targets:
                        continue
                    path = self._draft_path(theme_id, article["id"])
                    if not path.exists() or _sha(path.read_bytes()) != article["_draft_sha256"]:
                        raise SessionError("外部で本文が変わりました。reload_draftで読込み直してください", "external_edit")
                    state.setdefault("_expected_disk_hashes", {})[str(path)] = article["_draft_sha256"]
            if action == "undo" or action == "redo":
                return self._history(state, payload, action, dry_run)
            writes: list[tuple[Path, bytes]] = []
            if action == "record_generation":
                reply = payload.get("reply")
                if not isinstance(reply, str) or not reply.strip():
                    raise SessionError("AIの返答が空です")
                state["messages"].append({"id": f"m{len(state['messages'])+1}", "role": "assistant", "text": reply})
                proposals = payload.get("proposals", [])
                if not isinstance(proposals, list):
                    raise SessionError("提案一覧が不正です")
                for proposal in proposals:
                    self._article_action(state, theme_id, "propose", proposal, writes, dry_run)
            elif action == "add_message":
                role, text = payload.get("role"), payload.get("text")
                if role not in {"user", "assistant", "system"} or not isinstance(text, str) or not text.strip(): raise SessionError("対話の内容と帰属が不正です")
                state["messages"].append({"id": f"m{len(state['messages'])+1}", "role": role, "text": text})
            elif action == "create_article":
                aid = _safe(payload.get("article_id") or f"article-{len(state['articles'])+1}", "article_id")
                if any(a["id"] == aid for a in state["articles"]): raise SessionError("同じ記事が既にあります", "already_exists")
                if self._draft_path(theme_id, aid).exists():
                    raise SessionError("その保存先には既存の原稿があります。open_articleで接続してください", "already_exists")
                state["articles"].append({"id": aid, "title": str(payload.get("title") or aid), "revision": 0, "draft": "", "blocks": [], "skeleton": {"sections": []}, "_undo": [], "_redo": [], "_draft_sha256": _sha(b"")})
                if not dry_run: writes.append((self._draft_path(theme_id, aid), b""))
            elif action == "open_article":
                raw_path = payload.get("draft_path")
                if not isinstance(raw_path, str):
                    raise SessionError("開く原稿のpathを指定してください")
                path = _local_file(self._workspace, raw_path)
                if not path.is_relative_to(self._dirs["drafts"]) or path.suffix.lower() != ".md" or not path.is_file():
                    raise SessionError("採用したdrafts内のMarkdown原稿を指定してください", "invalid_draft")
                for other in self.list_themes():
                    existing = self._read(other["id"])
                    if any(path.samefile(self._draft_path(other["id"], a["id"]))
                           for a in existing["articles"] if self._draft_path(other["id"], a["id"]).exists()):
                        raise SessionError("その原稿は既にテーマへ接続されています", "already_open")
                aid = _safe(payload.get("article_id") or f"article-{len(state['articles'])+1}", "article_id")
                if any(a["id"] == aid for a in state["articles"]):
                    raise SessionError("同じ記事が既にあります", "already_exists")
                raw = path.read_bytes()
                article = {"id": aid, "title": str(payload.get("title") or path.stem), "revision": 0,
                           "draft": raw.decode("utf-8"), "draft_path": str(path.relative_to(self._dirs["drafts"])),
                           "blocks": [], "skeleton": {"sections": []}, "_undo": [], "_redo": [], "_draft_sha256": _sha(raw)}
                for marker in re.finditer(r"<!--\s*paragraph-id:\s*([a-z0-9][a-z0-9-]*)\s*-->\s*([^\n]+(?:\n(?!\s*\n|<!--)[^\n]+)*)", article["draft"]):
                    article["blocks"].append({"id": "b-" + uuid.uuid4().hex[:12], "text": marker.group(2).strip(),
                                              "source_refs": ["paragraph:" + marker.group(1)], "correspondence_status": "declared_unverified"})
                self._import_source(state, theme_id, raw_path, "existing_draft", writes, dry_run)
                if payload.get("skeleton_path"):
                    skeleton_path = _local_file(self._workspace, payload["skeleton_path"])
                    if not skeleton_path.is_file() or skeleton_path.stat().st_size > 300_000:
                        raise SessionError("骨組みは300KB以内の通常のJSONファイルを指定してください")
                    skeleton_raw = skeleton_path.read_bytes()
                    data = json.loads(skeleton_raw)
                    if isinstance(data, dict) and isinstance(data.get("episodes"), list):
                        episode = payload.get("episode")
                        if episode is None and len(data["episodes"]) == 1:
                            episode = data["episodes"][0].get("n")
                        data = next((e for e in data["episodes"] if e.get("n") == episode), None)
                    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
                        raise SessionError("骨組みJSONと、複数話がある場合は話数を指定してください")
                    sections = []
                    for i, section in enumerate(data["sections"]):
                        if not isinstance(section, dict) or not isinstance(section.get("heading"), str):
                            raise SessionError("骨組みの見出し形式が不正です")
                        sections.append({**section, "id": section.get("id", f"s{i+1}"),
                            "paragraph_ids": section.get("paragraph_ids", [p["id"] for p in section.get("paragraphs", []) if isinstance(p, dict) and p.get("id")])})
                    article["skeleton"] = {"sections": sections}
                    article["skeleton_source"] = {"path": str(skeleton_path.relative_to(self._workspace)), "sha256": _sha(skeleton_raw)}
                    self._import_source(state, theme_id, payload["skeleton_path"], "existing_skeleton", writes, dry_run)
                    if skeleton_path.read_bytes() != skeleton_raw:
                        raise SessionError("骨組みが読取り中に変わりました", "source_changed")
                if path.read_bytes() != raw:
                    raise SessionError("原稿が読取り中に変わりました", "source_changed")
                state["articles"].append(article)
            elif action == "add_source":
                if not self._import_source(state, theme_id, payload.get("path"), payload.get("kind", "source"), writes, dry_run, payload.get("id")):
                    return self._public(state)
            else:
                self._article_action(state, theme_id, action, payload, writes, dry_run)
            pending = state.pop("_feedback_pending", [])
            grouped = {}
            for aid, entries, before in pending:
                group = grouped.setdefault(aid, {"entries": [], "before": before})
                group["entries"].extend(entries)
            for aid, group in grouped.items():
                article = next(a for a in state["articles"] if a["id"] == aid)
                writes.extend(self._feedback_writes(state, article, group["entries"], group["before"]))
            state["revision"] += 1
            if dry_run: return self._public(state)
            self._commit(state, writes=writes)
            return self.get_theme(theme_id)

    @staticmethod
    def _frame(state: dict, article: dict) -> dict:
        return {"draft": article["draft"], "skeleton": copy.deepcopy(article["skeleton"]),
                "blocks": copy.deepcopy(article["blocks"]),
                "proposal_statuses": {p["id"]: p["status"] for p in state["proposals"]
                                      if p["article_id"] == article["id"]}}

    def _remember(self, state: dict, article: dict) -> None:
        article.setdefault("_undo", []).append(self._frame(state, article))
        article["_redo"] = []

    def _article_action(self, state, theme_id, action, p, writes, dry):
        aid = _safe(p.get("article_id"), "article_id")
        article = next((a for a in state["articles"] if a["id"] == aid), None)
        if article is None:
            raise SessionError("記事が見つかりません", "not_found")
        before = article["draft"]
        feedback = []
        changed = False
        if action in {"save_draft", "reload_draft", "resolve_draft"}:
            if action == "resolve_draft":
                path = self._draft_path(theme_id, aid)
                actual = path.read_bytes()
                if p.get("expected_draft_sha256") != _sha(actual):
                    raise SessionError("比較後に原稿が変わりました。もう一度比較してください", "stale")
                before = actual.decode("utf-8")
                article["draft"] = before
                state.setdefault("_expected_disk_hashes", {})[str(path)] = _sha(actual)
            draft = p.get("draft") if action != "reload_draft" else self._draft_path(theme_id, aid).read_bytes().decode("utf-8")
            if not isinstance(draft, str):
                raise SessionError("本文は文字列で指定してください")
            if len(draft.encode()) > 900_000:
                raise SessionError("本文が大きすぎます")
            self._remember(state, article)
            article["draft"] = draft
            blocks = p.get("blocks", [])
            if not isinstance(blocks, list):
                raise SessionError("本文の対応形式が不正です")
            article["blocks"] = blocks
            changed = True
            feedback = [{"origin": "author", "decision": "adopted", "before": before,
                         "after": draft, "reason": "本人が比較後に編集を保存" if action == "resolve_draft" else "本人の直接編集" if action == "save_draft" else "外部編集を明示的に読込み",
                         "evidence_ref": "nps-session:" + state["id"] + ":" + str(state["revision"])}]
        elif action == "set_skeleton":
            skeleton = p.get("skeleton")
            if not isinstance(skeleton, dict) or not isinstance(skeleton.get("sections"), list):
                raise SessionError("骨組みにはsections配列が必要です")
            self._remember(state, article)
            article["skeleton"] = skeleton
            changed = True
        elif action == "add_comment":
            if not isinstance(p.get("text"), str) or not p["text"].strip():
                raise SessionError("コメントを入力してください")
            quote = p.get("quote", "")
            state["comments"].append({"id": f"c{len(state['comments'])+1}", "article_id": aid,
                                      "quote": quote, "text": p["text"], "block_id": p.get("block_id"),
                                      "status": "open" if not quote or quote in before else "detached"})
        elif action == "propose":
            old, new = p.get("before"), p.get("after")
            target = p.get("target", "draft")
            if target not in {"draft", "skeleton"} or not isinstance(old, str) or not isinstance(new, str):
                raise SessionError("修正先と変更前後が必要です")
            if not isinstance(p.get("intent"), str) or not p["intent"].strip():
                raise SessionError("修正の意図が必要です")
            if p.get("scope", "local") not in {"local", "article", "future"}:
                raise SessionError("適用範囲を選んでください")
            current = before if target == "draft" else json.dumps(article["skeleton"], ensure_ascii=False)
            if old != current and (not old or current.count(old) != 1):
                raise SessionError("修正箇所を一意に特定できません", "stale_proposal")
            if target == "skeleton":
                parsed = json.loads(new)
                if not isinstance(parsed, dict) or not isinstance(parsed.get("sections"), list):
                    raise SessionError("骨組み案の形式が不正です")
            state["proposals"].append({"id": f"p{len(state['proposals'])+1}", "article_id": aid,
                "target": target, "before": old, "after": new, "intent": p["intent"],
                "status": "pending", "scope": p.get("scope") or "local", "base_revision": article["revision"],
                "blocks": copy.deepcopy(p.get("blocks", [])),
                "source_hash": _sha(_json({"messages": state["messages"], "sources": state["sources"]}))})
            feedback = [{"origin": "ai", "decision": "pending", "before": old, "after": new,
                         "reason": p["intent"], "evidence_ref": f"nps-session:{state['id']}:proposal:{state['proposals'][-1]['id']}",
                         "scope": p.get("scope") or "local", "target": target}]
        elif action == "decide":
            decision, ids = p.get("decision"), p.get("proposal_ids")
            scope = p.get("scope")
            if scope is not None and scope not in {"local", "article", "future"}:
                raise SessionError("適用範囲を選んでください")
            if decision not in {"adopted", "rejected", "pending"} or not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
                raise SessionError("対象の提案と採否が必要です")
            selected = [x for x in state["proposals"] if x["id"] in ids and x["article_id"] == aid]
            if len(selected) != len(ids):
                raise SessionError("提案が見つかりません", "not_found")
            if decision == "adopted":
                source_hash = _sha(_json({"messages": state["messages"], "sources": state["sources"]}))
                ranges = {"draft": [], "skeleton": []}
                for proposal in selected:
                    if proposal["status"] == "adopted":
                        raise SessionError("採用済みの案は再適用できません", "already_adopted")
                    if proposal["base_revision"] != article["revision"] or proposal.get("source_hash") != source_hash:
                        raise SessionError("提案後に本文・構成・対話が変わりました。再比較してください", "stale_proposal")
                    text = before if proposal["target"] == "draft" else json.dumps(article["skeleton"], ensure_ascii=False)
                    old = proposal["before"]
                    if old != text and (not old or text.count(old) != 1):
                        raise SessionError("提案箇所が更新されています", "stale_proposal")
                    start = text.index(old) if old else 0
                    end = start + len(old)
                    rows = ranges[proposal["target"]]
                    if any(start < right and left < end or (start == end == left == right) for left, right, _ in rows):
                        raise SessionError("選んだ提案の修正箇所が重複しています", "overlap")
                    rows.append((start, end, proposal["after"]))
                self._remember(state, article)
                for target, rows in ranges.items():
                    text = before if target == "draft" else json.dumps(article["skeleton"], ensure_ascii=False)
                    for left, right, after in sorted(rows, reverse=True):
                        text = text[:left] + after + text[right:]
                    if rows:
                        if target == "draft": article["draft"] = text
                        else: article["skeleton"] = json.loads(text)
                whole = [p for p in selected if p["target"] == "draft" and p["before"] == before and p.get("blocks")]
                if len(whole) == 1:
                    article["blocks"] = copy.deepcopy(whole[0]["blocks"])
                changed = True
            for proposal in selected:
                proposal["status"] = decision
                proposal["profile_binding"] = self._profile_binding(aid)
                if scope is not None:
                    proposal["scope"] = scope
                feedback.append({"origin": "ai", "decision": decision, "before": proposal["before"],
                                 "after": proposal["after"], "reason": proposal["intent"],
                                 "evidence_ref": f"nps-session:{state['id']}:proposal:{proposal['id']}",
                                 "scope": proposal["scope"], "target": proposal["target"],
                                 "profile_binding": proposal["profile_binding"]})
        elif action == "revoke_learning":
            proposal = next((row for row in state["proposals"] if row["id"] == p.get("proposal_id") and row["article_id"] == aid), None)
            if proposal is None or proposal.get("scope") != "future":
                raise SessionError("今後への適用を取り消す提案を選んでください")
            proposal["scope"] = "local"
            feedback = [{"origin": "author", "decision": "rejected", "before": proposal["before"],
                         "after": proposal["after"], "reason": "今後への適用を本人が取り消した。現稿は保持する。",
                         "evidence_ref": f"nps-session:{state['id']}:proposal:{proposal['id']}", "scope": "future",
                         "profile_binding": self._profile_binding(aid)}]
        else:
            raise SessionError("未対応の操作です", "unsupported_action")
        if changed:
            article["revision"] += 1
            article["_draft_sha256"] = _sha(article["draft"].encode())
            if not dry:
                writes.append((self._draft_path(theme_id, aid), article["draft"].encode()))
            for comment in state["comments"]:
                if comment["article_id"] == aid and comment["quote"]:
                    comment["status"] = "open" if comment["quote"] in article["draft"] else "detached"
        if feedback and not dry:
            state.setdefault("_feedback_pending", []).append((aid, feedback, before))

    def _history(self, state, p, action, dry):
        aid = _safe(p.get("article_id"), "article_id")
        article = next((a for a in state["articles"] if a["id"] == aid), None)
        if article is None:
            raise SessionError("記事が見つかりません", "not_found")
        source = article.setdefault("_undo" if action == "undo" else "_redo", [])
        target = article.setdefault("_redo" if action == "undo" else "_undo", [])
        if not source:
            raise SessionError("戻せる履歴がありません", "history_empty")
        before = article["draft"]
        previous_statuses = {p["id"]: p["status"] for p in state["proposals"] if p["article_id"] == aid}
        target.append(self._frame(state, article))
        frame = source.pop()
        for key in ("draft", "skeleton", "blocks"):
            article[key] = frame[key]
        for proposal in state["proposals"]:
            if proposal["article_id"] == aid and proposal["id"] in frame["proposal_statuses"]:
                proposal["status"] = frame["proposal_statuses"][proposal["id"]]
        article["revision"] += 1
        article["_draft_sha256"] = _sha(article["draft"].encode())
        source_hash = _sha(_json({"messages": state["messages"], "sources": state["sources"]}))
        for proposal in state["proposals"]:
            target = article["draft"] if proposal["target"] == "draft" else json.dumps(article["skeleton"], ensure_ascii=False)
            if (proposal["article_id"] == aid and proposal["status"] == "pending"
                    and proposal.get("source_hash") == source_hash
                    and (proposal["before"] == target or proposal["before"] and target.count(proposal["before"]) == 1)):
                proposal["base_revision"] = article["revision"]
        state["revision"] += 1
        if not dry:
            entries = [{"origin": "author", "decision": "adopted", "before": before,
                        "after": article["draft"], "reason": "本人による履歴復元: " + action,
                        "evidence_ref": f"nps-session:{state['id']}:revision:{state['revision']}"}]
            for proposal in state["proposals"]:
                if (proposal["article_id"] == aid and proposal.get("scope") == "future"
                        and previous_statuses.get(proposal["id"]) != proposal["status"]):
                    entries.append({"origin": "author", "decision": proposal["status"],
                                    "before": proposal["before"], "after": proposal["after"],
                                    "reason": "本人による採否と今後への適用の履歴復元: " + action,
                                    "evidence_ref": f"nps-session:{state['id']}:proposal:{proposal['id']}",
                                    "scope": "future", "profile_binding": proposal.get("profile_binding"),
                                    "target": proposal["target"]})
            writes = [(self._draft_path(state["id"], aid), article["draft"].encode())]
            writes.extend(self._feedback_writes(state, article, entries, before))
            self._commit(state, writes=writes)
        return self._public(state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NPSの対話型共同執筆をローカルで保存・再開する")
    parser.add_argument("--settings", type=Path, required=True); sub = parser.add_subparsers(dest="command", required=True)
    parser.add_argument("--profile-id", help="採用済みの文体・履歴profile。必須policyがある場合は明示選択")
    sub.add_parser("preflight"); sub.add_parser("list")
    create = sub.add_parser("create"); create.add_argument("title"); create.add_argument("--id"); create.add_argument("--dry-run", action="store_true")
    show = sub.add_parser("show"); show.add_argument("theme_id")
    act = sub.add_parser("action"); act.add_argument("theme_id"); act.add_argument("action"); act.add_argument("--payload", default="{}"); act.add_argument("--expected-revision", type=int); act.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv); store = SessionStore(args.settings, args.profile_id)
    try:
        if args.command == "preflight": result = store.preflight()
        elif args.command == "list": result = {"themes": store.list_themes()}
        elif args.command == "create": result = store.create_theme(args.title, args.id, args.dry_run)
        elif args.command == "show": result = store.get_theme(args.theme_id)
        else: result = store.mutate(args.theme_id, args.action, json.loads(args.payload), args.expected_revision, args.dry_run)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True)); return 0
    except (SessionError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "code": getattr(exc, "code", "invalid")}, ensure_ascii=False)); return 2


if __name__ == "__main__": raise SystemExit(main())
