#!/usr/bin/env python3
"""NPS共同執筆のローカル画面。preflightとdry-runは書込み・AI通信を行わない。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import mimetypes
import re
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

_SPEC = importlib.util.spec_from_file_location("_nps_writing_loader", Path(__file__).with_name("nps_script_loader.py"))
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("cannot load NPS script loader")
_LOADER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LOADER)
load_script = _LOADER.load_script

CORE = load_script("note_collaborative_session")
AI = load_script("note_collaborative_ai")
PROVENANCE = load_script("provenance_label_check")
MAX_REQUEST = 1_000_000


class WritingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, *, port=0, ui_root=None, provider=None, model=None):
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.ui_root = Path(ui_root or Path(__file__).resolve().parents[1] / "writing-app/dist").resolve()
        self.provider = provider or AI.generate
        self.model = model if model is not None else store.read_preferences().get("model")
        self.settings_revision = 0
        self.jobs = {}
        self.jobs_lock = threading.RLock()
        super().__init__(("127.0.0.1", port), Handler)

    def start_generation(self, theme_id, payload):
        store, model, settings_revision = self.store, self.model, self.settings_revision
        mode, instruction = payload.get("mode"), payload.get("instruction")
        snapshot = store.get_theme(theme_id)
        if snapshot["revision"] != payload.get("expected_revision"):
            raise CORE.SessionError("原稿または対話が更新されています。再読込みしてください", "stale")
        context = AI.build_context(snapshot, payload.get("article_id"), mode, instruction)
        context["editorial_references"] = store.generation_references(payload.get("article_id"))
        if len(json.dumps(context, ensure_ascii=False).encode()) > AI.MAX_CONTEXT_BYTES:
            raise AI.GenerationError("許可参照を含む入力が大きすぎます。自動省略せず対象を分けてください")
        with self.jobs_lock:
            if self.store is not store or self.settings_revision != settings_revision:
                raise CORE.SessionError("接続または保存先が変わりました。再確認してください", "stale")
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise CORE.SessionError("AIの応答を待っています", "busy")
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "status": "running", "theme_id": theme_id,
                   "input_revision": snapshot["revision"], "mode": mode}
            self.jobs[job_id] = job

        def run():
            try:
                receipt = {}
                result = AI.validate_result(self.provider(context, model=model, receipt=receipt), mode)
                current = store.get_theme(theme_id)
                if current["revision"] != snapshot["revision"]:
                    raise CORE.SessionError("生成中に編集されました。候補を保持しましたが、自動反映していません", "stale_generation")
                article_id = payload.get("article_id")
                article = next((a for a in current["articles"] if a["id"] == article_id), None)
                candidates = []
                if mode == "skeleton":
                    skeleton = {"sections": [{"id": f"s{i+1}", **row}
                                             for i, row in enumerate(result["sections"])]}
                    candidates = [{"target": "skeleton", "before": json.dumps(article["skeleton"], ensure_ascii=False),
                                   "after": json.dumps(skeleton, ensure_ascii=False), "intent": result["reply"] or "対話から構成案を作成"}]
                elif mode == "draft":
                    header = re.match(r"\A(?:\ufeff)?---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)", article["draft"])
                    if header:
                        generated_header = re.match(r"\A(?:\ufeff)?---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)", result["draft"])
                        body = result["draft"][generated_header.end():] if generated_header else result["draft"]
                        result["draft"] = header.group(0) + body
                    blocks = []
                    if result.get("blocks"):
                        paragraphs = PROVENANCE.fidelity_paragraphs(result["draft"])
                        if paragraphs != [block["text"] for block in result["blocks"]]:
                            raise AI.GenerationError("全文と段落の由来対応が一致しません。候補を保持して再確認します")
                        messages = {message["id"]: message for message in snapshot["messages"]}
                        sources = {source["id"] for source in snapshot["sources"]}
                        for block in result["blocks"]:
                            if block["kind"] == "hold":
                                raise AI.GenerationError("未確認の段落があります。確認後に本文案を作り直してください")
                            if any(ref not in messages for ref in block["message_ids"]) or any(ref not in sources for ref in block["source_ids"]):
                                raise AI.GenerationError("段落の根拠が選択した対話・素材にありません")
                            if block["kind"] == "user-said" and (not block["message_ids"] or any(messages[ref]["role"] != "user" for ref in block["message_ids"])):
                                raise AI.GenerationError("AIの発言を本人の判断として扱う由来対応は採用できません")
                            blocks.append({"id": "b-" + uuid.uuid4().hex[:12], "text": block["text"],
                                           "provenance_kind": block["kind"], "correspondence_status": "proposed",
                                           "source_refs": ["message:" + ref for ref in block["message_ids"]]
                                                          + ["source:" + ref for ref in block["source_ids"]]})
                    candidates = [{"before": article["draft"], "after": result["draft"],
                                   "intent": result["reply"] or "骨組みと対話を全文へ構成", "blocks": blocks}]
                elif mode == "revise":
                    candidates = result["changes"]
                current = store.mutate(theme_id, "record_generation", {
                    "reply": result["reply"] or "候補を作成しました。採用前に確認してください。",
                    "proposals": [{"article_id": article_id, "scope": "local", **p} for p in candidates],
                }, snapshot["revision"])
                with self.jobs_lock:
                    job.update(status="complete", theme=current, provider_receipt=receipt)
            except Exception as exc:
                with self.jobs_lock:
                    job.update(status="failed", error=str(exc), code=getattr(exc, "code", "generation_failed"))
                    if "result" in locals():
                        job["candidate"] = result

        threading.Thread(target=run, name="nps-generation", daemon=True).start()
        return {"job_id": job_id}

    def configuration(self):
        report = self.store.preflight()
        return {"session_token": self.token, "model": self.model or "configured",
                "settings_path": str(self.store.settings), "profile_id": self.store.profile_id,
                "storage": report["storage"], "settings_revision": self.settings_revision}

    def configure(self, data):
        model = data.get("model", self.model) or None
        if model == "configured": model = None
        if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 100):
            raise ValueError("モデル名が不正です")
        path = data.get("settings_path", str(self.store.settings))
        if not isinstance(path, str) or not path.strip():
            raise ValueError("既存のworkspace設定を指定してください")
        profile = data.get("profile_id", self.store.profile_id) or None
        if profile is not None and not isinstance(profile, str):
            raise ValueError("profile名が不正です")
        selected = CORE.SessionStore(Path(path), profile)
        selected.preflight()
        with self.jobs_lock:
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise CORE.SessionError("AIの応答後に接続・保存先を切り替えてください", "busy")
            selected.save_preferences(model)
            self.store, self.model = selected, model
            self.settings_revision += 1
        return self.configuration()


class Handler(BaseHTTPRequestHandler):
    server: WritingServer
    server_version = "NPSWriting/1"
    sys_version = ""

    def log_message(self, *args):
        pass  # Request paths can contain private article IDs; do not log them.

    def _send(self, value, status=200, content_type="application/json; charset=utf-8"):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def _allowed(self):
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed:
            self._send({"error": "接続先を確認してください", "code": "invalid_host"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in allowed}:
            self._send({"error": "別サイトからの要求は受け付けません", "code": "invalid_origin"}, 403)
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._send({"error": "別サイトからの要求は受け付けません", "code": "cross_site"}, 403)
            return False
        return True

    def _error(self, exc):
        code = getattr(exc, "code", "invalid")
        status = 409 if code in {"stale", "stale_proposal", "external_edit", "busy"} else 404 if code == "not_found" else 400
        self._send({"error": str(exc), "code": code}, status)

    def do_GET(self):
        if not self._allowed():
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/config":
                return self._send(self.server.configuration())
            if path == "/api/preflight":
                value = self.server.store.preflight()
                value["ai"] = AI.capabilities()
                return self._send(value)
            if path == "/api/themes":
                return self._send({"themes": self.server.store.list_themes()})
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "themes"]:
                return self._send(self.server.store.get_theme(parts[2]))
            if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                with self.server.jobs_lock:
                    job = copy.deepcopy(self.server.jobs.get(parts[2]))
                return self._send(job or {"error": "生成処理が見つかりません", "code": "not_found"}, 200 if job else 404)
            if path.startswith("/api/"):
                return self._send({"error": "操作が見つかりません", "code": "not_found"}, 404)
            relative = "index.html" if path == "/" else path.lstrip("/")
            candidate = self.server.ui_root / relative
            if (".." in Path(relative).parts or candidate.is_symlink()
                    or not candidate.resolve().is_relative_to(self.server.ui_root)
                    or not candidate.is_file()):
                return self._send({"error": "画面をbuildしてください", "code": "not_found"}, 404)
            mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            return self._send(candidate.read_bytes(), content_type=mime)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self._error(exc)

    def do_POST(self):
        if not self._allowed():
            return
        if not secrets.compare_digest(self.headers.get("X-NPS-Session", ""), self.server.token):
            return self._send({"error": "画面を再読込みしてください", "code": "invalid_session"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST:
                raise ValueError("要求サイズが不正です")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("JSONで要求してください")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("要求の形式が不正です")
            parts = urlsplit(self.path).path.strip("/").split("/")
            if parts == ["api", "preferences"]:
                return self._send(self.server.configure(data))
            if parts == ["api", "themes"]:
                return self._send(self.server.store.create_theme(data.get("title"), data.get("theme_id"),
                                                                 dry_run=data.get("dry_run") is True), 201)
            if len(parts) == 4 and parts[:2] == ["api", "themes"]:
                if parts[3] == "actions":
                    action, payload = data.get("action"), data.get("payload", {})
                    if not isinstance(payload, dict):
                        raise ValueError("操作内容が不正です")
                    if action == "record_generation":
                        raise ValueError("AIの返答は生成処理からのみ記録できます")
                    if action == "add_message":
                        payload = {**payload, "role": "user"}
                    return self._send(self.server.store.mutate(parts[2], action, payload,
                                                               data.get("expected_revision"), data.get("dry_run") is True))
                if parts[3] == "generate":
                    return self._send(self.server.start_generation(parts[2], data), 202)
            self._send({"error": "操作が見つかりません", "code": "not_found"}, 404)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self._error(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--profile-id", help="採用済み文体・履歴profileを明示選択")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--model", help="既存CLIで使用可能と確認したモデル。省略時は既存設定")
    parser.add_argument("--preflight", action="store_true", help="設定を読取り、起動・書込み・AI通信をしない")
    parser.add_argument("--dry-run", action="store_true", help="起動予定と設定検査をJSONで表示")
    parser.add_argument("--ui-root", type=Path, help="buildしたローカルUIの保存先")
    args = parser.parse_args(argv)
    try:
        store = CORE.SessionStore(args.settings, args.profile_id)
        report = store.preflight()
        if args.preflight or args.dry_run:
            report.update(dry_run=args.dry_run, writes_performed=False, ai_calls_performed=False,
                          server_started=False, intended_host="127.0.0.1", intended_port=args.port)
            print(json.dumps(report, ensure_ascii=False))
            return 0
        server = WritingServer(store, port=args.port, ui_root=args.ui_root, model=args.model)
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "server_started": True}, ensure_ascii=False), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc), "server_started": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
