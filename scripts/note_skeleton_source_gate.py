"""本人骨組みと本文blockを同じ段落ID・出典へ束縛する。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple

import yaml
from markdown_it import MarkdownIt
from markdown_it.rules_inline.backticks import backtick


COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
PARAGRAPH_ID = re.compile(r"<!--\s*paragraph-id:\s*([a-z0-9][a-z0-9-]*)\s*-->")
PROVENANCE_COMMENT = re.compile(r"<!--\s*provenance-label:\s*[^>]*-->")
REF_LINE = re.compile(r"^(.*):(\d+)(?:-\d+)?$")
NPS_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
NPS_LINK_TARGET = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def _front_matter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            try:
                value = yaml.safe_load("\n".join(lines[1:end])) or {}
            except yaml.YAMLError:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def _quote_block(source: str, start_line: int) -> str:
    lines = source.splitlines()
    if start_line < 1 or start_line > len(lines):
        return ""
    result = []
    for line in lines[start_line - 1 :]:
        if not line.startswith(">"):
            break
        result.append(line[1:].removeprefix(" "))
    return "\n".join(result)


def _inside_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _load_author_paragraphs(skeleton: dict, episode_n: int = 5, generic_ids: bool = False) -> tuple[dict[str, dict], set[str], list[str]]:
    errors = []
    episodes = skeleton.get("episodes", []) if isinstance(skeleton, dict) else []
    if not isinstance(episodes, list):
        return {}, set(), ["author_skeleton: episodesは配列で指定してください"]
    episode = next((item for item in episodes if isinstance(item, dict) and item.get("n") == episode_n), None)
    if not episode:
        return {}, set(), [f"author_skeleton: episode {episode_n} がありません"]
    sections = episode.get("sections", [])
    if not isinstance(sections, list):
        return {}, set(), ["author_skeleton: sectionsは配列で指定してください"]
    paragraphs = {}
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("paragraphs", []), list):
            errors.append("author_skeleton: sections[].paragraphsの形式が不正です")
            continue
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, dict):
                errors.append("author_skeleton: paragraphの形式が不正です")
                continue
            paragraph_id = paragraph.get("id")
            is_author = paragraph.get("source") == "本人の発言"
            if not isinstance(paragraph_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*" if generic_ids else r"b5-p\d{3}", paragraph_id):
                if not is_author and not (isinstance(paragraph_id, str) and paragraph_id.startswith("b5-p")):
                    continue
                errors.append("author_skeleton: 本人発言にparagraph idがありません")
                continue
            if paragraph_id in paragraphs:
                errors.append(f"author_skeleton: paragraph id重複 {paragraph_id}")
                continue
            paragraphs[paragraph_id] = paragraph
    conclusion = episode.get("conclusion", {})
    if not isinstance(conclusion, dict):
        errors.append("author_skeleton conclusionの形式が不正です")
        conclusion = {}
    conclusion_ids = conclusion.get("paragraph_ids", []) if isinstance(conclusion, dict) else []
    if not isinstance(conclusion_ids, list) or any(not isinstance(item, str) for item in conclusion_ids):
        errors.append("author_skeleton conclusion: paragraph_idsの形式が不正です")
        conclusion_ids = []
    if "conclusion" in episode and not conclusion_ids:
        errors.append("author_skeleton conclusion: 明示したparagraph_idsは空にできません")
    for paragraph_id in conclusion_ids:
        if paragraph_id not in paragraphs or paragraphs[paragraph_id].get("source") != "本人の発言":
            errors.append(f"author_skeleton conclusion: {paragraph_id}は本人発言ではありません")
    return paragraphs, set(conclusion_ids), errors


def _source_errors(paragraph_id: str, paragraph: dict, root: Path) -> list[str]:
    errors = []
    text = paragraph.get("text")
    if not isinstance(text, str) or not text.strip():
        return [f"{paragraph_id}: 原文textは空白だけでない文字列が必要です"]
    actual_text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if paragraph.get("text_sha256") != actual_text_hash:
        errors.append(f"{paragraph_id}: text_sha256が原文textと一致しません")

    ref = paragraph.get("ref", "")
    match = REF_LINE.match(ref) if isinstance(ref, str) else None
    if not match:
        return errors + [f"{paragraph_id}: source refに保存本文のpath:lineがありません"]
    source_path = (root / match.group(1)).resolve()
    if not _inside_root(source_path, root):
        return errors + [f"{paragraph_id}: source refがrepo root外です"]
    try:
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return errors + [f"{paragraph_id}: source refの保存本文を読めません"]
    if paragraph.get("source_sha256") != hashlib.sha256(source_bytes).hexdigest():
        errors.append(f"{paragraph_id}: source_sha256が保存本文と一致しません")
    quote = _quote_block(source_text, int(match.group(2)))
    if not quote or text not in quote:
        errors.append(f"{paragraph_id}: 原文textがsource refの連続引用blockにありません")
    supporting_sources = paragraph.get("supporting_sources", [])
    if not isinstance(supporting_sources, list):
        errors.append(f"{paragraph_id}: supporting_sourcesは配列で指定してください")
        supporting_sources = []
    if ".supporting_sources[" in paragraph_id and supporting_sources:
        errors.append(f"{paragraph_id}: supporting_sourcesの入れ子は許可されません")
        supporting_sources = []
    for index, fragment in enumerate(supporting_sources, 1):
        if not isinstance(fragment, dict):
            errors.append(f"{paragraph_id}: supporting_sources[{index}]の形式が不正です")
            continue
        fragment_errors = _source_errors(f"{paragraph_id}.supporting_sources[{index}]", fragment, root)
        errors.extend(fragment_errors)
    edited = paragraph.get("edited_text")
    if edited is not None and (not isinstance(edited, str) or not edited.strip()):
        errors.append(f"{paragraph_id}: edited_textは空でない文字列か、省略してください")
    return errors


class HeadingSpan(NamedTuple):
    start: int
    end: int
    level: int
    title: str


def _markdown_line_offsets(text: str) -> list[int]:
    """Match CommonMark's CR, LF and CRLF lines without treating Unicode spaces as lines."""
    offsets = [0, *(match.end() for match in re.finditer(r"\r\n?|\n", text))]
    if offsets[-1] != len(text):
        offsets.append(len(text))
    return offsets


