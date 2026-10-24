"""Opt-in visible vocabulary check; source exceptions require captured evidence."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import html
import re
import unicodedata


def normalized(text: str) -> str:
    return ''.join(char for char in unicodedata.normalize('NFKC', text)
                   if unicodedata.category(char) != 'Cf')


class _VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _without_code_spans(text: str) -> str:
    parts, cursor = [], 0
    runs = []
    for run in re.finditer(r'`+', text):
        preceding = run.start() - 1
        while preceding >= 0 and text[preceding] == '\\':
            preceding -= 1
        # Odd backslashes escape the delimiter; preserve ambiguous runs as prose.
        if (run.start() - 1 - preceding) % 2 == 0:
            runs.append(run)
    index = 0
    while index < len(runs):
        opening = runs[index]
        closing_index = next((candidate for candidate in range(index + 1, len(runs))
                              if len(runs[candidate][0]) == len(opening[0])), None)
        if closing_index is None:
            index += 1
            continue
        parts.append(text[cursor:opening.start()])
        # Keep physical rows stable for evidence-bound exception coordinates.
        parts.append('\n' * text[opening.start():runs[closing_index].end()].count('\n'))
        cursor = runs[closing_index].end()
        index = closing_index + 1
    return ''.join(parts) + text[cursor:]


def visible_text(text: str) -> str:
    # Remove only closed code spans and balanced link destinations; retain labels.
    text = _without_code_spans(text)
    text = re.sub(r'<?https?://[^\s<>]+>?', '', text) if not '[' in text else text
    result, index, brackets = [], 0, []
    while index < len(text):
        preceding = index - 1
        while preceding >= 0 and text[preceding] == '\\':
            preceding -= 1
        escaped = (index - 1 - preceding) % 2 == 1
        if text[index] == '[' and not escaped:
            brackets.append(index)
        if text[index:index + 2] == '](' and brackets and not escaped:
            depth, end = 1, index + 2
            while end < len(text) and depth:
                if text[end] == '\\':
                    end += 2
                    continue
                depth += (text[end] == '(') - (text[end] == ')')
                end += 1
            if depth == 0:
                brackets.pop()
                index = end
                continue
        if text[index] == ']' and brackets and not escaped:
            brackets.pop()
        result.append(text[index])
        index += 1
    text = ''.join(result)
    # Formatting markers do not divide visible words. Do not infer quote authenticity.
    text = re.sub(r'^\s{0,3}(?:>\s*)+', '', text)
    text = re.sub(r'^\s{0,3}#{1,6}\s+', '', text)
    for marker in ('[', ']', '*', '_', '~~'):
        text = text.replace(marker, '')
    parser = _VisibleHTML()
    parser.feed(text)
    parser.close()
    return normalized(html.unescape(''.join(parser.parts)))


def visible_lines(raw: bytes) -> dict[int, str]:
    lines = raw.decode('utf-8-sig').replace('\r\n', '\n').splitlines()
    start = 0
    if lines and lines[0].strip() == '---':
        for index in range(1, len(lines)):
            if lines[index].strip() == '---':
                start = index + 1
                break
        else:
            raise ValueError('unclosed vocabulary frontmatter')
    rendered, fence = {}, None
    for index in range(start, len(lines)):
        line = lines[index]
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is not None:
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
            continue
        if match and (match[1][0] != '`' or '`' not in match[2]):
            fence = (match[1][0], len(match[1]))
            continue
        rendered[index + 1] = line
    # Inline code may cross soft line breaks inside a paragraph, never blocks.
    # Keep evidence coordinates and treat ambiguous block starts conservatively.
    resolved, paragraph = {}, []

    def flush_paragraph():
        if paragraph:
            prose = _without_code_spans('\n'.join(text for _, text in paragraph))
            for (row, _), text in zip(paragraph, prose.split('\n'), strict=True):
                resolved[row] = visible_text(text)
            paragraph.clear()

    block_start = re.compile(r'^ {0,3}(?:#{1,6}(?:\s|$)|>|(?:[-+*]|\d+[.)])\s|<|(?:[-*_]\s*){3,}$|[=-]+\s*$)')
    for index in range(start, len(lines)):
        row = index + 1
        if row not in rendered or not rendered[row].strip() or block_start.match(rendered[row]):
            flush_paragraph()
            if row in rendered:
                resolved[row] = visible_text(rendered[row])
            continue
        paragraph.append((row, rendered[row]))
    flush_paragraph()
    return resolved


def check_vocabulary(raw: bytes, rules: list[dict], *, exceptions: object = None,
                     sources: dict | None = None) -> dict:
    lines = visible_lines(raw)
    target_sha = hashlib.sha256(raw).hexdigest()
    allowed = []
    if exceptions is not None:
        if not isinstance(exceptions, list):
            raise ValueError('vocabulary exceptions must be a list')
        for entry in exceptions:
            if (not isinstance(entry, dict)
                    or entry.get('kind') not in {'quotation', 'source_title', 'preserved_original'}
                    or entry.get('target_sha256') != target_sha
                    or not isinstance(entry.get('source_id'), str)
                    or entry['source_id'] not in (sources or {})
                    or type(entry.get('line')) is not int or type(entry.get('start')) is not int
                    or entry['start'] < 0 or not isinstance(entry.get('target_excerpt'), str)
                    or not entry['target_excerpt']):
                raise ValueError('vocabulary exception is not evidence bound')
            excerpt = entry['target_excerpt']
            source = sources[entry['source_id']]
            if (entry.get('target_excerpt_sha256') != hashlib.sha256(excerpt.encode()).hexdigest()
                    or visible_text(source['quote']) != excerpt
                    or lines.get(entry['line'], '')[entry['start']:entry['start'] + len(excerpt)] != excerpt):
                raise ValueError('vocabulary exception excerpt mismatch')
            allowed.append((entry['line'], entry['start'], entry['start'] + len(excerpt)))
    issues = []
    for line, text in lines.items():
        for rule in rules:
            avoid = visible_text(rule['avoid'])
            if not avoid:
                raise ValueError('vocabulary rule has no visible term')
            excluded = []
            for compound in rule['excluded_compounds']:
                for match in re.finditer(re.escape(visible_text(compound)), text):
                    excluded.append((match.start(), match.end()))
            for match in re.finditer(re.escape(avoid), text):
                if (any(start <= match.start() and match.end() <= end for start, end in excluded)
                        or any(row == line and start <= match.start() and match.end() <= end
                               for row, start, end in allowed)):
                    continue
                issues.append(dict(rule_id=rule['id'], line=line, start=match.start(),
                                   preferred=rule['preferred'], status='context_review_required'))
    # A soft line break or HTML split must not hide an avoided word. Multi-line
    # exceptions are deliberately unsupported; callers must obtain contextual review.
    for line, text in lines.items():
        following = lines.get(line + 1, '')
        if not text or not following:
            continue
        joined = text + following
        for rule in rules:
            for match in re.finditer(re.escape(visible_text(rule['avoid'])), joined):
                if match.start() < len(text) < match.end():
                    issues.append(dict(rule_id=rule['id'], line=line, start=match.start(),
                                       preferred=rule['preferred'], status='context_review_required'))
    return dict(status='blocked' if issues else 'mechanical_ok', issues=issues,
                target_sha256=target_sha, semantic_understanding_verified=False)
