"""Captured history inputs remain available for the caller's final readback."""
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("history_learning_fixture", Path(__file__).with_name("test_history_learning_gate.py"))
assert _SPEC is not None and _SPEC.loader is not None
_FIXTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURE)
learning = _FIXTURE.learning
import nps_script_loader


def test_history_returns_verified_mutable_input_paths(learning):
    from note_authorship_gate import check_history_learning_from_settings

    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'mechanical_ok'
    base = learning['root'] / 'feedback/article'
    expected = {learning['draft'], learning['settings'], learning['style'], learning['evidence'],
                base / 'feedback.json', base / 'note-vs-local-diff.md'}
    expected.update(base / 'snapshots' / (sha + '.txt')
                    for sha in result['feedback_readback']['snapshot_hashes'].values())
    assert set(result['mutable_input_hashes']) == {str(path.resolve()) for path in expected}
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha
               for name, sha in result['mutable_input_hashes'].items())
    role_paths = result['feedback_input_paths']
    assert role_paths['record'] == str(base / 'feedback.json')
    assert role_paths['difference'] == str(base / 'note-vs-local-diff.md')
    assert role_paths['snapshots'] == {role: str(base / 'snapshots' / (sha + '.txt'))
                                      for role, sha in result['feedback_readback']['snapshot_hashes'].items()}
    for selected in [role_paths['record'], role_paths['difference'], *role_paths['snapshots'].values()]:
        assert result['mutable_input_paths'][selected] == str(Path(selected).resolve())


def test_feedback_roles_preserve_same_digest_snapshot_deduplication(learning):
    from note_authorship_gate import check_history_learning_from_settings
    from note_feedback import record_feedback

    learning['source'].write_bytes(learning['draft'].read_bytes())
    dirs = {key: learning['root'] / key for key in ('sources', 'drafts', 'feedback')}
    record_feedback(dirs, 'article', learning['source'], learning['draft'],
                    learning['root'] / 'sources/prior.md', learning['record']['entries'], conversation_id='current')
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'mechanical_ok'
    assert result['feedback_input_paths']['snapshots']['source'] == result['feedback_input_paths']['snapshots']['draft']
    assert set(result['feedback_readback']['snapshot_hashes']) == {'source', 'prior', 'draft'}


@pytest.mark.parametrize('kind', ['record', 'difference', 'source_snapshot'])
@pytest.mark.parametrize('mutation', ['changed', 'missing', 'retarget'])
def test_history_final_feedback_readback_rejects_change(learning, monkeypatch, kind, mutation):
    note_feedback = nps_script_loader.load_script("note_feedback")
    from note_authorship_gate import check_history_learning_from_settings

    base = learning['root'] / 'feedback/article'
    paths = {'record': base / 'feedback.json', 'difference': base / 'note-vs-local-diff.md',
             'source_snapshot': base / 'snapshots' / (learning['record']['snapshot_hashes']['source'] + '.txt')}
    path = paths[kind]
    original = note_feedback.read_feedback_record
    reads = 0

    def changed_after_read(*args, **kwargs):
        nonlocal reads
        result = original(*args, **kwargs)
        reads += 1
        if reads == 2:
            if mutation == 'changed':
                path.write_bytes(path.read_bytes() + b'changed')
            elif mutation == 'missing':
                path.unlink()
            else:
                replacement = base / 'replacement.txt'
                replacement.write_bytes(path.read_bytes())
                path.unlink()
                path.symlink_to(replacement)
        return result

    monkeypatch.setattr(note_feedback, 'read_feedback_record', changed_after_read)
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'
    assert result['errors']


