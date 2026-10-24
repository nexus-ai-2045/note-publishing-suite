"""生成した各話ページが骨組み JSON と一致するかを確かめる。
段落の文・出どころ・どこから・主張の種類・確認の状態・通し番号・色の帯の並びを全部突き合わせる。"""
import argparse
import html
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

PLAN_KINDS = {
    'author-position': '本人の考え', 'accepted-response': '同意した返答',
    'research': '調べて説明すること', 'open-question': '答えを出していない疑問',
}


def validate_writing_plans(data):
    """構造と参照のみ検査する。同意記録の真正性・意味は独立レビューが必要。"""
    required = isinstance(data, dict) and data.get('skeleton_mode') == 'writing-plan'
    episodes = data['episodes'] if isinstance(data, dict) else data
    for ep in episodes:
        for section in ep['sections']:
            plan = section.get('writing_plan')
            if plan is None and not required and 'writing_plan' not in section:
                continue
            if not isinstance(plan, dict) or not isinstance(plan.get('items'), list) or not plan['items']:
                raise ValueError('writing_plan.itemsには空でない一覧が必要です')
            ids = [p.get('id') for p in section['paragraphs']]
            seen = set()
            for item in plan['items']:
                if not isinstance(item, dict) or item.get('kind') not in PLAN_KINDS:
                    raise ValueError('writing_planのkindが無効です')
                if not isinstance(item.get('text'), str) or not item['text'].strip():
                    raise ValueError('writing_planのtextが必要です')
                basis = item.get('basis')
                if (not isinstance(basis, list) or not basis
                        or any(not isinstance(ref, str) or not ref or ids.count(ref) != 1 for ref in basis)
                        or len(set(basis)) != len(basis)):
                    raise ValueError('writing_plan.basisには節内の一意なparagraph idが必要です')
                basis_sources = {p.get('source') for p in section['paragraphs'] if p.get('id') in basis}
                if item['kind'] in ('author-position', 'open-question', 'research'):
                    if '本人の発言' not in basis_sources:
                        raise ValueError('本人の考え・疑問・調査依頼には本人の発言basisが必要です')
                    if item['kind'] == 'author-position' and 'AIの案' in basis_sources:
                        raise ValueError('AIの案を根拠に含む本人の考えはaccepted-responseとadoptionで記録してください')
                key = (item['kind'], item['text'])
                if key in seen:
                    raise ValueError('writing_planのitemが重複しています')
                seen.add(key)
                adoption = item.get('adoption')
                if item['kind'] == 'accepted-response' or 'adoption' in item:
                    if not isinstance(adoption, dict) or any(
                        not isinstance(adoption.get(field), str) or not adoption[field].strip()
                        for field in ('user_message_id', 'user_quote', 'assistant_message_id', 'scope')
                    ):
                        raise ValueError('同意した返答にはadoptionの記録が必要です')
                    users = [p for p in section['paragraphs'] if p.get('source') == '本人の発言'
                             and p.get('message_id') == adoption['user_message_id']
                             and adoption['user_quote'] in p.get('text', '') and p.get('id') in basis]
                    replies = [p for p in section['paragraphs'] if p.get('source') == 'AIの案'
                               and p.get('message_id') == adoption['assistant_message_id']
                               and p.get('id') in basis]
                    if len(users) != 1 or len(replies) != 1:
                        raise ValueError('adoptionは根拠に含む本人とAIの実発言に一致する必要があります')
                urls = item.get('external_sources', [])
                if not isinstance(urls, list):
                    raise ValueError('external_sourcesはHTTPS URLの一覧が必要です')
                for url in urls:
                    try:
                        parsed = urlsplit(url) if isinstance(url, str) else None
                        valid = (parsed and parsed.scheme == 'https' and parsed.hostname
                                 and parsed.username is None and parsed.password is None
                                 and not any(c.isspace() or ord(c) < 32 for c in url)
                                 and '\\' not in url)
                        if parsed:
                            parsed.port
                    except ValueError:
                        valid = False
                    if not valid:
                        raise ValueError('external_sourcesは認証情報のないHTTPS URLに限定します')


