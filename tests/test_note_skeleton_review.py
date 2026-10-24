import hashlib
import json
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

def fixture(tmp_path):
    source = tmp_path / 'oral.md'
    source.write_text('# 本人原文\n\n> 原文の疑問。\n')
    row = {'id': 'a7-p001', 'source': '本人の発言', 'text': '原文の疑問。', 'edited_text': '原文の疑問。',
           'ref': 'oral.md:3', 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
           'text_sha256': hashlib.sha256('原文の疑問。'.encode()).hexdigest()}
    data = {'series': {'title': '任意の連載', 'index_title': '確認一覧'}, 'episodes': [
        {'n': 7, 'title': '第7話', 'sections': [{'heading': '疑問', 'paragraphs': [row,
            {'id': 'a7-p002', 'source': 'AIの案', 'text': '未採用のAI案。', 'ref': 'AI案'}]}]}]}
    skeleton = tmp_path / 'skeleton.json'; skeleton.write_text(json.dumps(data))
    draft = tmp_path / 'draft.md'; draft.write_text('---\nepisode: 7\nsource_mode: skeleton_first\nauthor_skeleton: skeleton.json\n---\n<!-- provenance-label: user-said; source: oral -->\n<!-- paragraph-id: a7-p001 -->\n原文の疑問。\n')
    return skeleton, draft

def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str,args)],capture_output=True,text=True)

def test_generic_html_and_verification(tmp_path):
    skeleton,draft=fixture(tmp_path);out=tmp_path/'html'
    rendered=run('note_skeleton_review.py',skeleton,out,'--workspace-root',tmp_path)
    assert rendered.returncode==0,rendered.stderr
    text=(out/'ep7.html').read_text()
    assert '原文の疑問。' in text and '未採用のAI案。' in text
    assert '由来ラベルは保存資料の申告' in text
    assert run('note_skeleton_review_check.py',skeleton,out,'--workspace-root',tmp_path).returncode==0
    (out/'ep7.html').write_text(text.replace('原文の疑問。','改変された本文。'))
    assert run('note_skeleton_review_check.py',skeleton,out,'--workspace-root',tmp_path).returncode!=0


@pytest.mark.parametrize('old,new', [
    ('<span class="m self">本人</span>', '<span class="m self">AI</span>'),
    ('<span class="m self">本人</span>', '<span class="m ai">本人</span>'),
])
def test_visible_source_marker_tamper_is_rejected(tmp_path, old, new):
    skeleton,_=fixture(tmp_path);out=tmp_path/'html'
    assert run('note_skeleton_review.py',skeleton,out,'--workspace-root',tmp_path).returncode==0
    page=out/'ep7.html';page.write_text(page.read_text().replace(old,new,1))
    assert run('note_skeleton_review_check.py',skeleton,out,'--workspace-root',tmp_path).returncode!=0


@pytest.mark.parametrize('mutation', ['title', 'heading', 'count', 'origin', 'missing'])
def test_index_tamper_or_missing_is_rejected(tmp_path, mutation):
    skeleton,_=fixture(tmp_path);out=tmp_path/'html'
    assert run('note_skeleton_review.py',skeleton,out,'--workspace-root',tmp_path).returncode==0
    index=out/'index.html'
    if mutation == 'missing':
        index.unlink()
    else:
        text=index.read_text()
        replacements={
            'title': ('<title>確認一覧</title>', '<title>改変一覧</title>'),
            'heading': ('<h1>任意の連載</h1>', '<h1>改変した連載</h1>'),
            'count': ('2段落', '99段落'),
            'origin': ('heading-origin self', 'heading-origin ai'),
        }
        old,new=replacements[mutation]
        assert old in text
        index.write_text(text.replace(old,new,1))
    assert run('note_skeleton_review_check.py',skeleton,out,'--workspace-root',tmp_path).returncode!=0


def test_bom_skeleton_renders_and_checks(tmp_path):
    skeleton,_=fixture(tmp_path);out=tmp_path/'html'
    skeleton.write_bytes(b'\xef\xbb\xbf'+skeleton.read_bytes())
    assert run('note_skeleton_review.py',skeleton,out,'--workspace-root',tmp_path).returncode==0
    checked=run('note_skeleton_review_check.py',skeleton,out,'--workspace-root',tmp_path)
    assert checked.returncode==0,checked.stdout+checked.stderr


def test_web5_filename_is_not_treated_as_b5(tmp_path):
    pytest.importorskip('yaml');pytest.importorskip('markdown_it')
    draft=tmp_path/'web5-notes.md';draft.write_text('通常のメモ。')
    result=run('note_skeleton_source_gate.py',draft,'--workspace-root',tmp_path)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)['status']=='not_applicable'


