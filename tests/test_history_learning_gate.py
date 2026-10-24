"""履歴の回収と、現在本文への適用を別々に検査する。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_identical_draft_has_same_history_binding_in_edit_and_layout(learning):
    from note_workflow_gate import check_packet, read_workspace_settings
    from note_feedback import read_article_feedback
    config, dirs = read_workspace_settings(learning['settings'], 'article')
    choice = dict(decision='omit', reason='この構成では追加しない', items=[])
    layout = dict(cover=dict(decision='omit', reason='画像なし'),
        toc=dict(decision='include', reason='見出しへ案内'),
        footer_cards=dict(decision='omit', reason='追加しない', urls=[]),
        illustrations=dict(choice), embeds=dict(choice), hyperlinks=dict(choice),
        review=dict(proposal_ref='fixture://proposal', discussion_ref='fixture://discussion', decision_ref='fixture://decision'))
    packet = dict(schema_version='note-workflow-review/v1', article_id='article', conversation_id='current',
        route='direct_draft', receipts=[], source_snapshot=str(learning['source']), draft=str(learning['draft']),
        proposed_draft=str(learning['draft']), edit_plan={'toc': True}, layout=layout, settings={'account':'example'},
        ssot_readback=config, history_evidence=str(learning['evidence']),
        feedback_readback=read_article_feedback(dirs, 'article', learning['source'], learning['draft']))
    edit = check_packet(packet, 'edit', 'current', settings_path=learning['settings'])
    layout_result = check_packet(packet, 'layout', 'current', settings_path=learning['settings'])
    assert edit['history_learning']['status'] == layout_result['history_learning']['status'] == 'mechanical_ok'
    assert edit['subject_hashes']['layout'] == layout_result['subject_hashes']['layout']

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nps_script_loader


@pytest.mark.parametrize('style', [None, [], {'default_profile': None},
    {'article_profiles': []}, {'article_profiles': {'fixture': ['']}},
    {'history_learning_policy': None}])
def test_generic_history_does_not_opt_out_of_malformed_style(tmp_path, style):
    from note_authorship_gate import check_history_learning_from_settings
    draft = tmp_path / 'draft.md'
    draft.write_text('---\narticle_lane: editor_fixture\n---\nBody.\n')
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'style': style}))
    assert check_history_learning_from_settings(draft, settings, 'fixture')['status'] == 'blocked'


def test_generic_history_settings_snapshot_change_blocks(tmp_path, monkeypatch):
    from note_authorship_gate import check_history_learning_from_settings
    draft = tmp_path / 'draft.md'
    draft.write_text('---\narticle_lane: exploratory_draft\n---\nBody.\n')
    settings = tmp_path / 'settings.json'
    settings.write_text('{}')
    original = Path.read_bytes
    reads = 0
    def swapped(path):
        nonlocal reads
        if path == settings:
            reads += 1
            if reads == 2:
                settings.write_text('{"style":null}')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', swapped)
    assert check_history_learning_from_settings(draft, settings, None)['status'] == 'blocked'


def test_strict_history_cli_rejects_generic_not_required(tmp_path):
    draft = tmp_path / 'draft.md'
    draft.write_text('---\narticle_lane: editor_fixture\n---\nBody.\n')
    settings = tmp_path / 'settings.json'
    settings.write_text('{}')
    script = Path(__file__).resolve().parents[1] / 'scripts/note_authorship_gate.py'
    checked = subprocess.run([sys.executable, str(script), str(draft), '--history-only',
        '--settings', str(settings), '--article-id', 'fixture', '--json'], capture_output=True, text=True)
    assert checked.returncode == 1
    assert json.loads(checked.stdout)['status'] == 'not_required'


@pytest.fixture
def learning(tmp_path):
    from note_authorship_gate import excerpt_id
    from note_feedback import record_feedback
    root = tmp_path.resolve()
    for name in ('sources', 'drafts', 'feedback'):
        (root / name).mkdir()
    style = root / 'history.md'
    style.write_text('本人にない因果を足さない。本人の言葉を保つ。', encoding='utf-8')
    settings = root / 'settings.json'
    settings.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(sources='sources', drafts='drafts', feedback='feedback'),
        style=dict(default_profile='history.md', article_profiles={'article': ['history.md']},
                   history_learning_policy=dict(schema='nps-history-learning-policy/v1', required=True)))))
    draft = root / 'drafts/current.md'
    draft.write_text('本人の言葉を保つ。公開済み本文。', encoding='utf-8')
    source = root / 'sources/current.md'; source.write_text('Discord本人原文', encoding='utf-8')
    prior = root / 'sources/prior.md'; prior.write_text('未発言の説明', encoding='utf-8')
    evidence = draft.with_suffix('.authorship.json')
    candidate = dict(id='rule-1', path=str(style), sha256=hashlib.sha256(style.read_bytes()).hexdigest(),
                     quote='本人にない因果を足さない。', evidence_ref='history.md#author')
    evidence.write_text(json.dumps(dict(schema_version='note-authorship-evidence/v1',
        draft_sha256=hashlib.sha256(draft.read_bytes()).hexdigest(), claims=[],
        history_learning=dict(sources=[candidate]))))
    entries = [dict(origin='ai', decision='pending', before='未発言の説明', after='本人の言葉を保つ。',
        reason='本人原文へ戻す', evidence_ref='history.md#author', history_source_id='rule-1',
        application_status='applied', target_sha256=hashlib.sha256(draft.read_bytes()).hexdigest(),
        target_excerpt_id=excerpt_id('本人の言葉を保つ。'))]
    dirs = {key: root / key for key in ('sources', 'drafts', 'feedback')}
    record_feedback(dirs, 'article', source, draft, prior, entries, conversation_id='current')
    record = json.loads((root / 'feedback/article/feedback.json').read_text())
    return dict(root=root, settings=settings, style=style, draft=draft, source=source,
                evidence=evidence, candidate=candidate, record=record)


@pytest.mark.parametrize('lane', ['production_candidate', 'continuation_article'])
def test_valid_generic_production_settings_opt_out_only_of_optional_history(learning, lane):
    from note_authorship_gate import check_history_learning_from_settings
    config = json.loads(learning['settings'].read_text())
    del config['style']['history_learning_policy']
    learning['settings'].write_text(json.dumps(config))
    learning['draft'].write_text(f'---\narticle_lane: {lane}\n---\nBody.\n')
    checked = check_history_learning_from_settings(learning['draft'], learning['settings'], 'article')
    assert checked['status'] == 'not_required'
    assert checked['errors'] == []
    script = Path(__file__).resolve().parents[1] / 'scripts/note_authorship_gate.py'
    strict = subprocess.run([sys.executable, str(script), str(learning['draft']), '--history-only',
        '--settings', str(learning['settings']), '--article-id', 'article', '--json'],
        capture_output=True, text=True)
    assert strict.returncode == 1
    assert json.loads(strict.stdout)['status'] == 'not_required'


@pytest.mark.parametrize('lane', ['production_candidate', 'continuation_article'])
@pytest.mark.parametrize('policy', ['absent', 'optional'])
@pytest.mark.parametrize('article_id', [None, '', '   ', 17])
def test_production_qa_requires_article_identity_even_with_optional_history(learning, lane, policy, article_id):
    from pre_publish_check import check_draft
    config = json.loads(learning['settings'].read_text())
    if policy == 'absent':
        del config['style']['history_learning_policy']
    else:
        config['style']['history_learning_policy']['required'] = False
    learning['settings'].write_text(json.dumps(config))
    learning['draft'].write_text(f'---\narticle_lane: {lane}\n---\nBody.\n')
    result = check_draft(learning['draft'], settings_path=learning['settings'], article_id=article_id)
    assert any(i['code'] == 'workspace_style_unverified' for i in result['issues'])


def test_optional_history_qa_does_not_require_article_id(learning):
    from pre_publish_check import check_draft
    config = json.loads(learning['settings'].read_text())
    config['style']['history_learning_policy']['required'] = False
    learning['settings'].write_text(json.dumps(config))
    learning['draft'].write_text('---\narticle_lane: exploratory_draft\n---\nBody.\n')
    result = check_draft(learning['draft'], settings_path=learning['settings'])
    assert not any(i['code'].startswith('history_') for i in result['issues'])


@pytest.mark.parametrize('changed', ['current', 'proposed'])
def test_changed_edit_proposal_uses_current_feedback_and_proposed_application(learning, monkeypatch, changed):
    from note_authorship_gate import check_history_learning_from_settings, excerpt_id
    from note_workflow_gate import check_packet, read_workspace_settings
    from note_feedback import read_article_feedback
    proposal = learning['root'] / 'drafts/proposed.md'
    proposal.write_text('本人の言葉を保つ。修正後の本文。')
    target_sha = hashlib.sha256(proposal.read_bytes()).hexdigest()
    evidence = json.loads(learning['evidence'].read_text())
    evidence['draft_sha256'] = target_sha
    evidence_path = proposal.with_suffix('.authorship.json')
    evidence_path.write_text(json.dumps(evidence))
    record_path = learning['root'] / 'feedback/article/feedback.json'
    record = json.loads(record_path.read_text())
    record['entries'][0].update(target_sha256=target_sha,
        target_excerpt_id=excerpt_id('本人の言葉を保つ。'))
    record_path.write_text(json.dumps(record))
    config, dirs = read_workspace_settings(learning['settings'], 'article')
    packet = dict(schema_version='note-workflow-review/v1', article_id='article', conversation_id='current',
        route='direct_draft', receipts=[], source_snapshot=str(learning['source']), draft=str(learning['draft']),
        proposed_draft=str(proposal), edit_plan={'toc': False}, settings={'account': 'example'},
        ssot_readback=config, history_evidence=str(evidence_path),
        feedback_readback=read_article_feedback(dirs, 'article', learning['source'], learning['draft']))
    result = check_packet(packet, 'edit', 'current', settings_path=learning['settings'])
    assert result['history_learning']['status'] == 'mechanical_ok'
    assert result['history_learning']['hashes']['target'] == target_sha
    sha = result['subject_hashes']['edit']
    packet['receipts'].append(dict(stage='edit', article_id='article', conversation_id='current', actor='user',
        status='approved', subject_sha256=sha, observed_at='2026-10-12T00:00:00+09:00', evidence_ref='fixture://approval'))
    assert check_packet(packet, 'edit', 'current', settings_path=learning['settings'])['status'] == 'approved'
    assert check_history_learning_from_settings(proposal, learning['settings'], 'article', evidence_path)['status'] == 'blocked'
    note_authorship_gate = nps_script_loader.load_script("note_authorship_gate")
    check_history_learning_from_settings = note_authorship_gate.check_history_learning_from_settings
    original = note_authorship_gate.evaluate_history_learning
    def changed_after_evaluation(*args, **kwargs):
        checked = original(*args, **kwargs)
        path = learning['draft'] if changed == 'current' else proposal
        path.write_text(path.read_text() + '\n検査中の変更')
        return checked
    monkeypatch.setattr(note_authorship_gate, 'evaluate_history_learning', changed_after_evaluation)
    checked = check_history_learning_from_settings(proposal, learning['settings'], 'article', evidence_path,
        current_draft=learning['draft'])
    assert checked['status'] == 'blocked'
    assert 'history_target_changed_during_context' in checked['errors']


def test_collection_before_new_draft_does_not_claim_adoption(learning):
    from note_feedback import history_readback
    learning['draft'].unlink()
    result = history_readback(learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'candidate_sources_verified'
    assert result['semantic_understanding_verified'] is False
    assert result['human_adoption_verified'] is False


@pytest.mark.parametrize('status', ['applied', 'preserved', 'not_applicable'])
def test_research_receives_only_actual_history_application_refs(learning, monkeypatch, status):
    from note_workflow_gate import check_packet, read_workspace_settings
    from note_feedback import read_article_feedback
    note_research_quality = nps_script_loader.load_script("note_research_quality")
    config = json.loads(learning['settings'].read_text())
    config['research_quality_policy'] = dict(schema_version='nps-research-quality-policy/v1',
        required=True, max_age_days={'official': 30, 'creator': 30, 'dynamic': 7})
    learning['settings'].write_text(json.dumps(config))
    row = learning['record']['entries'][0]
    row['application_status'] = status
    if status == 'preserved':
        row['before'] = row['after']
    elif status == 'not_applicable':
        row.update(before='', after='', reason='今回の話題には該当しない')
        row.pop('target_excerpt_id')
    (learning['root'] / 'feedback/article/feedback.json').write_text(json.dumps(learning['record']))
    expected, dirs = read_workspace_settings(learning['settings'], 'article')
    report = learning['root'] / 'drafts/report.json'
    report.write_text('{}')
    captured = []
    def inspect_refs(*args, **kwargs):
        captured.append(kwargs['history_application_refs'])
        return {}
    monkeypatch.setattr(note_research_quality, 'check_quality_report', inspect_refs)
    packet = dict(schema_version='note-workflow-review/v1', article_id='article',
        conversation_id='current', route='direct_draft', receipts=[],
        source_snapshot=str(learning['source']), draft=str(learning['draft']),
        proposed_draft=str(learning['draft']), research_report=str(report), edit_plan={},
        ssot_readback=expected,
        feedback_readback=read_article_feedback(dirs, 'article', learning['source'], learning['draft']),
        history_evidence=str(learning['evidence']))
    result = check_packet(packet, 'research', 'current', settings_path=learning['settings'])
    assert result['history_learning']['status'] == 'mechanical_ok'
    assert captured == [set() if status == 'not_applicable' else {row['evidence_ref']}]


@pytest.mark.parametrize('problem', ['missing', 'changed', 'outside', 'quote', 'hash', 'ref', 'duplicate'])
def test_history_sources_fail_closed(learning, problem):
    from note_feedback import history_readback
    data = json.loads(learning['evidence'].read_text())
    row = data['history_learning']['sources'][0]
    if problem == 'missing': data['history_learning']['sources'] = []
    elif problem == 'changed': learning['style'].write_text('変更された規則')
    elif problem == 'outside': row['path'] = str(learning['source'])
    elif problem == 'quote': row['quote'] = '保存されていない原文'
    elif problem == 'hash': row['sha256'] = '0' * 64
    elif problem == 'ref': row['evidence_ref'] = ''
    elif problem == 'duplicate': data['history_learning']['sources'].append(dict(row))
    learning['evidence'].write_text(json.dumps(data))
    with pytest.raises(ValueError):
        history_readback(learning['settings'], 'article', learning['evidence'])


def test_application_checks_after_and_current_version(learning):
    from note_authorship_gate import evaluate_history_learning
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert result['status'] == 'mechanical_ok'
    assert result['human_adoption_verified'] is False


@pytest.mark.parametrize('profile', [None, []])
def test_required_history_rejects_unknown_or_empty_article_profile(learning, profile):
    from note_workflow_gate import read_workspace_settings
    config = json.loads(learning['settings'].read_text())
    config['style']['article_profiles'] = {} if profile is None else {'article': profile}
    learning['settings'].write_text(json.dumps(config))
    with pytest.raises(ValueError):
        read_workspace_settings(learning['settings'], 'article')


def require_rule(learning):
    config = json.loads(learning['settings'].read_text())
    candidate = learning['candidate']
    config['style']['history_learning_policy']['required_sources'] = [
        {key: candidate[key] for key in ('id', 'path', 'quote', 'evidence_ref')}]
    learning['settings'].write_text(json.dumps(config))


@pytest.mark.parametrize('change', ['missing', 'id', 'quote', 'ref'])
def test_required_history_rule_cannot_be_omitted_or_relabelled(learning, change):
    from note_feedback import history_readback
    require_rule(learning)
    data = json.loads(learning['evidence'].read_text())
    row = data['history_learning']['sources'][0]
    if change == 'missing':
        data['history_learning']['sources'] = []
    elif change == 'id':
        row['id'] = 'different-rule'
    elif change == 'quote':
        row['quote'] = '本人の言葉を保つ。'
    else:
        row['evidence_ref'] = 'other-root'
    learning['evidence'].write_text(json.dumps(data))
    with pytest.raises(ValueError):
        history_readback(learning['settings'], 'article', learning['evidence'])


def test_settings_history_api_binds_required_rules_and_current_target(learning):
    from note_authorship_gate import check_history_learning_from_settings
    require_rule(learning)
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'mechanical_ok'
    assert result['human_adoption_verified'] is False
    data = json.loads(learning['evidence'].read_text())
    data['history_learning']['sources'][0]['quote'] = '本人の言葉を保つ。'
    learning['evidence'].write_text(json.dumps(data))
    assert check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])['status'] == 'blocked'


def test_settings_history_api_missing_evidence_and_production_context_stop(learning):
    from note_authorship_gate import check_history_learning_from_settings
    learning['evidence'].unlink()
    assert check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article')['status'] == 'blocked'
    learning['draft'].write_text('---\narticle_lane: production_candidate\n---\n原稿')
    assert check_history_learning_from_settings(learning['draft'], None, None)['status'] == 'blocked'


def test_continuation_qa_requires_explicit_settings(learning):
    from pre_publish_check import check_draft
    learning['draft'].write_text('---\narticle_lane: continuation_article\n---\n原稿')
    result = check_draft(learning['draft'], article_id='article')
    assert 'history_learning_settings_required' in [row['code'] for row in result['issues']]


def test_history_only_cli_requires_context_and_consumes_good_snapshot(learning):
    script = Path('scripts/note_authorship_gate.py')
    base = [sys.executable, str(script), str(learning['draft']), '--history-only', '--json']
    missing = subprocess.run(base, capture_output=True, text=True)
    assert missing.returncode == 1
    assert json.loads(missing.stdout)['status'] == 'blocked'
    good = subprocess.run(base + ['--settings', str(learning['settings']), '--article-id', 'article',
                                  '--evidence', str(learning['evidence'])], capture_output=True, text=True)
    assert good.returncode == 0, good.stdout
    assert json.loads(good.stdout)['status'] == 'mechanical_ok'


def test_four_required_rules_fail_when_one_is_missing_and_paths_are_portable(learning):
    from note_feedback import history_readback
    learning['style'].write_text('規則A\n規則B\n規則C\n規則D', encoding='utf-8')
    sha = hashlib.sha256(learning['style'].read_bytes()).hexdigest()
    sources = [dict(id=f'rule-{i}', path=str(learning['style']), sha256=sha,
                    quote=f'規則{letter}', evidence_ref=f'history.md#rule-{i}')
               for i, letter in enumerate('ABCD')]
    data = json.loads(learning['evidence'].read_text())
    data['history_learning']['sources'] = sources
    learning['evidence'].write_text(json.dumps(data))
    config = json.loads(learning['settings'].read_text())
    config['style']['history_learning_policy']['required_sources'] = [
        {**{key: source[key] for key in ('id', 'quote', 'evidence_ref')}, 'path': 'history.md'}
        for source in sources]
    learning['settings'].write_text(json.dumps(config))
    assert len(history_readback(learning['settings'], 'article', learning['evidence'])['sources']) == 4
    data['history_learning']['sources'] = sources[:3]
    learning['evidence'].write_text(json.dumps(data))
    with pytest.raises(ValueError, match='必須history source'):
        history_readback(learning['settings'], 'article', learning['evidence'])


def test_required_source_outside_style_allowlist_stops_at_settings_readback(learning):
    from note_workflow_gate import read_workspace_settings
    require_rule(learning)
    config = json.loads(learning['settings'].read_text())
    config['style']['history_learning_policy']['required_sources'][0]['path'] = str(learning['source'])
    learning['settings'].write_text(json.dumps(config))
    with pytest.raises(ValueError, match='style許可参照'):
        read_workspace_settings(learning['settings'], 'article')


def test_settings_history_api_rejects_feedback_snapshot_for_another_target(learning):
    from note_authorship_gate import check_history_learning_from_settings
    learning['draft'].write_text(learning['draft'].read_text() + '\n追加した本文')
    target_hash = hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
    data = json.loads(learning['evidence'].read_text())
    data['draft_sha256'] = target_hash
    learning['evidence'].write_text(json.dumps(data))
    learning['record']['entries'][0]['target_sha256'] = target_hash
    (learning['root'] / 'feedback/article/feedback.json').write_text(json.dumps(learning['record']))
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'
    assert 'history_feedback_target_mismatch' in result['errors']


def test_settings_history_api_rejects_target_swap_during_final_context_read(learning, monkeypatch):
    from note_authorship_gate import check_history_learning_from_settings
    note_workflow_gate = nps_script_loader.load_script("note_workflow_gate")
    original = note_workflow_gate.read_workspace_settings
    calls = 0

    def swap_during_reread(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            learning['draft'].write_text(learning['draft'].read_text(encoding='utf-8') + '\n未検査の変更', encoding='utf-8')
        return original(*args, **kwargs)

    monkeypatch.setattr(note_workflow_gate, 'read_workspace_settings', swap_during_reread)
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'
    assert 'history_target_changed_during_context' in result['errors']


def test_qa_rejects_target_swap_between_editorial_scan_and_history_check(learning, monkeypatch):
    pre_publish_check = nps_script_loader.load_script("pre_publish_check")
    from note_feedback import record_feedback
    original = pre_publish_check.collect_issues

    def swap_after_editorial_scan(text):
        issues = original(text)
        learning['draft'].write_text(text + '\n<!-- 未検査のHTMLコメント -->')
        sha = hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
        data = json.loads(learning['evidence'].read_text())
        data['draft_sha256'] = sha
        learning['evidence'].write_text(json.dumps(data))
        entries = [dict(row, target_sha256=sha) for row in learning['record']['entries']]
        dirs = {key: learning['root'] / key for key in ('sources', 'drafts', 'feedback')}
        record_feedback(dirs, 'article', learning['source'], learning['draft'],
                        learning['root'] / 'sources/prior.md', entries, conversation_id='current')
        return issues

    monkeypatch.setattr(pre_publish_check, 'collect_issues', swap_after_editorial_scan)
    result = pre_publish_check.check_draft(learning['draft'], settings_path=learning['settings'],
                                          article_id='article', authorship_evidence=learning['evidence'])
    assert 'draft_changed_during_check' in [row['code'] for row in result['issues']]


def test_plain_authorship_cli_rejects_legacy_to_history_target_swap(learning, monkeypatch, capsys):
    note_authorship_gate = nps_script_loader.load_script("note_authorship_gate")
    from note_feedback import record_feedback
    original = note_authorship_gate.evaluate

    def swap_after_authorship(*args, **kwargs):
        result = original(*args, **kwargs)
        learning['draft'].write_text(learning['draft'].read_text() + '\n僕は実際に体験しました。')
        sha = hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
        data = json.loads(learning['evidence'].read_text())
        data['draft_sha256'] = sha
        learning['evidence'].write_text(json.dumps(data))
        entries = [dict(row, target_sha256=sha) for row in learning['record']['entries']]
        dirs = {key: learning['root'] / key for key in ('sources', 'drafts', 'feedback')}
        record_feedback(dirs, 'article', learning['source'], learning['draft'],
                        learning['root'] / 'sources/prior.md', entries, conversation_id='current')
        return result

    monkeypatch.setattr(note_authorship_gate, 'evaluate', swap_after_authorship)
    monkeypatch.setattr(sys, 'argv', ['note_authorship_gate.py', str(learning['draft']), '--json',
        '--settings', str(learning['settings']), '--article-id', 'article', '--evidence', str(learning['evidence'])])
    assert note_authorship_gate.main() == 1
    assert json.loads(capsys.readouterr().out)['overall'] == 'blocked'


def test_source_capture_binds_draft_hash_to_evidence_snapshot(learning):
    from note_feedback import read_history_sources
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    captured = read_history_sources(learning['evidence'], refs)
    assert captured['draft_sha256'] == hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
    assert captured['evidence_sha256'] == hashlib.sha256(learning['evidence'].read_bytes()).hexdigest()


@pytest.mark.parametrize('binding', [None, '0' * 64])
def test_application_rejects_missing_or_wrong_evidence_draft_binding(learning, binding):
    from note_authorship_gate import evaluate_history_learning
    data = json.loads(learning['evidence'].read_text())
    if binding is None:
        data.pop('draft_sha256')
    else:
        data['draft_sha256'] = binding
    learning['evidence'].write_text(json.dumps(data))
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert result['status'] == 'blocked'


def test_collection_without_draft_binding_remains_candidate_only(learning):
    from note_feedback import history_readback
    data = json.loads(learning['evidence'].read_text())
    data.pop('draft_sha256')
    learning['evidence'].write_text(json.dumps(data))
    result = history_readback(learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'candidate_sources_verified'
    assert result['human_adoption_verified'] is False


def test_application_rejects_evidence_replaced_before_source_capture(learning, monkeypatch):
    from note_authorship_gate import evaluate_history_learning
    note_feedback = nps_script_loader.load_script("note_feedback")
    original = note_feedback.read_history_sources

    def replace_before_capture(evidence, reference_hashes, **kwargs):
        data = json.loads(evidence.read_text(encoding='utf-8'))
        data['draft_sha256'] = '0' * 64
        evidence.write_text(json.dumps(data), encoding='utf-8')
        return original(evidence, reference_hashes, **kwargs)

    monkeypatch.setattr(note_feedback, 'read_history_sources', replace_before_capture)
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert result['status'] == 'blocked'


def test_application_rejects_evidence_mutated_after_source_capture(learning, monkeypatch):
    from note_authorship_gate import evaluate_history_learning
    note_feedback = nps_script_loader.load_script("note_feedback")
    original = note_feedback.read_history_sources

    def replace_after_capture(evidence, reference_hashes, **kwargs):
        captured = original(evidence, reference_hashes, **kwargs)
        data = json.loads(evidence.read_text(encoding='utf-8'))
        data['changed_after_capture'] = True
        evidence.write_text(json.dumps(data), encoding='utf-8')
        return captured

    monkeypatch.setattr(note_feedback, 'read_history_sources', replace_after_capture)
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert result['status'] == 'blocked'
    assert 'history_target_changed_during_read' in result['errors']


@pytest.mark.parametrize('problem', ['old_hash', 'after_missing', 'excerpt', 'source_id', 'no_application', 'ref'])
def test_application_rejects_claim_without_application(learning, problem):
    from note_authorship_gate import evaluate_history_learning
    row = learning['record']['entries'][0]
    if problem == 'old_hash': row['target_sha256'] = '0' * 64
    elif problem == 'after_missing': row['after'] = '実本文にない文'
    elif problem == 'excerpt': row['target_excerpt_id'] = 'bad'
    elif problem == 'source_id': row['history_source_id'] = 'unknown'
    elif problem == 'no_application': learning['record']['entries'] = []
    elif problem == 'ref': row['evidence_ref'] = 'other.md'
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    assert evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)['status'] == 'blocked'


def test_history_only_cli_is_read_only(learning):
    before = {p: p.read_bytes() for p in learning['root'].rglob('*') if p.is_file()}
    result = subprocess.run([sys.executable, 'scripts/note_feedback.py', '--settings', str(learning['settings']),
        '--article-id', 'article', '--readback', '--history-only', '--history-evidence', str(learning['evidence'])],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'candidate_sources_verified'
    assert before == {p: p.read_bytes() for p in learning['root'].rglob('*') if p.is_file()}


def test_preserved_and_not_applicable_are_explicit(learning):
    from note_authorship_gate import evaluate_history_learning
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    row = learning['record']['entries'][0]
    row.update(application_status='preserved', before=row['after'])
    assert evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)['status'] == 'mechanical_ok'
    row.update(application_status='not_applicable', before='', after='', reason='今回の対象話題には該当しない')
    row.pop('target_excerpt_id')
    assert evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)['status'] == 'mechanical_ok'
    row['reason'] = ''
    assert evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)['status'] == 'blocked'


def test_continuation_qa_checks_required_history_and_legacy_optout(learning):
    from pre_publish_check import check_draft
    learning['draft'].write_text('---\narticle_lane: continuation_article\n---\n本人の言葉を保つ。')
    evidence = json.loads(learning['evidence'].read_text())
    evidence['draft_sha256'] = hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
    learning['evidence'].write_text(json.dumps(evidence))
    record_path = learning['root'] / 'feedback/article/feedback.json'
    record = json.loads(record_path.read_text()); record['entries'][0]['target_sha256'] = '0' * 64
    record_path.write_text(json.dumps(record))
    result = check_draft(learning['draft'], settings_path=learning['settings'], article_id='article')
    assert 'history_application_target_mismatch' in [i['code'] for i in result['issues']]
    config = json.loads(learning['settings'].read_text())
    config['style']['history_learning_policy']['required'] = False
    learning['settings'].write_text(json.dumps(config))
    assert not any(i['code'].startswith('history_') for i in check_draft(
        learning['draft'], settings_path=learning['settings'], article_id='article')['issues'])


@pytest.mark.parametrize('text', ['---\ntitle: 本人の言葉を保つ。\n---\n別の本文',
    '---\r\ntitle: 本人の言葉を保つ。\r\n---\r\n別の本文',
    '\ufeff---\ntitle: 本人の言葉を保つ。\n---\n別の本文'])
def test_application_in_frontmatter_is_not_body_application(learning, text):
    from note_authorship_gate import evaluate_history_learning
    learning['draft'].write_bytes(text.encode('utf-8'))
    target_hash = hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
    evidence = json.loads(learning['evidence'].read_text()); evidence['draft_sha256'] = target_hash
    learning['evidence'].write_text(json.dumps(evidence))
    learning['record']['entries'][0]['target_sha256'] = target_hash
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert 'history_application_after_missing' in result['errors']


def test_edit_plan_json_requires_reviewed_full_body_and_hash_binding(learning):
    from note_workflow_gate import check_packet, read_workspace_settings
    from note_feedback import read_article_feedback
    config, dirs = read_workspace_settings(learning['settings'], 'article')
    proposal = learning['root'] / 'drafts/patch.json'
    proposal.write_text(json.dumps({'text': '局所編集の提案'}))
    packet = dict(schema_version='note-workflow-review/v1', article_id='article', conversation_id='current',
        route='direct_draft', receipts=[], source_snapshot=str(learning['source']), draft=str(learning['draft']),
        proposed_draft=str(proposal), edit_plan={'toc': False}, settings={'account': 'example'},
        ssot_readback=config, history_evidence=str(learning['evidence']),
        feedback_readback=read_article_feedback(dirs, 'article', learning['source'], learning['draft']))
    result = check_packet(packet, 'edit', 'current', settings_path=learning['settings'])
    assert 'history_application' not in result['content_hashes']
    packet['edit_plan']['history_application_target'] = str(learning['draft'])
    result = check_packet(packet, 'edit', 'current', settings_path=learning['settings'])
    assert result['history_learning']['status'] == 'mechanical_ok'
    assert result['history_learning']['hashes']['target'] == hashlib.sha256(learning['draft'].read_bytes()).hexdigest()
    sha = result['subject_hashes']['edit']
    packet['receipts'].append(dict(stage='edit', article_id='article', conversation_id='current', actor='user',
        status='approved', subject_sha256=sha, observed_at='2026-10-12T00:00:00+09:00', evidence_ref='fixture://approval'))
    assert check_packet(packet, 'edit', 'current', settings_path=learning['settings'])['status'] == 'approved'
    learning['style'].write_text('本人の規則を変更')
    assert check_packet(packet, 'edit', 'current', settings_path=learning['settings'])['status'] == 'blocked'


def test_json_history_quote_uses_explicit_pointer(learning):
    from note_feedback import read_history_sources
    source = learning['root'] / 'historical.json'
    source.write_text(json.dumps({'entries': [{'after': '本人の原文\n改行を保持'}]}, ensure_ascii=False))
    data = json.loads(learning['evidence'].read_text())
    row = data['history_learning']['sources'][0]
    row.update(path=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               quote='本人の原文\n改行を保持', json_pointer='/entries/0/after')
    learning['evidence'].write_text(json.dumps(data))
    assert read_history_sources(learning['evidence'], {str(source): row['sha256']})['status'] == 'candidate_sources_verified'


def test_research_article_local_requires_application_while_future_loops_stay_planned(learning):
    from datetime import datetime, timezone
    from note_research_quality import AREAS, LOOPS, check_quality_report
    policy = dict(schema_version='nps-research-quality-policy/v1', required=True,
                  max_age_days={'official':30, 'creator':30, 'dynamic':7})
    source_id = 'historical-rule'
    evidence_ref = learning['record']['entries'][0]['evidence_ref']
    report = dict(schema_version='note-research-quality/v1', article_id='article', topic='本人語の編集',
        sources=[dict(id=source_id, kind='creator', url='https://example.com/previous',
            readback='保存した本人の修正を読む', observed_at=datetime.now(timezone.utc).isoformat(),
            evidence_path=str(learning['style']), evidence_sha256=hashlib.sha256(learning['style'].read_bytes()).hexdigest())],
        areas={area: dict(status='pass', reason='実資料と照合', decision='候補として確認',
                         source_ids=[source_id], unresolved=[]) for area in AREAS},
        pdca_loops=[dict(scope=scope, owner='主担当', change='本人語の保全', measure='本文の差分',
            when='適用時に確認', feedback_entry_ref=evidence_ref, status='planned', missing_data=[], constraints=[])
            for scope in LOOPS])
    arguments = dict(article_id='article', base_dir=learning['root'], feedback_refs={evidence_ref},
                     history_application_refs={evidence_ref})
    with pytest.raises(ValueError, match='article_local'):
        check_quality_report(json.dumps(report).encode(), policy, **arguments)
    local = next(row for row in report['pdca_loops'] if row['scope'] == 'article_local')
    local.update(status='observed', result='現版の本文へ反映を照合', source_id=source_id)
    assert check_quality_report(json.dumps(report).encode(), policy, **arguments)


def test_history_body_accepts_crlf_and_bom_without_rewriting_raw_hash(learning):
    from note_authorship_gate import evaluate_history_learning, excerpt_id
    after = '本人の言葉を保つ。\n続きの本文。'
    raw = ('\ufeff---\r\ntitle: Example\r\n---\r\n' + after.replace('\n', '\r\n')).encode('utf-8')
    learning['draft'].write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    evidence = json.loads(learning['evidence'].read_text()); evidence['draft_sha256'] = sha
    learning['evidence'].write_text(json.dumps(evidence))
    learning['record']['entries'][0].update(after=after, target_sha256=sha, target_excerpt_id=excerpt_id(after))
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    result = evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)
    assert result['status'] == 'mechanical_ok'
    assert result['hashes']['target'] == sha
    assert learning['draft'].read_bytes() == raw


def test_history_body_unclosed_frontmatter_is_blocked(learning):
    from note_authorship_gate import evaluate_history_learning
    raw = '---\ntitle: 本人の言葉を保つ。\n未閉じ'.encode('utf-8')
    learning['draft'].write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    evidence = json.loads(learning['evidence'].read_text()); evidence['draft_sha256'] = sha
    learning['evidence'].write_text(json.dumps(evidence))
    learning['record']['entries'][0]['target_sha256'] = sha
    refs = {str(learning['style']): hashlib.sha256(learning['style'].read_bytes()).hexdigest()}
    assert evaluate_history_learning(learning['draft'], learning['evidence'], learning['record'], refs)['status'] == 'blocked'


@pytest.mark.parametrize('destination', ['Windows layout', 'Mac移動先', 'VM workspace'])
def test_relative_history_survives_workspace_relocation(learning, tmp_path, destination):
    import shutil
    from note_authorship_gate import check_history_learning_from_settings
    evidence = learning['evidence']
    data = json.loads(evidence.read_text(encoding='utf-8'))
    data['history_learning']['sources'][0]['path'] = '../history.md'
    evidence.write_text(json.dumps(data), encoding='utf-8')
    cfg = json.loads(learning['settings'].read_text(encoding='utf-8'))
    required = dict(learning['candidate'], path='history.md')
    required.pop('sha256')
    cfg['style']['history_learning_policy']['required_sources'] = [required]
    learning['settings'].write_text(json.dumps(cfg), encoding='utf-8')
    assert check_history_learning_from_settings(learning['draft'], learning['settings'], 'article', evidence)['status'] == 'mechanical_ok'
    moved = tmp_path.parent / (tmp_path.name + destination)
    shutil.copytree(learning['root'], moved)
    try:
        result = check_history_learning_from_settings(moved/'drafts/current.md', moved/'settings.json', 'article', moved/'drafts/current.authorship.json')
        assert result['status'] == 'mechanical_ok'
        assert all(str(moved) in name for name in result['settings_readback']['reference_hashes'])
        assert '../history.md' == json.loads((moved/'drafts/current.authorship.json').read_text(encoding='utf-8'))['history_learning']['sources'][0]['path']
        (moved/'history.md').write_text('changed source', encoding='utf-8')
        assert check_history_learning_from_settings(moved/'drafts/current.md', moved/'settings.json', 'article', moved/'drafts/current.authorship.json')['status'] == 'blocked'
    finally:
        shutil.rmtree(moved)


def test_relative_history_cannot_escape_allowed_sources(learning):
    from note_authorship_gate import check_history_learning_from_settings
    data = json.loads(learning['evidence'].read_text(encoding='utf-8'))
    data['history_learning']['sources'][0]['path'] = '../sources/current.md'
    learning['evidence'].write_text(json.dumps(data), encoding='utf-8')
    assert check_history_learning_from_settings(learning['draft'], learning['settings'], 'article', learning['evidence'])['status'] == 'blocked'


@pytest.mark.parametrize('required', [False, True])
def test_setup_readback_exposes_configured_storage_without_writing(learning, required):
    from note_feedback import history_readback
    config = json.loads(learning['settings'].read_text())
    config['storage']['drafts'] = 'writing/原稿 with spaces'
    if not required:
        config['style'].pop('history_learning_policy')
    learning['settings'].write_text(json.dumps(config))
    before = {p: p.read_bytes() for p in learning['root'].rglob('*') if p.is_file()}
    result = history_readback(learning['settings'], 'article', learning['evidence'] if required else None)
    assert Path(result['storage']['drafts']) == (learning['root'] / 'writing/原稿 with spaces').resolve()
    assert result['settings_readback']['settings_sha256'] == hashlib.sha256(learning['settings'].read_bytes()).hexdigest()
    assert before == {p: p.read_bytes() for p in learning['root'].rglob('*') if p.is_file()}


@pytest.mark.parametrize('key', ['assets', 'ledgers'])
def test_optional_storage_uses_existing_workspace_boundary(learning, key):
    from note_feedback import history_readback
    config = json.loads(learning['settings'].read_text())
    config['style'].pop('history_learning_policy')
    config['storage'][key] = 'private/' + key
    learning['settings'].write_text(json.dumps(config))
    checked = history_readback(learning['settings'], 'article', None)
    assert Path(checked['storage'][key]) == (learning['root'] / 'private' / key).resolve()
    from note_workflow_gate import PACKAGE_ROOT
    config['storage'][key] = str(PACKAGE_ROOT / 'data')
    learning['settings'].write_text(json.dumps(config))
    with pytest.raises(ValueError, match='package外'):
        history_readback(learning['settings'], 'article', None)


def test_storage_rejects_existing_regular_file(learning):
    from note_feedback import history_readback
    config = json.loads(learning['settings'].read_text())
    config['storage']['assets'] = str(learning['style'])
    learning['settings'].write_text(json.dumps(config))
    with pytest.raises(ValueError, match='ディレクトリ'):
        history_readback(learning['settings'], 'article', learning['evidence'])


def add_article_rule(learning, *, global_required=True):
    """Extend the existing workspace fixture without changing production settings."""
    config = json.loads(learning['settings'].read_text())
    rule = {key: learning['candidate'][key] for key in ('id', 'path', 'quote', 'evidence_ref')}
    config['style']['history_learning_policy'] = dict(
        schema='nps-history-learning-policy/v1', required=global_required, required_sources=[rule])
    scoped = dict(rule, id='article-rule', quote='本人の言葉を保つ。')
    config['style']['article_profiles']['article'] = dict(
        references=['history.md'], history_learning_policy=dict(
            schema='nps-history-learning-policy/v1', required=True, required_sources=[scoped]))
    config['style']['article_profiles']['other'] = ['history.md']
    learning['settings'].write_text(json.dumps(config))
    return config, scoped


def test_article_history_union_and_other_article_isolation(learning):
    from note_workflow_gate import read_workspace_settings
    _, scoped = add_article_rule(learning)
    selected, _ = read_workspace_settings(learning['settings'], 'article')
    other, _ = read_workspace_settings(learning['settings'], 'other')
    assert [row['id'] for row in selected['history_learning_policy']['required_sources']] == ['rule-1', scoped['id']]
    assert [row['id'] for row in other['history_learning_policy']['required_sources']] == ['rule-1']


@pytest.mark.parametrize('global_required,scoped_required', [(True, False), (False, True)])
def test_article_history_cannot_weaken_required(learning, global_required, scoped_required):
    from note_workflow_gate import read_workspace_settings
    config, _ = add_article_rule(learning, global_required=global_required)
    config['style']['article_profiles']['article']['history_learning_policy']['required'] = scoped_required
    learning['settings'].write_text(json.dumps(config))
    selected, _ = read_workspace_settings(learning['settings'], 'article')
    assert selected['history_learning_policy']['required'] is True


@pytest.mark.parametrize('problem', ['duplicate', 'conflict', 'not_profile_reference', 'malformed', 'missing_id'])
def test_article_history_invalid_declarations_fail_closed(learning, problem):
    from note_workflow_gate import read_workspace_settings
    config, _ = add_article_rule(learning)
    profile = config['style']['article_profiles']['article']
    if problem in ('duplicate', 'conflict'):
        profile['history_learning_policy']['required_sources'][0]['id'] = 'rule-1'
        if problem == 'duplicate':
            profile['history_learning_policy']['required_sources'] = config['style']['history_learning_policy']['required_sources']
    elif problem == 'not_profile_reference':
        (learning['root'] / 'other.md').write_text('別の文体参照')
        profile['references'] = ['other.md']  # history.md remains default, not selected profile.
    elif problem == 'malformed':
        profile['history_learning_policy'] = None
    learning['settings'].write_text(json.dumps(config))
    with pytest.raises(ValueError):
        read_workspace_settings(learning['settings'], '' if problem == 'missing_id' else 'article')


@pytest.mark.parametrize('problem', ['missing_source', 'missing_application', 'wrong_after', 'none'])
@pytest.mark.parametrize('status', ['applied', 'preserved'])
@pytest.mark.parametrize('with_global', [True, False])
def test_article_required_rule_reaches_existing_g2(learning, problem, status, with_global):
    from note_authorship_gate import check_history_learning_from_settings
    from note_feedback import record_feedback
    from note_authorship_gate import excerpt_id
    config, scoped = add_article_rule(learning)
    if not with_global:
        del config['style']['history_learning_policy']
        learning['settings'].write_text(json.dumps(config))
    evidence = json.loads(learning['evidence'].read_text())
    if problem != 'missing_source':
        evidence['history_learning']['sources'].append(dict(scoped, sha256=learning['candidate']['sha256']))
    learning['evidence'].write_text(json.dumps(evidence))
    entries = list(learning['record']['entries'])
    if problem != 'missing_application':
        after = '現稿にない文' if problem == 'wrong_after' else '本人の言葉を保つ。'
        entries.append(dict(entries[0], history_source_id=scoped['id'], after=after,
                            before=after if status == 'preserved' else entries[0]['before'],
                            application_status=status, target_excerpt_id=excerpt_id(after)))
    dirs = {key: learning['root'] / key for key in ('sources', 'drafts', 'feedback')}
    record_feedback(dirs, 'article', learning['source'], learning['draft'],
                    learning['root'] / 'sources/prior.md', entries, conversation_id='current')
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == ('mechanical_ok' if problem == 'none' else 'blocked')


def test_article_only_required_policy_has_no_generic_opt_out(learning):
    from note_authorship_gate import check_history_learning_from_settings
    config, _ = add_article_rule(learning)
    del config['style']['history_learning_policy']
    learning['settings'].write_text(json.dumps(config))
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'  # scoped source absent; cannot return not_required.
    assert check_history_learning_from_settings(
        learning['draft'], learning['settings'], None, learning['evidence'])['status'] == 'blocked'
