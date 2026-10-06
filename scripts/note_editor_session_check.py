from __future__ import annotations

from datetime import datetime
from typing import Any


def validate_edit_session(data: dict[str, Any]) -> list[dict[str, str]]:
    if data.get("article_lane") != "production_candidate":
        return []
    errors = []

    def reject(code: str, message: str) -> None:
        errors.append({"severity": "error", "code": code, "message": message})

    session = data.get("edit_session")
    if not isinstance(session, dict):
        reject("edit_session_missing", "編集後の画像・公開設定の観測が未確認です")
        return errors
    images = session.get("image_edits")
    if not isinstance(images, list):
        reject("image_edits_unknown", "画像変更の観測が必要です。変更なしは空配列で明示します")
    else:
        for image in images:
            if not isinstance(image, dict) or not image.get("block_id"):
                reject("image_edit_unknown", "画像ブロックの識別情報が未確認です")
                continue
            if image.get("neighbors_verified") is not True or image.get("text_unchanged") is not True:
                reject("image_context_unverified", "画像前後の構造と本文保持が未確認です")
            if type(image.get("introduced_empty_paragraphs")) is not int or image["introduced_empty_paragraphs"] != 0:
                reject("image_empty_paragraphs", "画像操作で生じた空段落が残存または未確認です")
    settings = session.get("publish_settings")
    if not isinstance(settings, dict):
        reject("publish_settings_unknown", "公開設定の再読が未確認です")
        return errors
    if not session.get("settings_visit_id") or settings.get("visit_id") != session["settings_visit_id"]:
        reject("publish_settings_stale", "現在の公開設定画面と確認記録が一致しません")
    try:
        saved = datetime.fromisoformat(data["save_readback"]["observed_at"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(settings["observed_at"].replace("Z", "+00:00"))
        if saved.tzinfo is None or observed.tzinfo is None or observed < saved:
            raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        reject("publish_settings_before_readback", "本文の保存・再読後に公開設定を確認する必要があります")
    if any(not isinstance(value, list) or any(not isinstance(tag, str) or not tag.strip() for tag in value) for value in (settings.get("tags"), data.get("tags"))):
        reject("publish_tags_unknown", "タグの観測が必要です。タグなしは空配列で明示します")
    if settings.get("tags") != data.get("tags") or settings.get("magazine") != data.get("magazine"):
        reject("publish_settings_mismatch", "最新画面のタグ・マガジンと提出された観測が異なります")
    contests = settings.get("contest_entries")
    if not isinstance(contests, list):
        reject("contest_entries_unknown", "お題参加の確認が必要です。対象なしは空配列で明示します")
    else:
        for contest in contests:
            if not isinstance(contest, dict) or not contest.get("tag") or contest.get("tag") not in (data.get("tags") if isinstance(data.get("tags"), list) else []):
                reject("contest_entry_invalid", "お題の参加タグを確認できません")
            elif contest.get("participation_confirmed") is not True or contest.get("popup_resolved") is not True:
                reject("contest_entry_unconfirmed", "タグ入力だけではお題参加完了と扱えません")
    return errors