def test_history_preserves_feedback_storage_alias_and_rejects_retarget(learning, monkeypatch):
    note_feedback = nps_script_loader.load_script("note_feedback")
    from note_authorship_gate import check_history_learning_from_settings

    root = learning['root']
    link = root / 'feedback-link'
    link.symlink_to(root / 'feedback', target_is_directory=True)
    replacement = root / 'replacement-feedback'
    shutil.copytree(root / 'feedback', replacement)
    config = json.loads(learning['settings'].read_text())
    config['storage']['feedback'] = 'feedback-link'
    learning['settings'].write_text(json.dumps(config))
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'mechanical_ok'
    logical = str(link / 'article/feedback.json')
    assert result['mutable_input_paths'][logical] == str(root / 'feedback/article/feedback.json')
    original = note_feedback.read_feedback_record
    reads = 0

    def retarget_after_read(*args, **kwargs):
        nonlocal reads
        result = original(*args, **kwargs)
        reads += 1
        if reads == 2:
            link.unlink()
            link.symlink_to(replacement, target_is_directory=True)
        return result

    monkeypatch.setattr(note_feedback, 'read_feedback_record', retarget_after_read)
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'
    assert 'history_mutable_input_path_changed' in result['errors']


@pytest.mark.parametrize('kind', ['required_source', 'evidence_source'])
def test_history_source_alias_same_content_retarget_blocks(learning, monkeypatch, kind):
    note_feedback = nps_script_loader.load_script("note_feedback")
    from note_authorship_gate import check_history_learning_from_settings

    link = learning['root'] / 'rule-link.md'
    link.symlink_to(learning['style'])
    replacement = learning['root'] / 'replacement-rule.md'
    replacement.write_bytes(learning['style'].read_bytes())
    if kind == 'required_source':
        config = json.loads(learning['settings'].read_text())
        candidate = learning['candidate']
        config['style']['history_learning_policy']['required_sources'] = [
            {**{key: candidate[key] for key in ('id', 'quote', 'evidence_ref')}, 'path': link.name}]
        learning['settings'].write_text(json.dumps(config))
    else:
        evidence = json.loads(learning['evidence'].read_text())
        evidence['history_learning']['sources'][0]['path'] = str(link)
        learning['evidence'].write_text(json.dumps(evidence))
    original_draft = learning['draft'].read_bytes()
    original_evidence = learning['evidence'].read_bytes()
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'mechanical_ok'
    assert result['mutable_input_paths'][str(link)] == str(learning['style'])
    original = note_feedback.read_feedback_record
    reads = 0

    def retarget_after_read(*args, **kwargs):
        nonlocal reads
        result = original(*args, **kwargs)
        reads += 1
        if reads == 2:
            link.unlink()
            link.symlink_to(replacement)
        return result

    monkeypatch.setattr(note_feedback, 'read_feedback_record', retarget_after_read)
    result = check_history_learning_from_settings(
        learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert result['status'] == 'blocked'
    assert 'history_mutable_input_path_changed' in result['errors']
    assert learning['draft'].read_bytes() == original_draft
    assert learning['evidence'].read_bytes() == original_evidence


@pytest.mark.parametrize('kind', ['draft', 'settings', 'current_draft', 'evidence'])
@pytest.mark.parametrize('timing', ['before_read', 'after_read'])
def test_major_input_alias_is_captured_before_first_read(learning, monkeypatch, kind, timing):
    from note_authorship_gate import check_history_learning_from_settings

    target = learning['draft']
    baseline = None
    logical = learning['draft'] if kind == 'current_draft' else learning[kind]
    if kind == 'current_draft':
        target = learning['root'] / 'drafts/proposal.md'
        target.write_bytes(learning['draft'].read_bytes())
        baseline = logical
    actual = logical.with_name(logical.name + '.original')
    logical.rename(actual)
    logical.symlink_to(actual)
    replacement = logical.with_name(logical.name + '.replacement')
    replacement.write_bytes(actual.read_bytes())
    assert check_history_learning_from_settings(target, learning['settings'], 'article',
                                                learning['evidence'], current_draft=baseline)['status'] == 'mechanical_ok'
    original_read = Path.read_bytes
    changed = False

    def retarget():
        logical.unlink()
        logical.symlink_to(replacement)

    def swapped(path):
        nonlocal changed
        first = not changed and path in (logical, actual)
        if first:
            changed = True
            if timing == 'before_read':
                retarget()
        value = original_read(path)
        if first and timing == 'after_read':
            retarget()
        return value

    monkeypatch.setattr(Path, 'read_bytes', swapped)
    result = check_history_learning_from_settings(target, learning['settings'], 'article',
                                                  learning['evidence'], current_draft=baseline)
    assert changed
    assert result['status'] == 'blocked'


@pytest.mark.parametrize('policy', ['absent', 'optional', 'no_settings'])
def test_opt_out_still_rejects_first_read_alias_change(learning, monkeypatch, policy):
    from note_authorship_gate import check_history_learning_from_settings

    config = json.loads(learning['settings'].read_text(encoding='utf-8'))
    if policy == 'absent':
        del config['style']['history_learning_policy']
    else:
        config['style']['history_learning_policy']['required'] = False
    learning['settings'].write_text(json.dumps(config), encoding='utf-8')
    settings = None if policy == 'no_settings' else learning['settings']
    logical = learning['draft'] if settings is None else settings
    actual = logical.with_name(logical.name + '.original')
    logical.rename(actual)
    logical.symlink_to(actual)
    replacement = logical.with_name(logical.name + '.replacement')
    replacement.write_bytes(actual.read_bytes())
    assert check_history_learning_from_settings(learning['draft'], settings, 'article')['status'] == 'not_required'
    original_read = Path.read_bytes
    changed = False

    def swapped(path):
        nonlocal changed
        value = original_read(path)
        if not changed and path in (logical, actual):
            changed = True
            logical.unlink()
            logical.symlink_to(replacement)
        return value

    monkeypatch.setattr(Path, 'read_bytes', swapped)
    assert check_history_learning_from_settings(learning['draft'], settings, 'article')['status'] == 'blocked'


@pytest.mark.parametrize('kind', ['evidence', 'source', 'settings', 'workspace_reference'])
@pytest.mark.parametrize('timing', ['before_read', 'after_read'])
def test_g1_first_read_alias_capture_and_same_content_retarget(learning, monkeypatch, kind, timing):
    from note_feedback import history_readback, read_history_sources
    from note_workflow_gate import read_workspace_settings

    actual = learning['style'] if kind in ('source', 'workspace_reference') else learning[kind]
    logical = actual.with_name(actual.name + '.link')
    logical.symlink_to(actual)
    replacement = actual.with_name(actual.name + '.replacement')
    replacement.write_bytes(actual.read_bytes())
    refs = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (learning['style'], replacement)}
    if kind == 'source':
        data = json.loads(learning['evidence'].read_text(encoding='utf-8'))
        data['history_learning']['sources'][0]['path'] = str(logical)
        learning['evidence'].write_text(json.dumps(data), encoding='utf-8')
    elif kind == 'workspace_reference':
        config = json.loads(learning['settings'].read_text(encoding='utf-8'))
        config['style']['default_profile'] = logical.name
        learning['settings'].write_text(json.dumps(config), encoding='utf-8')
    if kind == 'settings':
        execute = lambda: history_readback(logical, 'article', learning['evidence'])
    elif kind == 'workspace_reference':
        execute = lambda: read_workspace_settings(learning['settings'], 'article')
    else:
        execute = lambda: read_history_sources(logical if kind == 'evidence' else learning['evidence'], refs)
    execute()
    original_read = Path.read_bytes
    changed = False

    def swapped(path):
        nonlocal changed
        first = not changed and path in (logical, actual)
        if first:
            changed = True
        if first and timing == 'before_read':
            logical.unlink()
            logical.symlink_to(replacement)
        value = original_read(path)
        if first and timing == 'after_read':
            logical.unlink()
            logical.symlink_to(replacement)
        return value

    monkeypatch.setattr(Path, 'read_bytes', swapped)
    with pytest.raises(ValueError):
        execute()
    assert changed