def _markdown_headings(text: str) -> list[HeadingSpan]:
    """Use the existing CommonMark parser for ATX/setext, excluding fenced code."""
    offsets = _markdown_line_offsets(text)
    tokens = MarkdownIt("commonmark").parse(text)
    return [HeadingSpan(offsets[token.map[0]], offsets[token.map[1]], int(token.tag[1:]),
                        "".join(child.content for child in (tokens[index + 1].children or [])
                                if child.type != "html_inline"))
            for index, token in enumerate(tokens)
            if token.type == "heading_open" and token.level == 0 and token.map is not None]


def _marker_end(text: str, start: int, headings: list[HeadingSpan]) -> int:
    ends = [m.start() for pattern in (PARAGRAPH_ID, PROVENANCE_COMMENT) for m in pattern.finditer(text, start)]
    heading = next((heading for heading in headings if heading.start >= start), None)
    if heading:
        ends.append(heading.start)
    return min(ends, default=len(text))


def _metadata_view(body: str) -> str:
    """Mask Markdown code blocks without moving real provenance-marker offsets."""
    offsets = _markdown_line_offsets(body)
    chars = list(body)
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(body)
    for token in tokens:
        if token.type not in {"fence", "code_block"} or token.map is None:
            continue
        for index in range(offsets[token.map[0]], offsets[token.map[1]]):
            if chars[index] not in "\r\n":
                chars[index] = " "
    inline_spans = []

    def capture_backtick(state, silent):
        start, count = state.pos, len(state.tokens)
        handled = backtick(state, silent)
        if not silent and len(state.tokens) > count and state.tokens[-1].type == "code_inline":
            inline_spans.append((start, state.pos))
        return handled

    parser.inline.ruler.at("backticks", capture_backtick)
    for token in tokens:
        if token.type != "inline" or token.map is None:
            continue
        start, end = offsets[token.map[0]], offsets[token.map[1]]
        inline_spans.clear()
        parser.inline.parse(body[start:end], parser, {}, [])
        for left, right in inline_spans:
            for index in range(start + left, start + right):
                if chars[index] not in "\r\n":
                    chars[index] = " "
    return "".join(chars)


