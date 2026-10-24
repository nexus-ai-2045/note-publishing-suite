"""既存記事の更新に限定した、利用者設定による追加確認省略の判定。UI操作は行わない。"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path


def authorize_update(settings_path: Path | None, observation: object) -> dict:
    denied = {"automation_allowed": False, "manual_publish_required": True,
              "reason": "existing_update_not_authorized", "authenticity_verified": False}
    if settings_path is None or not isinstance(observation, dict):
        return denied
    try:
        path = Path(settings_path).resolve()
        settings = json.loads(path.read_text(encoding="utf-8"))
        policy = settings.get("publication_policy", {}).get("existing_article_update", {})
        if (policy.get("enabled") is not True or policy.get("schema") != "nps-existing-update-policy/v1"
                or not isinstance(policy.get("account"), str) or not policy["account"]):
            return denied
        root = (path.parent / settings["workspace_root"]).resolve()
        evidence = (root / policy["approval_ref"]).resolve()
        if not evidence.is_relative_to(root) or hashlib.sha256(evidence.read_bytes()).hexdigest() != policy["approval_sha256"]:
            return denied
        note_id = observation.get("note_id")
        if not isinstance(note_id, str) or not re.fullmatch(r"n[a-z0-9]+", note_id):
            return denied
        if (observation.get("operation") != "update_existing"
                or observation.get("published_before") is not True
                or observation.get("account") != policy["account"]
                or observation.get("public_url") != f'https://note.com/{policy["account"]}/n/{note_id}'
                or observation.get("action") != "更新する"
                or observation.get("new_publication") is not False
                or observation.get("schedule_change") is not False
                or observation.get("external_share") is not False):
            return denied
        # 値の同一性と検査receiptはruntimeが実観測へ束縛する。JSONだけで真正性を証明しない。
        for keys in (("approved_content_sha256", "editor_content_sha256", "saved_content_sha256"),
                     ("baseline_settings_sha256", "current_settings_sha256")):
            values = [observation.get(key) for key in keys]
            if any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in values) or len(set(values)) != 1:
                return denied
        checks = observation.get("checks", {})
        if any(checks.get(key) is not True for key in (
                "requested_change_only", "body_and_links_verified", "layout_verified",
                "saved_and_reloaded", "public_identity_verified", "prepublish_qa_passed")):
            return denied
        if not isinstance(observation.get("edit_request_ref"), str) or not observation["edit_request_ref"].strip():
            return denied
        return {"automation_allowed": True, "manual_publish_required": False,
                "reason": "authorized_existing_article_update", "action": "更新する",
                "note_id": note_id, "public_url": observation["public_url"],
                "policy_approval_sha256": policy["approval_sha256"], "authenticity_verified": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return denied