@pytest.mark.parametrize('kind', ['record', 'difference', 'source_snapshot'])
@pytest.mark.parametrize('timing', ['first_read', 'after_reader_return'])
def test_feedback_first_role_binding_survives_same_content_retarget(learning, monkeypatch, kind, timing):
    note_feedback = nps_script_loader.load_script("note_feedback")
    from note_authorship_gate import check_history_learning_from_settings

    base = learning['root'] / 'feedback/article'
    logical = {'record':base/'feedback.json','difference':base/'note-vs-local-diff.md',
               'source_snapshot':base/'snapshots'/(learning['record']['snapshot_hashes']['source']+'.txt')}[kind]
    actual = logical.with_name(logical.name+'.original')
    logical.rename(actual);logical.symlink_to(actual)
    replacement = logical.with_name(logical.name+'.replacement')
    replacement.write_bytes(actual.read_bytes())
    assert check_history_learning_from_settings(learning['draft'], learning['settings'], 'article', learning['evidence'])['status']=='mechanical_ok'
    changed = False

    def retarget():
        nonlocal changed
        changed = True
        logical.unlink();logical.symlink_to(replacement)

    if timing == 'first_read':
        original = Path.read_bytes
        def swapped(path):
            value = original(path)
            if not changed and path in (logical,actual):retarget()
            return value
        monkeypatch.setattr(Path,'read_bytes',swapped)
    else:
        original = note_feedback.read_feedback_record
        def swapped(*args, **kwargs):
            result = original(*args,**kwargs)
            if not changed:retarget()
            return result
        monkeypatch.setattr(note_feedback,'read_feedback_record',swapped)
    result = check_history_learning_from_settings(learning['draft'], learning['settings'], 'article', learning['evidence'])
    assert changed
    assert result['status']=='blocked'