@pytest.mark.parametrize('name', ['b5.md', 'draft-b05-review.md'])
def test_exact_b5_filename_token_preserves_b5_contract(tmp_path, name):
    pytest.importorskip('yaml');pytest.importorskip('markdown_it')
    draft=tmp_path/name;draft.write_text('通常のメモ。')
    result=run('note_skeleton_source_gate.py',draft,'--workspace-root',tmp_path)
    assert result.returncode!=0
    assert 'B5: source_mode' in result.stdout

@pytest.mark.parametrize('mutation',['source','draft'])
def test_source_and_draft_drift_rejected(tmp_path,mutation):
    pytest.importorskip('yaml');pytest.importorskip('markdown_it')
    _,draft=fixture(tmp_path)
    valid=run('note_skeleton_source_gate.py',draft,'--workspace-root',tmp_path)
    assert valid.returncode==0,valid.stdout+valid.stderr
    target=tmp_path/'oral.md' if mutation=='source' else draft
    target.write_text(target.read_text().replace('原文の疑問。','変更された疑問。'))
    assert run('note_skeleton_source_gate.py',draft,'--workspace-root',tmp_path).returncode!=0

def test_unsafe_source_url_is_not_rendered(tmp_path):
    skeleton,_=fixture(tmp_path);data=json.loads(skeleton.read_text())
    data['episodes'][0]['sections'][0]['paragraphs'][0]['check']={'status':'確認待ち','urls':['javascript:alert(1)']}
    skeleton.write_text(json.dumps(data))
    assert run('note_skeleton_review.py',skeleton,tmp_path/'html','--workspace-root',tmp_path).returncode!=0


def writing_plan_fixture(tmp_path):
    skeleton, draft = fixture(tmp_path)
    data = json.loads(skeleton.read_text())
    data['skeleton_mode'] = 'writing-plan'
    section = data['episodes'][0]['sections'][0]
    section['paragraphs'][0]['message_id'] = 'user-1'
    section['paragraphs'][1]['message_id'] = 'assistant-1'
    section['writing_plan'] = {'items': [
        {'kind': 'author-position', 'text': 'この節で説明する本人の問題意識。', 'basis': ['a7-p001']},
        {'kind': 'open-question', 'text': '未解決の問いを問いのまま示す。', 'basis': ['a7-p001']},
        {'kind': 'research', 'text': '依頼に基づき資料で説明する。', 'basis': ['a7-p001'],
         'external_sources': ['https://example.org/reference']},
        {'kind': 'accepted-response', 'text': '本人が同意した範囲を説明する。',
         'basis': ['a7-p001', 'a7-p002'], 'adoption': {
             'user_message_id': 'user-1', 'user_quote': '原文の疑問。',
             'assistant_message_id': 'assistant-1', 'scope': 'この問題意識のみ'}},
    ]}
    skeleton.write_text(json.dumps(data))
    return skeleton, data, section