def writing_plan_html(section):
    """保存された計画を全項目表示し、原文の折り畳みとは区別する。"""
    plan = section.get('writing_plan')
    if plan is None:
        return ''
    rows = []
    for item in plan['items']:
        urls = ''.join(f'<li><a href="{html.escape(url, quote=True)}" rel="noreferrer">{html.escape(url)}</a></li>'
                       for url in item.get('external_sources', []))
        adoption = item.get('adoption')
        receipt = ''
        if adoption:
            receipt = ('<p class="adoption">同意の記録（真正性と意味は別途確認）</p>'
                       + ''.join(f'<p>{label}: {html.escape(adoption[field])}</p>' for field, label in (
                           ('user_message_id', '本人の発言ID'), ('user_quote', '本人の原文'),
                           ('assistant_message_id', '返答ID'), ('scope', '同意の範囲')))
                       + '<p class="how">同意の記録は申告であり、この画面だけで真正性を保証しません。</p>')
        rows.append(f'<li class="plan-item" data-kind="{item["kind"]}">'
                    f'<b>{PLAN_KINDS[item["kind"]]}</b><p>{html.escape(item["text"])}</p>'
                    '<details class="plan-references"><summary>根拠・出典を確認</summary>'
                    f'<p class="plan-basis">根拠の発言ID: {html.escape(", ".join(item["basis"]))}</p>'
                    + (f'<ul class="external-sources">{urls}</ul>' if urls else '') + receipt + '</details></li>')
    return ('<div class="writing-plan"><b>書く内容</b>'
            f'<ol>{"".join(rows)}</ol></div>')

SRC = {"本人の発言": "self", "AIの案": "ai", "口述が必要": "need", "公開本文": "pub"}
ROW = re.compile(
    r'<li class="(\w+)((?: c-\w+)?)" id="p(\d+)"(?: data-paragraph-id="([^"]+)")?><span class="no">\d+</span><span class="tags"><span class="m (\w+)">([^<]+)</span>'
    r'(?:<span class="ct \w+">([^<]+)</span>)?</span><span class="t">(.*?)</span>(?:<div class="fig">.*?</div>)?'
    r'<span class="src">(.*?)</span>(?:<span class="chk (\w+)">([^<　]+))?', re.S)
SOURCE_LABEL = {"本人の発言": "本人", "AIの案": "AI", "口述が必要": "口述待ち", "公開本文": "公開"}


def display_text(paragraph):
    edited = paragraph.get("edited_text")
    if edited is None:
        return html.escape(paragraph["text"])
    return (f'<span class="raw-text">原文: {html.escape(paragraph["text"])}</span><br>'
            f'<span class="edited-text">{"現稿対応" if paragraph.get("draft_correspondence") else "編集案"}: {html.escape(edited)}</span>')
def draft_correspondence_errors(ep, repo_root):
    """Reject a source/draft pairing after either saved text has changed."""
    binding = ep.get("draft_correspondence")
    if binding is None:
        return []
    errors = []
    try:
        target = (repo_root / binding["draft_path"]).resolve(strict=True)
        if not target.is_relative_to(repo_root.resolve()):
            return ["draft path outside repository"]
        raw = target.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if binding["draft_sha256"] != digest:
            errors.append("draft correspondence is stale")
        body = re.sub(r"\A---\r?\n.*?\r?\n---(?:\r?\n|$)", "", raw.decode("utf-8-sig"), count=1, flags=re.S)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        blocks = [block.strip() for block in re.split(r"\n\s*\n", body)
                  if block.strip() and not block.strip().startswith(("#", "- "))]
        rows = [p for section in ep["sections"] for p in section["paragraphs"]]
        if binding["draft_body_paragraphs"] != len(blocks) or binding["source_paragraphs"] != len(rows):
            errors.append("draft/source paragraph count mismatch")
        covered = set()
        for row in rows:
            pair = row["draft_correspondence"]
            if pair["draft_sha256"] != digest or pair["source_text_sha256"] != hashlib.sha256(row["text"].encode()).hexdigest():
                errors.append("paragraph correspondence hash mismatch")
            display = row.get("edited_text", "")
            markers = list(re.finditer(r"［本文 第(\d+)段落］\n", display))
            if [int(mark.group(1)) for mark in markers] != pair["draft_paragraphs"]:
                errors.append("displayed draft paragraph differs from saved draft")
            for index, number in enumerate(pair["draft_paragraphs"]):
                if type(number) is not int or not 1 <= number <= len(blocks):
                    errors.append("invalid draft paragraph number")
                elif index >= len(markers):
                    errors.append("displayed draft paragraph differs from saved draft")
                else:
                    end = markers[index + 1].start() if index + 1 < len(markers) else len(display)
                    if display[markers[index].end():end].strip() != blocks[number - 1]:
                        errors.append("displayed draft paragraph differs from saved draft")
                    else:
                        covered.add(number)
        for item in binding["draft_only_paragraphs"]:
            number = item["paragraph"]
            if type(number) is not int or not 1 <= number <= len(blocks) or item["text"] != blocks[number - 1]:
                errors.append("additional draft paragraph differs from saved draft")
            else:
                covered.add(number)
        if covered != set(range(1, len(blocks) + 1)):
            errors.append("draft paragraphs missing from correspondence")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        errors.append("draft correspondence cannot be verified")
    return errors