@pytest.mark.parametrize('kind', ['draft','evidence','source'])
@pytest.mark.parametrize('timing', ['before_read','after_read'])
def test_plain_evaluate_first_read_alias_is_fixed(learning, monkeypatch, kind, timing):
    from note_authorship_gate import evaluate

    source = learning['root']/'sources/plain.md'
    source.write_bytes(learning['draft'].read_bytes())
    logical = source if kind=='source' else learning[kind]
    actual=logical.with_name(logical.name+'.original');logical.rename(actual);logical.symlink_to(actual)
    replacement=logical.with_name(logical.name+'.replacement');replacement.write_bytes(actual.read_bytes())
    assert evaluate(learning['draft'],learning['evidence'],source=source,shortening_stop_causes=[])['overall']=='ok'
    original=Path.read_bytes
    changed=False
    def swapped(path):
        nonlocal changed
        first=not changed and path in (logical,actual)
        if first:changed=True
        if first and timing=='before_read':
            logical.unlink();logical.symlink_to(replacement)
        value=original(path)
        if first and timing=='after_read':
            logical.unlink();logical.symlink_to(replacement)
        return value
    monkeypatch.setattr(Path,'read_bytes',swapped)
    result=evaluate(learning['draft'],learning['evidence'],source=source,shortening_stop_causes=[])
    assert result['overall']=='blocked'
    assert result['snapshot_changed']


@pytest.mark.parametrize('kind', ['settings','source','draft'])
def test_full_g1_readback_keeps_first_selected_input(learning, monkeypatch, kind):
    from note_feedback import readback

    logical=learning[kind]
    actual=logical.with_name(logical.name+'.original');logical.rename(actual);logical.symlink_to(actual)
    replacement=logical.with_name(logical.name+'.replacement');replacement.write_bytes(actual.read_bytes())
    assert readback(learning['settings'],'article',learning['source'],learning['draft'])['status']=='readback'
    original=Path.read_bytes
    changed=False
    def swapped(path):
        nonlocal changed
        value=original(path)
        if not changed and path in (logical,actual):
            changed=True;logical.unlink();logical.symlink_to(replacement)
        return value
    monkeypatch.setattr(Path,'read_bytes',swapped)
    with pytest.raises(ValueError):readback(learning['settings'],'article',learning['source'],learning['draft'])