def test_writing_plan_precedes_collapsed_source_and_preserves_evidence(tmp_path):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    # 子見出しにも同じ確認画面を使う。
    section['heading'] = '論点 > 出発点'
    skeleton.write_text(json.dumps(data))
    out = tmp_path / 'html'
    rendered = run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path)
    assert rendered.returncode == 0, rendered.stderr
    page = (out / 'ep7.html').read_text()
    assert page.index('書く内容') < page.index('<details class="plan-evidence">') < page.index('data-paragraph-id="a7-p001"')
    assert '調べて説明すること' in page and '真正性を保証しません' in page
    assert 'data-paragraph-id="a7-p001"' in page
    checked = run('note_skeleton_review_check.py', skeleton, out, '--workspace-root', tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_writing_plan_default_shows_content_and_hides_internal_references(tmp_path):
    skeleton, _, section = writing_plan_fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    page = (out / 'ep7.html').read_text()
    plan = page.split('<div class="writing-plan">', 1)[1].split('</div>', 1)[0]

    class DefaultPlanText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.visible = []
            self.details = 0

        def handle_starttag(self, tag, attrs):
            if tag == 'details':
                assert 'open' not in dict(attrs)
                self.depth += 1
                self.details += 1

        def handle_endtag(self, tag):
            if tag == 'details':
                self.depth -= 1

        def handle_data(self, text):
            if not self.depth:
                self.visible.append(text)

    parsed = DefaultPlanText()
    parsed.feed(plan)
    visible = ''.join(parsed.visible)
    assert parsed.details == len(section['writing_plan']['items'])
    for item in section['writing_plan']['items']:
        assert item['text'] in visible
    assert '本人の考え' in visible and '調べて説明すること' in visible
    for private_detail in ('真正性', 'a7-p001', 'https://example.org/reference', 'user-1', 'この問題意識のみ'):
        assert private_detail in plan
        assert private_detail not in visible
    assert '<summary>根拠・出典を確認</summary>' in plan


@pytest.mark.parametrize('mutation', ['missing-plan', 'empty-plan', 'invalid-kind', 'unknown-basis',
    'empty-basis', 'duplicate-basis', 'duplicate-item', 'missing-adoption', 'bad-user-id',
    'bad-assistant-id', 'bad-user-quote', 'missing-adoption-basis', 'empty-scope',
    'http-url', 'credentials-url', 'invalid-port', 'url-not-list'])
def test_invalid_writing_plans_rejected_by_renderer_and_checker(tmp_path, mutation):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    items = section['writing_plan']['items']
    if mutation == 'missing-plan': del section['writing_plan']
    elif mutation == 'empty-plan': items.clear()
    elif mutation == 'invalid-kind': items[0]['kind'] = 'ai-conclusion'
    elif mutation == 'unknown-basis': items[0]['basis'] = ['unknown']
    elif mutation == 'empty-basis': items[1]['basis'] = []
    elif mutation == 'duplicate-basis': items[0]['basis'] *= 2
    elif mutation == 'duplicate-item': items.append(items[0].copy())
    elif mutation == 'missing-adoption': del items[-1]['adoption']
    elif mutation == 'bad-user-id': items[-1]['adoption']['user_message_id'] = 'other-user'
    elif mutation == 'bad-assistant-id': items[-1]['adoption']['assistant_message_id'] = 'other-ai'
    elif mutation == 'bad-user-quote': items[-1]['adoption']['user_quote'] = '存在しない同意'
    elif mutation == 'missing-adoption-basis': items[-1]['basis'] = ['a7-p001']
    elif mutation == 'empty-scope': items[-1]['adoption']['scope'] = ''
    elif mutation == 'http-url': items[2]['external_sources'] = ['http://example.org']
    elif mutation == 'credentials-url': items[2]['external_sources'] = ['https://name:pass@example.org']
    elif mutation == 'invalid-port': items[2]['external_sources'] = ['https://example.org:bad']
    elif mutation == 'url-not-list': items[2]['external_sources'] = 'https://example.org'
    skeleton.write_text(json.dumps(data))
    for script in ('note_skeleton_review.py', 'note_skeleton_review_check.py'):
        assert run(script, skeleton, out, '--workspace-root', tmp_path).returncode != 0


@pytest.mark.parametrize('kind', ['author-position', 'open-question', 'research'])
def test_ai_only_basis_cannot_be_presented_as_author_position_or_request(tmp_path, kind):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    # 同意したAI返答を本人の判断へ分類変更し、同意証拠を外す変異。
    item = section['writing_plan']['items'][-1]
    item['kind'] = kind
    item['basis'] = ['a7-p002']
    del item['adoption']
    skeleton.write_text(json.dumps(data))
    for script in ('note_skeleton_review.py', 'note_skeleton_review_check.py'):
        result = run(script, skeleton, out, '--workspace-root', tmp_path)
        assert result.returncode != 0
        assert '本人の発言basisが必要です' in result.stderr


def test_author_position_with_ai_basis_requires_accepted_response_record(tmp_path):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    item = section['writing_plan']['items'][-1]
    item['kind'] = 'author-position'
    del item['adoption']
    skeleton.write_text(json.dumps(data))
    for script in ('note_skeleton_review.py', 'note_skeleton_review_check.py'):
        result = run(script, skeleton, out, '--workspace-root', tmp_path)
        assert result.returncode != 0
        assert 'accepted-responseとadoptionで記録してください' in result.stderr


def test_writing_plan_counts_distinguish_items_and_source_records(tmp_path):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    section['heading'] = '論点 > 出発点'
    data['episodes'][0]['sections'].append({
        'heading': '結び',
        'paragraphs': [{'id': 'a7-p003', 'source': '本人の発言', 'text': '残る問い。', 'ref': '別の発言'}],
        'writing_plan': {'items': [{'kind': 'open-question', 'text': 'この問いは未決として残す。',
                                    'basis': ['a7-p003']}]},
    })
    skeleton.write_text(json.dumps(data))
    out = tmp_path / 'html'
    rendered = run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path)
    assert rendered.returncode == 0, rendered.stderr
    page = (out / 'ep7.html').read_text()
    index = (out / 'index.html').read_text()
    assert '書く内容5項目・根拠3件' in page and '書く内容5項目・根拠3件' in index
    assert page.count('書く内容4項目・根拠2件') >= 3  # 目次・大見出し・小見出し
    assert '書く内容1項目・根拠1件' in page
    assert '根拠の由来: 本人 2・AI 1' in index
    assert '<input type="radio"' not in page
    assert '構成の表示' in page and '書く内容まで' in page
    assert run('note_skeleton_review_check.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0


def test_legacy_counts_and_source_filters_are_preserved(tmp_path):
    skeleton, _ = fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    page = (out / 'ep7.html').read_text()
    assert '2段落' in page
    assert '<input type="radio"' in page and '>絞り込み</span>' in page
    assert '書く内容0項目' not in page


@pytest.mark.parametrize('mutation', ['changed-text', 'missing-item', 'duplicate-item', 'changed-basis', 'changed-adoption', 'opened-evidence'])
def test_rendered_plan_tampering_is_rejected(tmp_path, mutation):
    skeleton, _, _ = writing_plan_fixture(tmp_path)
    out = tmp_path / 'html'
    assert run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path).returncode == 0
    target = out / 'ep7.html'
    page = target.read_text()
    if mutation == 'changed-text': page = page.replace('この節で説明する本人の問題意識。', 'AIが追加した結論。')
    elif mutation == 'changed-basis': page = page.replace('根拠の発言ID: a7-p001', '根拠の発言ID: unknown', 1)
    elif mutation == 'changed-adoption': page = page.replace('本人の発言ID: user-1', '本人の発言ID: fabricated')
    elif mutation == 'opened-evidence': page = page.replace('<details class="plan-evidence">', '<details class="plan-evidence" open>')
    else:
        start = page.index('<li class="plan-item"')
        end = page.index('</li>', start) + len('</li>')
        block = page[start:end]
        page = page.replace(block, '' if mutation == 'missing-item' else block + block, 1)
    target.write_text(page)
    assert run('note_skeleton_review_check.py', skeleton, out, '--workspace-root', tmp_path).returncode != 0