def nps_body_character_count(text: str) -> int:
    """Keep body-line normalization while excluding CommonMark heading spans and refs."""
    _, body = _split_front_matter(text)
    body = COMMENT.sub("", body)
    headings = _markdown_headings(body)
    reference = next((heading for heading in headings
                      if re.match(r"(?:参考|出典|引用|参照)", heading.title)), None)
    if reference:
        body = body[:reference.start]
    total = 0
    offsets = _markdown_line_offsets(body)
    for start, end in zip(offsets, offsets[1:]):
        raw_line = body[start:end]
        if any(heading.start <= start < heading.end for heading in headings):
            continue
        line = raw_line.strip()
        if not line or line.startswith("---"):
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:]
        text_without_link_targets = NPS_LINK_TARGET.sub(r"\1", line)
        total += len(re.sub(r"\s", "", text_without_link_targets))
    return total


def _is_conclusion_heading(level: int, text: str) -> bool:
    terms = r"(?:総括|結論|まとめ|総論)"
    if level > 1:
        return bool(re.search(terms, text))
    # H1 is normally the article title. Treat it as a summary only when a
    # summary term is a heading label/suffix, not when it merely occurs in a
    # phrase such as 「結論を急がないための記事タイトル」.
    return bool(re.search(rf"(?:^|[｜|:：\s]){terms}(?:$|[｜|:：\s])", text)
                or re.search(rf"{terms}$", text))


def _draft_block_errors(body: str, paragraphs: dict[str, dict], conclusion_ids: set[str]) -> list[str]:
    errors = []
    headings = _markdown_headings(body)
    metadata = _metadata_view(body)
    markers = list(PARAGRAPH_ID.finditer(metadata))
    marker_ids = [marker.group(1) for marker in markers]
    if len(marker_ids) != len(set(marker_ids)):
        errors.append("本文: paragraph-idが重複しています")
    if conclusion_ids - set(marker_ids):
        errors.append("本文: author_skeleton conclusion paragraph-idが本文にありません")

    user_comments = [m for m in COMMENT.finditer(metadata) if re.search(r"provenance-label:\s*user-said\b", m.group())]
    if len(user_comments) != len(markers):
        errors.append("本文: user-saidコメントとparagraph-idの数が一致しません")
    for comment in user_comments:
        next_comment = next((m for m in COMMENT.finditer(metadata, comment.end())), None)
        limit = next_comment.start() if next_comment else len(body)
        marker = next((marker for marker in markers if comment.end() <= marker.start() <= limit), None)
        if marker is None:
            errors.append("本文: paragraph-idのないuser-said blockがあります")
        elif COMMENT.sub("", body[comment.end():marker.start()]).strip():
            errors.append("本文: user-said labelとparagraph-idの間に未対応の本文があります")

    spans = []
    for marker in markers:
        paragraph_id = marker.group(1)
        paragraph = paragraphs.get(paragraph_id)
        if paragraph is None or paragraph.get("source") != "本人の発言":
            errors.append(f"本文: {paragraph_id}は本人発言のsource blockではありません")
            continue
        preceding_labels = list(re.finditer(r"<!--\s*provenance-label:\s*([^;\s]+)", metadata[: marker.start()]))
        if not preceding_labels or preceding_labels[-1].group(1) != "user-said":
            errors.append(f"本文: {paragraph_id}に直前のuser-said provenance labelがありません")
        end = _marker_end(metadata, marker.end(), headings)
        actual = body[marker.end() : end].replace("\r\n", "\n").strip()
        expected = paragraph.get("edited_text", paragraph.get("text", ""))
        expected = expected.replace("\r\n", "\n").strip() if isinstance(expected, str) else ""
        if actual != expected:
            errors.append(f"本文: {paragraph_id}のblockがedited_text/textと一致しません")
        spans.append((marker.start(), end, paragraph_id))

    covered_conclusion_ids: set[str] = set()
    for heading in headings:
        level = heading.level
        direct_end = next((m.start for m in headings if m.start > heading.start), len(body))
        subtree_end = next(
            (m.start for m in headings if m.start > heading.start and m.level <= level), len(body)
        )
        direct_spans = [(a, b, pid) for a, b, pid in spans if heading.end <= a < direct_end]
        direct_ids = {pid for _, _, pid in direct_spans}
        subtree_spans = [(a, b, pid) for a, b, pid in spans if heading.end <= a < subtree_end]
        subtree_ids = {pid for _, _, pid in subtree_spans}
        explicit_conclusion = _is_conclusion_heading(level, heading.title.strip())
        contains_conclusion_ids = bool(direct_ids & conclusion_ids)
        if not (explicit_conclusion or contains_conclusion_ids):
            continue
        covered_conclusion_ids.update(subtree_ids & conclusion_ids)
        if conclusion_ids and subtree_ids - conclusion_ids:
            errors.append("総括: 結論以外のparagraph-idが本文blockに含まれています")
        for _, _, paragraph_id in subtree_spans:
            if paragraphs[paragraph_id].get("source") != "本人の発言":
                errors.append(f"総括: {paragraph_id}は本人の発言ではありません")
        visible = body[heading.end : subtree_end]
        for start, stop, _ in reversed(subtree_spans):
            visible = visible[: start - heading.end] + visible[stop - heading.end :]
        visible = COMMENT.sub("", visible)
        for nested in reversed(_markdown_headings(visible)):
            visible = visible[:nested.start] + visible[nested.end:]
        if visible.strip():
            errors.append("総括: paragraph-idで対応しないAI等の本文があります")
    if conclusion_ids - covered_conclusion_ids:
        errors.append("総括: 本人の結論paragraph-idが総括sectionにありません")
    return errors


