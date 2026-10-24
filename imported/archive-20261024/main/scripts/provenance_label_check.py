#!/usr/bin/env python3
"""Validate provenance labels for source-pack locked Note drafts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


TARGET_SOURCE_MODE = "source_pack_locked_with_user_speech_priority"
ALLOWED_LABELS = {
    "user-said",
    "external-fact",
    "assistant-organized",
    "hold",
}
REQUIRED_LABELS = {"user-said", "external-fact", "assistant-organized"}

SOURCE_HINTS = {
    "user-said": (
        "user",
        "speech",
        "transcript",
        "confirmed",
        "conversation",
        "current-conversation",
    ),
    "external-fact": ("external", "official", "public", "source_pack", "source-pack"),
    "assistant-organized": ("assistant", "structure", "synthesis", "transition", "outline"),
    "hold": ("hold", "unresolved", "needs_review", "needs-review"),
}

LABEL_RE = re.compile(
    r"^\s*(?:"
    r"<!--\s*provenance-label:\s*(?P<html_label>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<html_source>[^;>]+?))?\s*--!?>"
    r"|"
    r"\[provenance-label:\s*(?P<bracket_label>[a-z-]+)"
    r"(?:\s*;\s*source:\s*(?P<bracket_source>[^\]]+))?\]"
    r")\s*$"
)

USER_SPEECH_CUE_RE = re.compile(
    r"(僕|私|ユーザー(?:が|は|曰く)|本人(?:が|は)|体験|user said|user-said)",
    re.I,
)
HOLD_CUE_RE = re.compile(r"(hold|保留|未確認|要確認|追加確認|needs[-_ ]review|unresolved)", re.I)


@dataclass(frozen=True)
class Block:
    label: str
    source: str
    line: int
    text: str
    review: str = ""
    heading: str = ""
    quote: str = ""


MULTILINE_LABEL_RE = re.compile(
    r"^\s*<!--\s*provenance\s*\n(?P<meta>.*?)\n\s*--!?>\s*$",
    re.M | re.S,
)
PROVENANCE_COMMENT_RE = re.compile(
    r"^\s*<!--\s*(?:provenance-label:.*?--!?>|provenance\s*\n.*?\n\s*--!?>)\s*$",
    re.M | re.S,
)


def split_frontmatter(text: str) -> tuple[dict[str, object], str, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 1

    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text, 1

    frontmatter = parse_simple_yaml(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    body_start_line = end + 2
    return frontmatter, body, body_start_line


def parse_simple_yaml(lines: list[str]) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith(" ") and ":" in raw:
            key, value = raw.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if value == "":
                data[current_key] = []
            elif value.lower() in {"true", "false"}:
                data[current_key] = value.lower() == "true"
            else:
                data[current_key] = value.strip("\"'")
            continue
        if current_key and raw.strip().startswith("- "):
            existing = data.setdefault(current_key, [])
            if isinstance(existing, list):
                existing.append(raw.strip()[2:].strip("\"'"))
    return data


def parse_blocks(body: str, start_line: int) -> tuple[list[Block], list[dict[str, object]]]:
    blocks: list[Block] = []
    findings: list[dict[str, object]] = []
    current_label: str | None = None
    current_source = ""
    current_review = ""
    current_start = start_line
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_label, current_source, current_review, current_start
        text = "\n".join(current_lines).strip()
        if text and current_label:
            heading = ""
            quote = ""
            for content_line in text.splitlines():
                stripped = content_line.strip()
                if not heading and re.match(r"^#{1,6}\s+", stripped):
                    heading = re.sub(r"^#{1,6}\s+", "", stripped)
                elif stripped and not stripped.startswith("#"):
                    quote = stripped[:80]
                    break
            blocks.append(
                Block(
                    label=current_label,
                    source=current_source.strip(),
                    line=current_start,
                    text=text,
                    review=current_review.strip(),
                    heading=heading,
                    quote=quote,
                )
            )
        elif text and not all(
            not line.strip() or re.match(r"^#\s+\S", line.strip())
            for line in text.splitlines()
        ):
            findings.append(
                {
                    "severity": "error",
                    "code": "unlabeled_content",
                    "line": current_start,
                    "message": "Content appears before a provenance label.",
                }
            )
        current_lines = []

    lines = body.splitlines()
    offset = 0
    while offset < len(lines):
        line = lines[offset]
        line_no = start_line + offset
        match = LABEL_RE.match(line)
        consumed = 1
        metadata: dict[str, str] = {}
        if not match and re.match(r"^\s*<!--\s*provenance\s*$", line):
            comment_lines = [line]
            cursor = offset + 1
            while cursor < len(lines):
                comment_lines.append(lines[cursor])
                if re.match(r"^\s*--!?>\s*$", lines[cursor]):
                    break
                cursor += 1
            comment = "\n".join(comment_lines)
            multiline = MULTILINE_LABEL_RE.match(comment)
            if multiline:
                for raw in multiline.group("meta").splitlines():
                    if ":" in raw:
                        key, value = raw.split(":", 1)
                        metadata[key.strip()] = value.strip()
                consumed = len(comment_lines)
        if match:
            flush()
            current_label = match.group("html_label") or match.group("bracket_label") or ""
            current_source = match.group("html_source") or match.group("bracket_source") or ""
            current_review = ""
            current_start = line_no + 1
        elif metadata:
            flush()
            current_label = metadata.get("kind", "")
            current_source = metadata.get("source", "")
            current_review = metadata.get("review", "")
            current_start = line_no + consumed
        else:
            current_lines.append(line)
        if (match or metadata) and current_label not in ALLOWED_LABELS:
            findings.append(
                {
                    "severity": "error",
                    "code": "unknown_label",
                    "line": line_no,
                    "message": f"Unknown provenance label: {current_label}",
                }
            )
        offset += consumed
    flush()
    return blocks, findings


def strip_provenance_comments(text: str) -> str:
    """Remove local provenance metadata before producing a public-body candidate."""
    return re.sub(r"\n{3,}", "\n\n", PROVENANCE_COMMENT_RE.sub("", text)).strip() + "\n"


def source_hint_matches(label: str, source: str) -> bool:
    normalized = source.lower().replace(" ", "_")
    return any(hint in normalized for hint in SOURCE_HINTS[label])


def validate_blocks(blocks: list[Block]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    present = {block.label for block in blocks if block.label in ALLOWED_LABELS}
    for missing in sorted(REQUIRED_LABELS - present):
        findings.append(
            {
                "severity": "error",
                "code": "missing_required_label",
                "label": missing,
                "message": f"Required provenance label is missing: {missing}",
            }
        )

    for block in blocks:
        if block.label not in ALLOWED_LABELS:
            continue
        if not block.source:
            findings.append(
                {
                    "severity": "error",
                    "code": "missing_source_hint",
                    "line": block.line,
                    "label": block.label,
                    "message": "Provenance label must include a compatible source hint.",
                }
            )
        elif not source_hint_matches(block.label, block.source):
            findings.append(
                {
                    "severity": "error",
                    "code": "source_hint_mismatch",
                    "line": block.line,
                    "label": block.label,
                    "source": block.source,
                    "message": "Source hint does not match the provenance label boundary.",
                }
            )

        if block.label == "external-fact" and USER_SPEECH_CUE_RE.search(block.text):
            findings.append(
                {
                    "severity": "error",
                    "code": "user_speech_inside_external_fact",
                    "line": block.line,
                    "label": block.label,
                    "message": "User speech cue appears inside an external-fact block.",
                }
            )
        if block.label == "hold" and not HOLD_CUE_RE.search(block.text):
            findings.append(
                {
                    "severity": "error",
                    "code": "hold_without_review_cue",
                    "line": block.line,
                    "label": block.label,
                    "message": "Hold block must keep an explicit review or unresolved cue.",
                }
            )
        if block.label == "hold":
            findings.append(
                {
                    "severity": "error",
                    "code": "hold_present",
                    "line": block.line,
                    "label": block.label,
                    "message": "Hold block requires human review before public-body export.",
                }
            )
    return findings


def check_draft(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, body_start_line = split_frontmatter(text)
    source_mode = str(frontmatter.get("source_mode") or "")
    if source_mode != TARGET_SOURCE_MODE:
        return {
            "draft": str(path),
            "ok": True,
            "overall": "skipped",
            "reason": "source_mode_not_targeted",
            "source_mode": source_mode or "unknown",
            "findings": [],
            "labels_seen": [],
            "external_actions_performed": [],
            "publication_actions_performed": [],
        }

    blocks, findings = parse_blocks(body, body_start_line)
    findings.extend(validate_blocks(blocks))
    labels_seen = sorted({block.label for block in blocks if block.label in ALLOWED_LABELS})
    return {
        "draft": str(path),
        "ok": not findings,
        "overall": "ok" if not findings else "error",
        "source_mode": source_mode,
        "labels_seen": labels_seen,
        "block_count": len(blocks),
        "publication_ready": not findings and not any(
            block.label == "hold" for block in blocks
        ),
        "blocks": [
            {
                "kind": block.label,
                "source": block.source,
                "review": block.review,
                "line": block.line,
                "heading": block.heading,
                "quote": block.quote,
            }
            for block in blocks
        ],
        "findings": findings,
        "external_actions_performed": [],
        "publication_actions_performed": [],
    }


# Conversation fidelity is an opt-in workspace contract, independent of draft mode.
def conversation_units(messages: list[dict]) -> list[dict]:
    """全user発言を空行単位に分ける。執筆者による抜粋は行わない。"""
    units = []
    for message in messages:
        if message.get('role') == 'user':
            for index, quote in enumerate(re.split(r'\n\s*\n', message['text'].strip())):
                if quote.strip():
                    units.append({'id': f"{message['id']}:p{index + 1}", 'quote': quote.strip()})
    return units


def capture_conversation(log: Path, conversation_id: str, article_id: str,
                         *, prefix: bytes | None = None) -> dict:
    """指定したローカルCodex記録の実在prefixを固定。tool出力は素材にしない。"""
    import hashlib
    raw = log.read_bytes() if prefix is None else prefix
    messages, found_id = [], None
    for line in raw.splitlines():
        item = json.loads(line)
        payload = item.get('payload', {})
        if item.get('type') == 'session_meta':
            found_id = payload.get('id')
        if item.get('type') != 'response_item' or payload.get('type') != 'message':
            continue
        role = payload.get('role')
        if role not in ('user', 'assistant'):
            continue
        text = '\n'.join(part.get('text', '') for part in payload.get('content', [])
                         if part.get('type') in ('input_text', 'output_text', 'text'))
        if role == 'user' and '## My request:' in text:
            text = text.split('## My request:', 1)[1].strip()
        if not text.strip() or text.startswith(('# AGENTS.md instructions', '<external_codex_apps_open_page>')):
            continue
        messages.append({'id': f'm{len(messages) + 1:04d}', 'role': role, 'text': text.strip()})
    if found_id != conversation_id or not any(m['role'] == 'user' for m in messages):
        raise ValueError('会話ID不一致または本人発言なし')
    return {'schema_version': 'note-conversation-source/v1', 'conversation_id': conversation_id,
            'article_id': article_id, 'capture': {'log_path': str(log.resolve()),
            'byte_length': len(raw), 'prefix_sha256': hashlib.sha256(raw).hexdigest()},
            'messages': messages}


def fidelity_paragraphs(text: str) -> list[str]:
    """見出し・表・リンクを含め、公開本文の全段落を検査対象にする。"""
    _, body, _ = split_frontmatter(text)
    body = strip_provenance_comments(body)
    return [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]


def fidelity_mapping_digest(mapping: dict) -> str:
    """レビュー自体への参照を除き、分類・省略理由・更新関係をレビュー版へ束縛。"""
    import hashlib
    content = {k: v for k, v in mapping.items() if k not in ('review_path', 'review_sha256')}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def check_conversation_fidelity(draft: Path, policy: dict | None, article_id: str,
                                conversation_id: str | None = None) -> dict:
    """構造・原文・全発言対応と独立意味レビューを分離して照合する。"""
    import hashlib
    errors = []
    result = {'status': 'not_required', 'errors': errors, 'hashes': {},
              'semantic_review': 'not_recorded', 'human_adoption_verified': False}
    if not policy or not policy.get('required'):
        return result
    result['status'] = 'blocked'
    captured = {}
    def read(path):
        path = Path(path).resolve(strict=True)
        raw = path.read_bytes()
        captured[path] = raw
        return raw
    def digest(raw):
        return hashlib.sha256(raw).hexdigest()
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)
    try:
        require(policy.get('schema') == 'note-conversation-fidelity-policy/v1', '会話忠実性policy不正')
        source_path = Path(policy['source'])
        source_raw = read(source_path)
        require(digest(source_raw) == policy['sha256'], '全文原資料の版不一致')
        source = json.loads(source_raw)
        require(source.get('schema_version') == 'note-conversation-source/v1'
                and source.get('article_id') == article_id, '全文原資料の対象不一致')
        require(conversation_id is not None and source.get('conversation_id') == conversation_id,
                '現在の会話IDと原資料が不一致')
        capture = source['capture']
        log = Path(capture['log_path']).resolve(strict=True)
        size = capture['byte_length']
        require(type(size) is int and size > 0, '会話記録範囲不正')
        with log.open('rb') as handle:
            prefix = handle.read(size)
        require(digest(prefix) == capture['prefix_sha256'], '会話記録prefix不一致')
        reconstructed = capture_conversation(log, source['conversation_id'], article_id, prefix=prefix)
        require(reconstructed == source, '全文原資料が会話記録と一致しない・選択抜粋')
        current = capture_conversation(log, conversation_id, article_id)
        user_turns = lambda value: [(m['id'], m['text']) for m in value['messages'] if m['role'] == 'user']
        require(user_turns(current) == user_turns(source), '最新の本人発言が未反映。原資料を再取得する必要')
        draft_raw = read(draft)
        paragraphs = fidelity_paragraphs(draft_raw.decode('utf-8'))
        mapping_path = draft.with_suffix('.fidelity.json')
        mapping_raw = read(mapping_path)
        mapping = json.loads(mapping_raw)
        require(mapping.get('schema_version') == 'note-conversation-fidelity/v1'
                and mapping.get('article_id') == article_id, '会話対応表の対象不一致')
        require(mapping.get('source_sha256') == digest(source_raw)
                and mapping.get('draft_sha256') == digest(draft_raw), '会話対応表の版不一致')
        units = conversation_units(source['messages'])
        by_id = {u['id']: u for u in units}
        order = {u['id']: i for i, u in enumerate(units)}
        coverage = mapping['source_coverage']
        require(isinstance(coverage, list) and len(coverage) == len(units)
                and {r['unit_id'] for r in coverage} == set(by_id), '本人発言の未分類・重複')
        superseded = set()
        for row in coverage:
            unit_id = row['unit_id']
            require(row.get('quote') == by_id[unit_id]['quote'], '本人原文引用の不一致')
            require(isinstance(row.get('reason'), str) and row['reason'].strip(), '発言の取扱理由なし')
            disposition = row.get('disposition')
            require(disposition in ('represented', 'omitted', 'superseded'), '発言の取扱不正')
            if disposition == 'represented':
                quotes = row.get('draft_quotes', [])
                require(quotes and all(q and any(q in p for p in paragraphs) for q in quotes), '発言の反映先が本文にない')
            elif disposition == 'superseded':
                later = row.get('superseded_by')
                require(later in by_id and order[later] > order[unit_id], '最新説明への更新先不正')
                superseded.add(unit_id)
        blocks = mapping['blocks']
        require(isinstance(blocks, list) and len(blocks) == len(paragraphs)
                and [b.get('index') for b in blocks] == list(range(len(paragraphs))), '本文段落の未分類・抱き合わせ')
        for block, paragraph in zip(blocks, paragraphs):
            require(block.get('text') == paragraph, '本文段落の原文不一致')
            kind = block.get('kind')
            require(kind in ('user-said', 'external-fact', 'assistant-organized', 'hold'), '本文由来不正')
            require(kind != 'hold', '未採用のAI追加または意味変化が残っている')
            require(isinstance(block.get('reason'), str) and block['reason'].strip(), '本文の意味対応説明なし')
            refs = block.get('source_refs', [])
            if kind == 'user-said':
                require(refs, '本人判断の原発言なし')
            for ref in refs:
                require(ref.get('unit_id') in by_id and ref['unit_id'] not in superseded,
                        '本人発言でない参照または失効した旧説明を使用')
                require(isinstance(ref.get('quote'), str) and ref['quote'].strip()
                        and ref['quote'] in by_id[ref['unit_id']]['quote'], '本文の本人引用が原資料にない')
            if kind == 'external-fact':
                evidence = block.get('external_sources', [])
                require(evidence and all(isinstance(e, str) and e.startswith('https://') for e in evidence), '外部事実の出典なし')
            elif kind == 'assistant-organized':
                require(refs or block.get('structure_only') is True, 'AI整理の接続元なし')
            assistant_refs = block.get('assistant_refs', [])
            require(kind != 'user-said' or not assistant_refs, 'assistant発言を本人判断の根拠に使用')
            message_by_id = {message['id']: message for message in source['messages']}
            for ref in assistant_refs:
                message = message_by_id.get(ref.get('message_id'))
                require(message is not None and message['role'] == 'assistant'
                        and isinstance(ref.get('quote'), str) and ref['quote'].strip()
                        and ref['quote'] in message['text'], 'AI説明の引用と帰属が不一致')
        review_path = Path(mapping['review_path'])
        if not review_path.is_absolute():
            review_path = mapping_path.parent / review_path
        review_raw = read(review_path)
        require(digest(review_raw) == mapping['review_sha256'], '独立意味レビューの版不一致')
        review = json.loads(review_raw)
        require(review.get('mapping_sha256') == fidelity_mapping_digest(mapping), '独立意味レビュー後に対応表が変更')
        require(review.get('draft_sha256') == digest(draft_raw)
                and review.get('source_sha256') == digest(source_raw), '独立意味レビューの対象不一致')
        require(review.get('reviewer_id') and mapping.get('writer_id')
                and review['reviewer_id'] != mapping['writer_id'], '執筆者の自己申告は独立レビューではない')
        source_results = review['source_results']
        require(len(source_results) == len(units) and {r['unit_id'] for r in source_results} == set(by_id), '独立レビューの発言網羅不足')
        block_results = review['block_results']
        require(len(block_results) == len(blocks) and [r['index'] for r in block_results] == list(range(len(blocks))), '独立レビューの段落網羅不足')
        require(all(r.get('verdict') == 'supported' and isinstance(r.get('reason'), str) and r['reason'].strip()
                    for r in source_results + block_results), '独立意味レビューで欠落・意味変化・未発言追加あり')
        require(all(path.read_bytes() == raw for path, raw in captured.items()), '検査中に原資料・本文・対応表・レビューが変更')
        result.update(status='mechanical_ok', semantic_review='independent_review_recorded',
                      source_unit_count=len(units), paragraph_count=len(blocks),
                      hashes={'draft': digest(draft_raw), 'source': digest(source_raw),
                              'mapping': digest(mapping_raw), 'review': digest(review_raw)},
                      authenticity_notice='意味の一致とレビュー実行の真正性は機械だけでは保証しない。実際の担当結果を呼出元が回収する。')
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, AttributeError, IndexError) as exc:
        errors.append(str(exc))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--public-output",
        type=Path,
        help="検査が通った場合だけ、由来コメントを除いた公開本文候補を書き出す。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check_draft(args.draft)
    if args.public_output and result["ok"] and result.get("publication_ready"):
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        _, public_body, _ = split_frontmatter(args.draft.read_text(encoding="utf-8"))
        args.public_output.write_text(
            strip_provenance_comments(public_body),
            encoding="utf-8",
            newline="\n",
        )
        result["public_output"] = str(args.public_output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"overall={result['overall']}")
        print(f"source_mode={result['source_mode']}")
        print("external_actions_performed=0")
        print("publication_actions_performed=0")
    else:
        print("overall=error")
        for finding in result["findings"]:
            line = f":{finding.get('line')}" if finding.get("line") else ""
            print(f"error:{finding['code']}{line} {finding['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