def test_checker_only_change_invalidates_generated_page_version(tmp_path):
    import re
    import shutil
    skeleton, _ = fixture(tmp_path)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    for name in ('note_skeleton_review.py', 'note_skeleton_review_check.py'):
        shutil.copy2(SCRIPTS / name, scripts / name)
    output = tmp_path / 'html'
    command = [sys.executable, str(scripts / 'note_skeleton_review.py'), str(skeleton),
               str(output), '--workspace-root', str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True)
    before = (output / 'ep7.html').read_text()
    helper = scripts / 'note_skeleton_review_check.py'
    helper.write_text(helper.read_text() + '\n# helper implementation changed\n')
    subprocess.run(command, check=True, capture_output=True)
    after = (output / 'ep7.html').read_text()
    version = lambda text: re.search(r'name="generation-version" content="([a-f0-9]+)"', text).group(1)
    assert version(before) != version(after)


@pytest.mark.parametrize('kind', ['author-position', 'open-question', 'research'])
def test_optional_adoption_never_accepts_fabricated_evidence(tmp_path, kind):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    item = next(row for row in section['writing_plan']['items'] if row['kind'] == kind)
    item['adoption'] = {'user_message_id': 'missing-user', 'user_quote': '架空の同意',
                        'assistant_message_id': 'missing-ai', 'scope': 'この項目'}
    skeleton.write_text(json.dumps(data))
    for script in ('note_skeleton_review.py', 'note_skeleton_review_check.py'):
        result = run(script, skeleton, tmp_path / 'html', '--workspace-root', tmp_path)
        assert result.returncode != 0
        assert 'adoptionは根拠に含む本人とAIの実発言' in result.stderr


@pytest.mark.parametrize('kind', ['research', 'open-question'])
def test_optional_adoption_with_real_basis_is_preserved(tmp_path, kind):
    skeleton, data, section = writing_plan_fixture(tmp_path)
    section['writing_plan']['items'][-1]['kind'] = kind
    skeleton.write_text(json.dumps(data))
    out = tmp_path / 'html'
    rendered = run('note_skeleton_review.py', skeleton, out, '--workspace-root', tmp_path)
    assert rendered.returncode == 0, rendered.stderr
    checked = run('note_skeleton_review_check.py', skeleton, out, '--workspace-root', tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