def test_plain_cli_keeps_first_selected_draft(learning, monkeypatch, capsys):
    note_authorship_gate = nps_script_loader.load_script("note_authorship_gate")

    logical=learning['draft'];actual=logical.with_name(logical.name+'.original')
    logical.rename(actual);logical.symlink_to(actual)
    replacement=logical.with_name(logical.name+'.replacement');replacement.write_bytes(actual.read_bytes())
    monkeypatch.setattr(sys,'argv',['gate',str(logical),'--evidence',str(learning['evidence']),
        '--settings',str(learning['settings']),'--article-id','article','--json'])
    assert note_authorship_gate.main()==0
    capsys.readouterr()
    original=Path.read_bytes
    changed=False
    def swapped(path):
        nonlocal changed
        value=original(path)
        if not changed and path in (logical,actual):
            changed=True;logical.unlink();logical.symlink_to(replacement)
        return value
    monkeypatch.setattr(Path,'read_bytes',swapped)
    assert note_authorship_gate.main()==1
    assert json.loads(capsys.readouterr().out)['snapshot_changed']


def test_g2_keeps_workspace_first_reference_alias_after_reader_returns(learning, monkeypatch):
    note_workflow_gate = nps_script_loader.load_script("note_workflow_gate")
    from note_authorship_gate import check_history_learning_from_settings

    link=learning['root']/'reference-link.md';link.symlink_to(learning['style'])
    replacement=learning['root']/'replacement-reference.md';replacement.write_bytes(learning['style'].read_bytes())
    config=json.loads(learning['settings'].read_text(encoding='utf-8'))
    config['style']['default_profile']=link.name
    config['style']['article_profiles']['article']=[learning['style'].name,replacement.name]
    learning['settings'].write_text(json.dumps(config),encoding='utf-8')
    assert check_history_learning_from_settings(learning['draft'],learning['settings'],'article',learning['evidence'])['status']=='mechanical_ok'
    original=note_workflow_gate.read_workspace_settings
    reads=0
    def swapped(*args, **kwargs):
        nonlocal reads
        result=original(*args,**kwargs);reads+=1
        if reads==1:link.unlink();link.symlink_to(replacement)
        return result
    monkeypatch.setattr(note_workflow_gate,'read_workspace_settings',swapped)
    assert check_history_learning_from_settings(learning['draft'],learning['settings'],'article',learning['evidence'])['status']=='blocked'


@pytest.mark.parametrize('kind',['source','evidence'])
def test_g1_keeps_source_capture_through_final_workspace_read(learning, monkeypatch, kind):
    note_workflow_gate = nps_script_loader.load_script("note_workflow_gate")
    from note_feedback import history_readback

    actual=learning['style'] if kind=='source' else learning['evidence']
    link=actual.with_name(actual.name+'.link');link.symlink_to(actual)
    replacement=actual.with_name(actual.name+'.replacement');replacement.write_bytes(actual.read_bytes())
    config=json.loads(learning['settings'].read_text(encoding='utf-8'))
    if kind=='source':
        data=json.loads(learning['evidence'].read_text(encoding='utf-8'))
        data['history_learning']['sources'][0]['path']=str(link)
        learning['evidence'].write_text(json.dumps(data),encoding='utf-8')
        config['style']['article_profiles']['article'].append(replacement.name)
        learning['settings'].write_text(json.dumps(config),encoding='utf-8')
    evidence=link if kind=='evidence' else learning['evidence']
    assert history_readback(learning['settings'],'article',evidence)['status']=='candidate_sources_verified'
    original=note_workflow_gate.read_workspace_settings
    reads=0
    def swapped(*args, **kwargs):
        nonlocal reads
        result=original(*args,**kwargs);reads+=1
        if reads==2:link.unlink();link.symlink_to(replacement)
        return result
    monkeypatch.setattr(note_workflow_gate,'read_workspace_settings',swapped)
    with pytest.raises(ValueError):history_readback(learning['settings'],'article',evidence)
