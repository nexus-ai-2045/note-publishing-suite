"""承認済み記事別フッター計画と、供給された観測だけを照合する。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSONキーの重複があります")
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    def invalid_constant(_: str) -> None:
        raise ValueError("JSONに非標準の数値があります")

    return json.loads(
        text, object_pairs_hook=_unique_object, parse_constant=invalid_constant
    )


def _selection_block(text: str) -> str:
    blocks: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    selected = False
    body: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if fence_char is not None:
            if (
                match
                and match[1][0] == fence_char
                and len(match[1]) >= fence_length
                and not match[2].strip()
            ):
                if selected:
                    blocks.append("\n".join(body))
                fence_char = None
                selected = False
                body = []
            elif selected:
                body.append(line)
            continue
        if match:
            fence_char, fence_length = match[1][0], len(match[1])
            selected = bool(
                re.fullmatch(r"footer-selection(?:[ \t]+JSON)?", match[2].strip(), re.I)
            )
    if selected or len(blocks) != 1:
        raise ValueError("閉じたfooter-selection JSONブロックは1つ必要です")
    return blocks[0]


def load_production_plan(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".md":
        text = _selection_block(text)
    value = parse_json(text)
    if isinstance(value, dict) and "footer_selection" in value:
        value = value["footer_selection"]
    if not isinstance(value, dict):
        raise ValueError("選定計画はJSONオブジェクトが必要です")
    return value


def plan_sha256(plan: dict[str, Any]) -> str:
    payload = {key: value for key, value in plan.items() if key != "review"}
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _url(value: Any) -> bool:
    if (
        not _nonempty(value)
        or value != value.strip()
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        return False
    try:
        parts = urlsplit(value)
        return (
            parts.scheme in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and parts.port != 0
        )
    except ValueError:
        return False


def validate_footer_selection(data: dict[str, Any], plan: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def fail(code: str, message: str) -> None:
        errors.append({"severity": "error", "code": code, "message": message})

    if isinstance(plan, dict) and "footer_selection" in plan:
        plan = plan["footer_selection"]
    if not isinstance(plan, dict) or not plan:
        fail("footer_plan_missing", "記事別の選定計画がありません")
        return errors
    allowed = {
        "article_id", "reader", "series", "reader_action", "links", "review",
        "decision", "reason",
    }
    if set(plan) - allowed:
        fail("footer_plan_unknown_fields", "選定計画に未知の項目があります")
    for field in ("article_id", "reader", "series", "reader_action"):
        if not _nonempty(plan.get(field)):
            fail(
                "footer_plan_field_missing",
                "選定計画の識別情報・読者・読後行動が不足しています",
            )
    for field in ("article_id", "series"):
        if not _nonempty(data.get(field)) or data.get(field) != plan.get(field):
            fail(
                "footer_context_mismatch",
                "観測の記事またはシリーズが選定計画と一致しません",
            )
    review = plan.get("review")
    if not isinstance(review, dict):
        review = {}
    if set(review) - {"status", "reviewer", "reviewed_at", "plan_sha256"}:
        fail("footer_review_unknown_fields", "レビュー記録に未知の項目があります")
    if review.get("status") != "approved" or not _nonempty(review.get("reviewer")):
        fail("footer_plan_unapproved", "選定計画の人間レビュー承認がありません")
    try:
        stamp = review.get("reviewed_at")
        if not isinstance(stamp, str) or "T" not in stamp:
            raise ValueError
        reviewed_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if (
            reviewed_at.tzinfo is None
            or reviewed_at.utcoffset() is None
            or reviewed_at > datetime.now(timezone.utc)
        ):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        fail(
            "footer_review_time_invalid",
            "レビュー日時は未来でないタイムゾーン付きISO日時が必要です",
        )
    try:
        if review.get("plan_sha256") != plan_sha256(plan):
            fail("footer_review_hash_mismatch", "選定計画が承認時の内容と一致しません")
    except (TypeError, ValueError):
        fail("footer_plan_invalid", "選定計画を正規化できません")
    # 既存計画は採用として扱い、空リンクから省略を推測しない。
    decision = plan.get("decision", "include")
    if (
        decision not in ("include", "omit")
        or ("decision" in plan and not _nonempty(plan.get("reason")))
    ):
        fail("footer_plan_decision_invalid", "フッターの明示的な採否と理由が不正です")
    links = plan.get("links")
    if not isinstance(links, list) or (not links and decision != "omit"):
        fail("footer_plan_links_missing", "選定リンクは1件以上必要です")
        links = []
    if decision == "omit" and links:
        fail("footer_plan_decision_mismatch", "フッター非採用の選定リンクは空配列が必要です")
    expected: dict[str, tuple[int, str, bool, bool]] = {}
    for index, link in enumerate(links):
        if not isinstance(link, dict):
            fail("footer_plan_link_invalid", "選定リンクの形式が不正です")
            continue
        if set(link) - {"url", "registry_ref", "reason", "presentation", "required", "require_rendered"}:
            fail("footer_plan_link_unknown_fields", "選定リンクに未知の項目があります")
        url = link.get("url")
        if not _url(url):
            fail(
                "footer_plan_url_invalid",
                "選定リンクURLは認証情報を含まない絶対HTTP(S) URLが必要です",
            )
            continue
        if not _nonempty(link.get("registry_ref")) or not _nonempty(link.get("reason")):
            fail(
                "footer_plan_link_metadata_missing",
                "既存登録正本への参照と採用理由が必要です",
            )
        if (
            link.get("presentation") not in ("card", "text_link")
            or type(link.get("required")) is not bool
        ):
            fail(
                "footer_plan_link_invalid",
                "リンクの表示種別または必須・任意の指定が不正です",
            )
            continue
        if url in expected:
            fail("footer_plan_duplicate_url", "選定計画でURLが重複しています")
        if type(link.get("require_rendered", False)) is not bool:
            fail("footer_plan_link_invalid", "require_renderedは真偽値が必要です")
        if decision != "omit":
            expected[url] = (index, link["presentation"], link["required"], link.get("require_rendered", False))
    footer = data.get("footer")
    nodes = footer.get("nodes") if isinstance(footer, dict) else None
    if isinstance(footer, dict) and set(footer) - {"nodes"}:
        fail(
            "footer_legacy_or_unknown_fields",
            "旧形式または未知のフッター項目はDOM順のnodesへ移行してください",
        )
    if not isinstance(nodes, list):
        fail("footer_nodes_missing", "DOM順のフッター観測ノードがありません")
        return errors
    seen: set[str] = set()
    order: list[int] = []
    for node in nodes:
        if not isinstance(node, dict):
            fail("footer_node_invalid", "フッター観測ノードの形式が不正です")
            continue
        tag = node.get("tag")
        if tag == "FIGURE":
            candidates = [
                node[key] for key in ("data_src", "data-src", "url") if key in node
            ]
            if "hrefs" in node:
                if not isinstance(node["hrefs"], list):
                    fail("footer_node_invalid", "カードのhrefsは配列が必要です")
                    continue
                candidates.extend(node["hrefs"])
            if (
                not candidates
                or any(not _url(url) for url in candidates)
                or len(set(candidates)) != 1
            ):
                fail("footer_card_url_ambiguous", "カードのURLを一意に解決できません")
                continue
            url, presentation = candidates[0], "card"
        elif tag == "A":
            candidates = [node[key] for key in ("href", "url") if key in node]
            if (
                not candidates
                or any(not _url(url) for url in candidates)
                or len(set(candidates)) != 1
                or not _nonempty(node.get("text"))
            ):
                fail("footer_node_invalid", "文字リンクのURLまたは表示文字が不正です")
                continue
            url, presentation = candidates[0], "text_link"
            if node["text"].strip() == url:
                fail("footer_raw_url", "URLそのものが表示文字として残っています")
        else:
            fail("footer_node_unknown", "未知または空のフッター観測ノードがあります")
            continue
        if url in seen:
            fail("footer_duplicate_url", "フッター観測でURLが重複しています")
        seen.add(url)
        if url not in expected:
            fail("footer_extra_url", "選定計画にないリンクが観測されています")
            continue
        index, planned_presentation, _, require_rendered = expected[url]
        order.append(index)
        if presentation != planned_presentation:
            fail(
                "footer_presentation_mismatch",
                "カードと文字リンクの表示種別が選定計画と一致しません",
            )
        if require_rendered and presentation == "card" and (
            node.get("rendered") is not True
            or not _nonempty(node.get("title"))
            or node.get("rendered_href") != url
        ):
            fail("footer_card_not_rendered", "カードの読込み済み表示・タイトル・リンク先を確認できません")
    if order != sorted(order):
        fail("footer_order_mismatch", "リンクのDOM順が選定計画と一致しません")
    if any(required and url not in seen for url, (_, _, required, _) in expected.items()):
        fail("footer_required_missing", "必須の選定リンクが観測されていません")
    return errors


def validate_policy(value: Any) -> dict:
    """読戻し必須の適用だけを利用側が記事ごとに宣言する。"""
    if (not isinstance(value, dict)
            or set(value) - {'schema', 'required', 'reason'}
            or value.get('schema') != 'nps-footer-readback-policy/v1'
            or type(value.get('required')) is not bool
            or not value['required'] and not _nonempty(value.get('reason'))):
        raise ValueError('footer_readback_policy_invalid')
    return dict(value)


def _target_identity(value: Any) -> tuple[str, str]:
    if not _url(value):
        raise ValueError('footer_target_url_invalid')
    parsed = urlsplit(value)
    editor = re.fullmatch(r'/notes/(n[a-zA-Z0-9]+)/edit/?', parsed.path)
    reader = re.fullmatch(r'/[^/]+/n/(n[a-zA-Z0-9]+)/?', parsed.path)
    if parsed.hostname == 'editor.note.com' and editor:
        return ('note.com', editor[1])
    if parsed.hostname == 'note.com' and reader:
        return ('note.com', reader[1])
    return (parsed.netloc, parsed.path)


def check_readback(policy: Any, data: Any, *, article_id: str, article_sha256: str,
                   layout: dict | None = None, public_only: bool = False,
                   expected_url: str | None = None) -> dict:
    """既存フッター検査を対象版と読取り面に束縛する。観測の真正性は認証しない。"""
    result = {'status': 'not_required', 'errors': [], 'hashes': {},
              'verification_scope': 'supplied_snapshot_only', 'live_dom_verified': False,
              'ready_for_publish': False}
    if policy is None:
        return result
    try:
        policy = validate_policy(policy)
        if not policy['required']:
            return result
        if (not isinstance(data, dict) or data.get('article_id') != article_id
                or not isinstance(article_sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', article_sha256)
                or data.get('article_draft_sha256') != article_sha256
                or not _url(data.get('url'))):
            raise ValueError('footer_readback_article_or_version_invalid')
        surface = data.get('surface')
        if surface not in ({'public'} if public_only else {'reader_saved', 'reserved', 'public'}):
            raise ValueError('footer_readback_surface_invalid')
        if expected_url is None:
            raise ValueError('footer_readback_target_missing')
        if expected_url is not None and _target_identity(data['url']) != _target_identity(expected_url):
            raise ValueError('footer_readback_target_mismatch')
        stamp = datetime.fromisoformat(data['captured_at'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp > datetime.now(timezone.utc):
            raise ValueError('footer_readback_time_invalid')
        plan = data.get('production_plan')
        issues = validate_footer_selection(data, plan)
        if layout is not None and isinstance(plan, dict):
            cards = layout.get('footer_cards', {})
            planned = [link['url'] for link in plan.get('links', [])
                       if isinstance(link, dict) and link.get('presentation') == 'card']
            if (cards.get('decision') != ('include' if planned else 'omit')
                    or cards.get('urls') != planned):
                issues.append({'severity': 'error', 'code': 'footer_layout_plan_mismatch',
                               'message': 'フッター選定と採用layoutのカードが一致しません'})
        if issues:
            result.update(status='blocked', errors=[issue['code'] for issue in issues])
        else:
            raw = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
            result.update(status='ok', surface=surface,
                          hashes={'readback': hashlib.sha256(raw).hexdigest(),
                                  'article_draft': article_sha256})
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        result.update(status='blocked', errors=['footer_readback_missing_invalid_or_stale'])
    return result