def check_author_skeleton(draft_path: Path, text: str, root: Path) -> dict:
    """Validate B5 source hashes and paragraph-id-bound user blocks; legacy drafts stay optional."""
    offset, body = _split_front_matter(text)
    metadata = _front_matter(text)
    filename_b5 = bool(re.search(r"(?<![a-z0-9])b0?5(?![a-z0-9])", draft_path.stem, re.IGNORECASE))
    is_b5 = (metadata.get("episode") == 5 and str(metadata.get("series", "")).startswith("B")) or filename_b5
    binding = metadata.get("author_skeleton")
    required = is_b5 or metadata.get("source_mode") == "skeleton_first"
    if not required and not binding:
        return {"required": False, "status": "not_applicable", "errors": []}
    if is_b5 and metadata.get("source_mode") != "source_pack_locked_with_user_speech_priority":
        return {"required": True, "status": "blocked", "errors": ["B5: source_modeが対象の固定方式ではありません"]}
    if not isinstance(binding, str) or not binding.strip():
        return {"required": required, "status": "blocked", "errors": ["author_skeleton: 骨組みから本文へのbindingがありません"]}
    skeleton_path = (root / binding).resolve()
    if not _inside_root(skeleton_path, root):
        return {"required": required, "status": "blocked", "errors": ["author_skeletonがrepo root外です"]}
    try:
        skeleton = json.loads(skeleton_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"required": required, "status": "blocked", "errors": ["author_skeleton JSONを読めません"]}
    if not isinstance(skeleton, dict):
        return {"required": required, "status": "blocked", "errors": ["author_skeletonはJSON objectである必要があります"]}
    episode_n = 5 if is_b5 else metadata.get("episode")
    if type(episode_n) is not int or episode_n < 1:
        return {"required": required, "status": "blocked", "errors": ["author_skeleton: 対象episodeの整数指定が必要です"]}
    paragraphs, conclusion_ids, errors = _load_author_paragraphs(skeleton, episode_n, generic_ids=not is_b5)
    if is_b5 and not conclusion_ids and any(
            _is_conclusion_heading(heading.level, heading.title)
            for heading in _markdown_headings(body)):
        errors.append("B5: 明示総括のconclusion paragraph_idsが宣言されていません")
    if errors:
        return {"required": True, "status": "blocked", "errors": errors}
    episodes = skeleton.get("episodes", [])
    if not isinstance(episodes, list):
        episodes = []
    episode = next((item for item in episodes if isinstance(item, dict) and item.get("n") == episode_n), {})
    character_counts = episode.get("character_counts", {})
    if not isinstance(character_counts, dict):
        errors.append("author_skeleton: character_countsの形式が不正です")
        character_counts = {}
    if character_counts:
        expected_draft_hash = character_counts.get("draft_sha256")
        try:
            current_draft_hash = hashlib.sha256(draft_path.read_bytes()).hexdigest()
        except OSError:
            current_draft_hash = None
        if expected_draft_hash and expected_draft_hash != current_draft_hash:
            errors.append("author_skeleton: character_counts draft_sha256が対象本文と一致しません")
        for field in ("skeleton_paragraph_text_no_whitespace", "draft_body_no_whitespace"):
            if not isinstance(character_counts.get(field), int) or character_counts[field] < 0:
                errors.append(f"author_skeleton: character_counts.{field}がありません")
        actual_body_chars = nps_body_character_count(text)
        if character_counts.get("draft_body_no_whitespace") != actual_body_chars:
            errors.append("author_skeleton: draft_body_no_whitespaceがNPS本文字数と一致しません")
    else:
        actual_body_chars = None
    calculated_skeleton_chars = 0
    for section in episode.get("sections", []):
        for paragraph in section.get("paragraphs", []):
            raw_text = paragraph.get("text", "")
            if not isinstance(raw_text, str):
                errors.append("author_skeleton: paragraph textは文字列で指定してください")
                continue
            calculated_skeleton_chars += sum(not character.isspace() for character in raw_text)
    if character_counts and character_counts.get("skeleton_paragraph_text_no_whitespace") != calculated_skeleton_chars:
        errors.append("author_skeleton: 原文骨組み文字数がparagraph text合計と一致しません")
    for paragraph_id, paragraph in paragraphs.items():
        if paragraph.get("source") == "本人の発言":
            errors.extend(_source_errors(paragraph_id, paragraph, root))
    errors.extend(_draft_block_errors(body, paragraphs, conclusion_ids))
    author_ids = sum(paragraph.get("source") == "本人の発言" for paragraph in paragraphs.values())
    if not author_ids:
        errors.append("author_skeleton: 本人発言のsource paragraphがありません")
    if not any(paragraphs.get(marker.group(1), {}).get("source") == "本人の発言"
               for marker in PARAGRAPH_ID.finditer(_metadata_view(body))):
        errors.append("author_skeleton: 本文に対応する本人発言blockがありません")
    return {"required": required, "status": "blocked" if errors else "verified", "paragraph_ids": author_ids,
            "character_counts": {"draft_body": character_counts.get("draft_body_no_whitespace"),
                                 "draft_body_recomputed": actual_body_chars,
                                 "raw_skeleton": character_counts.get("skeleton_paragraph_text_no_whitespace"),
                                 "target": episode.get("target_chars")},
            "body_offset_lines": offset, "errors": errors}


def _split_front_matter(text: str) -> tuple[int, str]:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return index + 1, "".join(lines[index + 1 :])
    return 0, text


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="保存原文・骨組み・本文blockの対応を確認する。ラベルだけで著者性を認証しない。")
    parser.add_argument('draft', type=Path)
    parser.add_argument('--workspace-root', type=Path, required=True)
    args = parser.parse_args(argv)
    root, draft = args.workspace_root.resolve(strict=True), args.draft.resolve(strict=True)
    if not draft.is_relative_to(root):
        parser.error('draftは利用者workspace内に置いてください')
    result = check_author_skeleton(draft, draft.read_text(encoding='utf-8-sig'), root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
