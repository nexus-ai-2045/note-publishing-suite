#!/usr/bin/env python3
"""Validate live Note editor line-break structure before draft save."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def resolve_policy(style: dict, article_id: str | None = None, *, require_article_id: bool = False) -> dict | None:
    """Inherit the author's policy; an article cannot weaken an enabled rule."""
    if not isinstance(style, dict):
        raise ValueError("style must be an object")
    profiles = style.get("article_profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("article_profiles must be an object")
    any_policy = "linebreak_policy" in style or any(
        isinstance(value, dict) and "linebreak_policy" in value for value in profiles.values())
    if require_article_id and any_policy and (not isinstance(article_id, str) or not article_id.strip()):
        raise ValueError("article-id is required to resolve the adopted linebreak policy")
    article = profiles.get(article_id, {})
    policies = []
    for owner in (style, article if isinstance(article, dict) else {}):
        if "linebreak_policy" not in owner:
            continue
        value = owner["linebreak_policy"]
        if (not isinstance(value, dict) or value.get("schema") != "nps-linebreak-policy/v1"
                or type(value.get("after_kuten")) is not bool):
            raise ValueError("linebreak_policy must declare schema and boolean after_kuten")
        policies.append(value)
    if not policies:
        return None
    return {"schema": "nps-linebreak-policy/v1",
            "after_kuten": any(value["after_kuten"] for value in policies)}


def missing_kuten_breaks(text: str) -> list[int]:
    """A paragraph end is a boundary; closing quotes belong to the sentence."""
    missing = []
    closers = '」』）】〉》〕］｝”’"\'_*~'
    for match in re.finditer("。", text):
        end = match.end()
        while end < len(text) and text[end] in closers:
            end += 1
        while end < len(text) and text[end] in " \t\r":
            end += 1
        if end < len(text) and text[end] != "\n":
            missing.append(match.start())
    return missing


def validate_draft(text: str, policy: dict | None = None) -> dict:
    """Inspect actual Markdown, rather than trusting a dropped frontmatter flag."""
    lines = text.lstrip("\ufeff").splitlines()
    metadata = ""
    offset = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            return {"ok": False, "issues": [issue("linebreak_frontmatter_invalid", "front matterが閉じていません")]}
        metadata = "\n".join(lines[1:end])
        offset = end + 1
    declared = bool(re.search(r"(?m)^\s+linebreak_after_kuten:\s*true\s*$", metadata))
    required = declared or bool(policy and policy["after_kuten"])
    result = {"ok": True, "required": required, "draft_sha256": hashlib.sha256(text.encode()).hexdigest(), "issues": []}
    if not required:
        return result
    fence = None
    for index, line in enumerate(lines[offset:], offset + 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence or re.match(r"^\s{0,3}#{1,6}\s", line):
            continue
        # A code example may contain full stops; it is not author prose.
        prose = re.sub(r"(`+)(.+?)\1", lambda m: m.group().replace("。", "\ufffc"), line)
        # Link destinations and delimiters are not visible prose. Keep labels so
        # a following visible sentence still requires its own soft break.
        prose = re.sub(r"!?\[([^]\n]*)\]\((?:[^()\n]|\([^()\n]*\))*\)", r"\1", prose)
        prose = re.sub(r"https?://[^\s<>。）」』】]+", lambda m: m.group().replace("。", "\ufffc"), prose)
        if missing_kuten_breaks(prose):
            result["issues"].append(issue("kuten_linebreak_missing", f"本文{index}行: 句点の後に次の文が同じ行で続いています"))
    if fence:
        result["issues"].append(issue("linebreak_code_fence_unclosed", "閉じていないコード囲みは本文除外に使えません"))
    result["ok"] = not result["issues"]
    return result


class _Paragraphs(HTMLParser):
    """Read live visible paragraph lines, including nested emphasis and links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.current: list[str] | None = None
        self.parents: list[list[str]] = []
        self.hidden = 0
        self.code = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"table-of-contents", "iframe", "pre", "script", "style"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag == "code":
            self.code += 1
        if tag in {"p", "li"}:
            if self.current is not None:
                if "".join(self.current).strip():
                    self.blocks.append("".join(self.current))
                self.parents.append([])
            self.current = []
        if tag == "br" and self.current is not None:
            if "ProseMirror-trailingBreak" not in dict(attrs).get("class", ""):
                self.current.append("\n")

    def handle_endtag(self, tag):
        if tag in {"table-of-contents", "iframe", "pre", "script", "style"}:
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == "code":
            self.code = max(0, self.code - 1)
        if tag in {"p", "li"} and self.current is not None:
            if "".join(self.current).strip():
                self.blocks.append("".join(self.current))
            self.current = self.parents.pop() if self.parents else None

    def handle_data(self, text):
        if not self.hidden and self.current is not None:
            # HTML source whitespace does not produce a Shift+Enter break.
            text = re.sub(r"[\t\n\r\f ]+", " ", text)
            self.current.append(text.replace("。", "\ufffc") if self.code else text)


def validate_live_html(body_html: object, policy: dict | None) -> dict:
    required = bool(policy and policy["after_kuten"])
    result = {"ok": True, "required": required, "issues": []}
    if not required:
        return result
    if not isinstance(body_html, str) or not body_html.strip():
        return {**result, "ok": False, "issues": [issue("linebreak_body_html_missing", "採用規則の検査には現在の本文HTMLが必要です")]}
    parser = _Paragraphs()
    parser.feed(body_html)
    parser.close()
    visible = [block for block in parser.blocks if block.strip()]
    if not visible:
        result["issues"].append(issue("linebreak_body_html_empty", "検査可能な本文段落がありません"))
    for i, block in enumerate(visible, 1):
        if missing_kuten_breaks(block):
            result["issues"].append(issue("kuten_linebreak_missing", f"Note本文の段落{i}: 句点の後に改行がありません"))
    trailing = sum(block.rstrip(" \t\r").endswith("\n") for block in visible)
    if trailing:
        result["issues"].append(issue("trailing_plain_br", "本文HTMLの段落末尾に不要なbrが残っています"))
    result.update(ok=not result["issues"], body_html_sha256=hashlib.sha256(body_html.encode()).hexdigest(),
                  trailing_plain_br_count=trailing,
                  paragraph_soft_break_counts=[block.count("\n") for block in visible])
    return result


def validate(data: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if data.get("article_lane") not in {"production_candidate", "continuation_article"} and not data.get("linebreak_policy"):
        return errors, warnings

    trailing = data.get("trailing_plain_br_count")
    consecutive_empty = data.get("consecutive_empty_paragraph_count")
    literal_backslash = data.get("literal_backslash_linebreak_count")
    empty = data.get("empty_paragraph_count")
    empty_before_figure = data.get("empty_paragraph_before_figure_count")
    multi = data.get("paragraphs_with_multiple_plain_br_count")

    if trailing != 0:
        errors.append(issue("trailing_plain_br", "文字の末尾に不要な通常brが残っています"))
    if consecutive_empty != 0:
        errors.append(issue("consecutive_empty_paragraphs", "空段落が連続しています"))
    if literal_backslash != 0:
        errors.append(issue("literal_backslash_linebreak", "改行の代わりにバックスラッシュが表示されています"))
    if not isinstance(empty, int) or empty < 0:
        errors.append(issue("empty_paragraph_count_missing", "空段落数の実測が必要です"))
    elif empty > 0:
        warnings.append(issue("empty_paragraphs_review", f"単独の空段落が{empty}件あります。画像・埋め込み周辺か目視確認してください"))
    if not isinstance(empty_before_figure, int) or empty_before_figure < 0:
        errors.append(
            issue(
                "empty_paragraph_before_figure_count_missing",
                "図の直前にある空段落数の実測が必要です",
            )
        )
    elif empty_before_figure > 0:
        errors.append(
            issue(
                "empty_paragraph_before_figure",
                f"図の直前に空段落が{empty_before_figure}件あります",
            )
        )
    if isinstance(multi, int) and multi > 0:
        warnings.append(issue("multiple_linebreaks_review", f"段落内に複数の通常brを含む段落が{multi}件あります。意図した読みやすさ調整か確認してください"))
    if any(field in data for field in ("expected_paragraph_soft_break_counts", "paragraph_soft_break_counts")):
        expected = data.get("expected_paragraph_soft_break_counts")
        observed = data.get("paragraph_soft_break_counts")
        structure_valid = True
        for field, counts in (
            ("expected_paragraph_soft_break_counts", expected),
            ("paragraph_soft_break_counts", observed),
        ):
            if not isinstance(counts, list) or any(
                type(count) is not int or count < 0 for count in counts
            ):
                structure_valid = False
                errors.append(issue(f"{field}_invalid", f"{field}は本文段落順の0以上の整数配列で指定してください"))
        if structure_valid and observed != expected:
            errors.append(issue("source_paragraph_structure_mismatch", "本文の段落境界または段落内改行が原稿の期待構造と一致しません"))
    policy = data.get("linebreak_policy")
    if policy is not None:
        try:
            policy = resolve_policy({"linebreak_policy": policy})
            live = validate_live_html(data.get("body_html"), policy)
            errors.extend(live["issues"])
            expected = data.get("expected_paragraph_soft_break_counts")
            if policy["after_kuten"] and expected is not None and expected != live.get("paragraph_soft_break_counts"):
                errors.append(issue("source_paragraph_structure_mismatch", "本文HTMLの実改行が原稿の期待構造と一致しません"))
        except ValueError as exc:
            errors.append(issue("linebreak_policy_invalid", str(exc)))
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observation", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--settings", type=Path, help="採用済み著者設定から規則を継承する")
    parser.add_argument("--article-id")
    args = parser.parse_args()
    data = json.loads(args.observation.read_text(encoding="utf-8"))
    if args.settings is not None:
        spec = importlib.util.spec_from_file_location("_linebreak_workflow", Path(__file__).with_name("note_workflow_gate.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected, _ = module.read_workspace_settings(args.settings, args.article_id or "")
        if expected.get("linebreak_policy"):
            data["linebreak_policy"] = expected["linebreak_policy"]
    errors, warnings = validate(data)
    payload = {
        "ok": not errors,
        "ready_for_draft_save": not errors,
        "issues": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
