"""Vocabulary rules constrain presentation without certifying author/source meaning."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from note_authorship_gate import check_history_learning_from_settings
from note_feedback import article_history_policy, validate_history_policy

RULE = dict(id='word-choice', avoid='難問', preferred='疑問', excluded_compounds=['難問題'])


@pytest.mark.parametrize('body,blocked', [
    ('本文`未閉じ\n\n難問です\n\n次`です', True),
    ('本文`未閉じ\n# 難問です\n次`です', True),
    ('本文`未閉じ\n- 難問です\n次`です', True),
    ('これは](難問)です', True), (r'\[ラベル](難問)', True),
    ('`code\n難問\ncode`', False), ('``code\n難問\ncode``', False),
    ('code\n難問\ncode`', True),
    ('## 難問を考える', True), ('難問という言葉', True), ('[難問](https://example.test)', True),
    ('難問題を扱う', False), ('[資料](https://example.test/難問)', False),
    ('```text\n難問\n```\n本文', False), ('~~~\n難問\n~~~', False),
    ('> 難問の引用\n> 続き', True), ('> 引用\n難問という本人語り', True),
    ('引用という語の後にも難問', True), ('『難問』', True),
    ('## 参考・出典\n- [難問](https://example.test)', True),
    ('[文献](https://example.test)を見て難問と考える', True),
    ('<b>難</b>問', True), ('難&#x554f;', True), ('難<!--comment-->問', True),
    ('<blockquote>難問</blockquote>', True), ('`難問`というコード', False),
    ('---\ntitle: 難問\n---\n本文', False),
    ('難*問*', True), ('難\n問', True), ('難\u200b問', True),
    ('``難問`a`', True),
    (r'\`難問\`が残る', True), (r'\`難問`が残る', True),
    (r'\\`難問`というコード', False),
])
def test_vocabulary_visible_context(tmp_path, body, blocked):
    draft = tmp_path / 'draft.md'
    draft.write_text(body)
    style = tmp_path / 'style.md'
    style.write_text('A voice reference.')
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile='style.md', article_profiles={'article': ['style.md']},
            history_learning_policy=dict(schema='nps-history-learning-policy/v1', required=False,
                vocabulary_rules=[RULE])))))
    result = check_history_learning_from_settings(draft, settings, 'article')
    assert result['status'] == ('blocked' if blocked else 'mechanical_ok')
    assert result['hashes']['target'] == __import__('hashlib').sha256(draft.read_bytes()).hexdigest()
    if blocked:
        assert any('vocabulary' in error for error in result['errors'])


@pytest.mark.parametrize('rule', [None, {}, dict(RULE, avoid=''), dict(RULE, preferred=''),
    dict(RULE, excluded_compounds='bad'), dict(RULE, excluded_compounds=['unrelated']),
    dict(RULE, excluded_compounds=['難問']), dict(RULE, excluded_compounds=['難問題', '難問題'])])
def test_vocabulary_malformed_rules_block(rule):
    with pytest.raises(ValueError):
        validate_history_policy(dict(schema='nps-history-learning-policy/v1', required=False,
                                     vocabulary_rules=[rule]))


def test_vocabulary_rules_union_and_scope():
    global_policy = dict(schema='nps-history-learning-policy/v1', required=False, vocabulary_rules=[RULE])
    local = dict(RULE, id='local', avoid='別語', preferred='適語', excluded_compounds=[])
    style = dict(history_learning_policy=global_policy, article_profiles={
        'article': dict(references=['voice.md'], history_learning_policy=dict(
            schema='nps-history-learning-policy/v1', required=False, vocabulary_rules=[local])),
        'other': ['voice.md']})
    assert len(article_history_policy(style, 'article')['vocabulary_rules']) == 2
    assert len(article_history_policy(style, 'other')['vocabulary_rules']) == 1
    with pytest.raises(ValueError): article_history_policy(style, None)
    local['id'] = RULE['id']
    with pytest.raises(ValueError): article_history_policy(style, 'article')


@pytest.mark.parametrize('kind', ['quotation', 'source_title', 'preserved_original'])
@pytest.mark.parametrize('problem', ['none', 'stale_target', 'stale_source', 'wrong_span', 'extra_prose', 'unknown_source'])
def test_vocabulary_exceptions_require_captured_exact_source(tmp_path, kind, problem):
    import hashlib
    body = {'quotation': '> 難問', 'source_title': '[難問](https://example.test)',
            'preserved_original': '難問'}[kind]
    if problem == 'extra_prose': body += ' と考える難問'
    draft = tmp_path / 'draft.md'
    draft.write_text(body)
    style = tmp_path / 'style.md'
    style.write_text('保存原文：難問')
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile='style.md', article_profiles={'article': ['style.md']},
            history_learning_policy=dict(schema='nps-history-learning-policy/v1', required=False,
                vocabulary_rules=[RULE])))))
    sha = hashlib.sha256(draft.read_bytes()).hexdigest()
    source = dict(id='original', path='style.md', quote='難問', evidence_ref='fixture://original',
                  sha256=hashlib.sha256(style.read_bytes()).hexdigest())
    exception = dict(kind=kind, source_id='original', target_sha256=sha, line=1, start=0,
                     target_excerpt='難問', target_excerpt_sha256=hashlib.sha256('難問'.encode()).hexdigest())
    if problem == 'stale_target': exception['target_sha256'] = '0' * 64
    elif problem == 'stale_source': source['sha256'] = '0' * 64
    elif problem == 'wrong_span': exception['start'] = 1
    elif problem == 'unknown_source': exception['source_id'] = 'other'
    draft.with_suffix('.authorship.json').write_text(json.dumps(dict(
        schema_version='note-authorship-evidence/v1', draft_sha256=sha,
        history_learning=dict(sources=[source], vocabulary_exceptions=[exception]))))
    result = check_history_learning_from_settings(draft, settings, 'article')
    assert result['status'] == ('mechanical_ok' if problem == 'none' else 'blocked')
    if problem == 'extra_prose': assert len(result['vocabulary_check']['issues']) == 1


from test_history_learning_gate import learning


@pytest.mark.parametrize('blocked', [False, True])
def test_vocabulary_real_g2_preserves_binding_report(learning, blocked):
    config = json.loads(learning['settings'].read_text())
    rule = dict(RULE, avoid='本人' if blocked else '難問', excluded_compounds=[])
    config['style']['history_learning_policy']['vocabulary_rules'] = [rule]
    learning['settings'].write_text(json.dumps(config))
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == ('blocked' if blocked else 'mechanical_ok')
    assert result['vocabulary_check']['target_sha256'] == result['hashes']['target']
    assert result['settings_readback']['history_learning_policy']['vocabulary_rules'] == [rule]


def test_vocabulary_rejects_changed_draft_during_scan(learning, monkeypatch):
    import nps_script_loader
    note_author_vocabulary = nps_script_loader.load_script('note_author_vocabulary')
    config = json.loads(learning['settings'].read_text())
    config['style']['history_learning_policy']['vocabulary_rules'] = [RULE]
    learning['settings'].write_text(json.dumps(config))
    original = note_author_vocabulary.check_vocabulary
    def change_target(*args, **kwargs):
        result = original(*args, **kwargs)
        learning['draft'].write_text('検査中に変更')
        return result
    monkeypatch.setattr(note_author_vocabulary, 'check_vocabulary', change_target)
    assert check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])['status'] == 'blocked'


@pytest.mark.parametrize('exceptions', [[], None, {}, "invalid"])
def test_vocabulary_empty_exceptions_need_no_sources(tmp_path, exceptions):
    draft = tmp_path / 'draft.md'
    draft.write_text('普通の本文')
    (tmp_path / 'style.md').write_text('A voice reference.')
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile='style.md', article_profiles={'article': ['style.md']},
            history_learning_policy=dict(schema='nps-history-learning-policy/v1', required=False,
                vocabulary_rules=[RULE])))))
    draft.with_suffix('.authorship.json').write_text(json.dumps(dict(
        schema_version='note-authorship-evidence/v1',
        history_learning=dict(vocabulary_exceptions=exceptions))))
    result = check_history_learning_from_settings(draft, settings, 'article')
    assert result['status'] == ('mechanical_ok' if exceptions == [] else 'blocked')