def _bound_draft_paths(data, workspace_root, draft_paths):
    """Index再生成に必要な本文だけをworkspace内の明示bindingから補う。"""
    paths = list(draft_paths or [])
    episodes = data.get("episodes", []) if isinstance(data, dict) else data
    for episode in episodes:
        if not episode.get("character_counts"):
            continue
        binding = episode.get("draft_correspondence") or {}
        value = binding.get("draft_path")
        if isinstance(value, str) and value.strip():
            paths.append(workspace_root / value)
    resolved = []
    for path in paths:
        target = Path(path).resolve(strict=True)
        if not target.is_relative_to(workspace_root.resolve()):
            raise ValueError("draftは利用者workspace内に置いてください")
        if target not in resolved:
            resolved.append(target)
    return resolved


def _index_matches_source(data, out, workspace_root, source_path, draft_paths):
    """同じrendererで正規indexを作り、表示契約全体を重複実装せず比較する。"""
    drafts = _bound_draft_paths(data, workspace_root, draft_paths)
    with tempfile.TemporaryDirectory() as temporary:
        command = [sys.executable, str(Path(__file__).with_name("note_skeleton_review.py")),
                   str(source_path), temporary, "--workspace-root", str(workspace_root)]
        for draft in drafts:
            command.extend(("--draft", str(draft)))
        rendered = subprocess.run(command, capture_output=True, text=True)
        if rendered.returncode:
            print("  index regeneration failed:", rendered.stderr.strip() or rendered.stdout.strip())
            return False
        expected = (Path(temporary) / "index.html").read_bytes()
    try:
        return (out / "index.html").read_bytes() == expected
    except OSError:
        return False


def check_pages(data, out, workspace_root, source_path=None, draft_paths=None):
    episodes = data["episodes"] if isinstance(data, dict) else data
    if (not isinstance(episodes, list) or any(not isinstance(ep, dict) or type(ep.get("n")) is not int or ep["n"] < 1 for ep in episodes)
            or len({ep["n"] for ep in episodes}) != len(episodes)):
        raise ValueError("各話nは重複のない正の整数で指定してください")
    bad = 0
    for ep in episodes:
        binding_errors = draft_correspondence_errors(ep, workspace_root)
        if binding_errors:
            bad += 1
            print("  draft correspondence:", "; ".join(binding_errors))
        h = (out / f"ep{ep['n']}.html").read_text(encoding="utf-8")
        want = [(SRC[p["source"]], SRC[p["source"]], SOURCE_LABEL[p["source"]], p.get("id") or "", p.get("claim") or "", display_text(p), html.escape((p.get("ref") or "").strip()) or "（記録なし）",
                 (p.get("check") or {}).get("status", "")) for s in ep["sections"] for p in s["paragraphs"]]
        got = [(m[0], m[4], m[5], m[3] or "", m[6], m[7], m[8], m[10]) for m in ROW.findall(h)]
        nums = [int(m[2]) for m in ROW.findall(h)]
        strip = re.findall(r'<a href="#p(\d+)" class="(\w+)', h)
        plans = re.findall(r'<div class="writing-plan">.*?</div>', h, re.S)
        expected_plans = [writing_plan_html(section) for section in ep["sections"] if "writing_plan" in section]
        evidence = re.findall(
            r'<div class="writing-plan">.*?</div><details class="plan-evidence">'
            r'<summary>根拠の発言を確認</summary><ul class="rows">(.*?)</ul></details>', h, re.S)
        evidence_ids = [re.findall(r'data-paragraph-id="([^"]+)"', rows) for rows in evidence]
        expected_ids = [[html.escape(p['id']) for p in section['paragraphs'] if p.get('id')]
                        for section in ep['sections'] if 'writing_plan' in section]
        ok = (plans == expected_plans and evidence_ids == expected_ids
              and got == want and nums == list(range(1, len(want) + 1))
              and [(int(a), b) for a, b in strip] == [(i + 1, w[0]) for i, w in enumerate(want)])
        if not ok:
            bad += 1
            for i, (g, w) in enumerate(zip(got, want), 1):
                if g != w:
                    print("  first diff at", i, g, w)
                    break
        print(ep["n"], "paragraphs", len(want), "rows", len(got), "strip", len(strip), "OK" if ok else "MISMATCH")
    if source_path is not None:
        index_ok = _index_matches_source(data, out, workspace_root, source_path, draft_paths)
        if not index_ok:
            bad += 1
        print("index", "OK" if index_ok else "MISMATCH")
    print("mismatch pages:", bad)
    return 1 if bad else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--draft", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    source = args.source.resolve(strict=True)
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    validate_writing_plans(data)
    return check_pages(data, args.output, args.workspace_root.resolve(strict=True), source, args.draft)


if __name__ == "__main__":
    sys.exit(main())
