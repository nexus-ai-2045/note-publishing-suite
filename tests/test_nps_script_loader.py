"""公開cacheを変えず、配布元へ束縛した依存が遅延実行にも残る回帰。"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def bootstrap(root):
    spec = importlib.util.spec_from_file_location('test_loader_bootstrap', root / 'nps_script_loader.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_script


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'scripts'
    shutil.copytree(SCRIPTS, root)
    return root


@pytest.mark.parametrize('first', ['pre_publish_check', 'note_workflow_gate'])
def test_same_source_closure_and_public_cache_unchanged(source, monkeypatch, first):
    names = ['pre_publish_check', 'note_workflow_gate', 'note_feedback', 'note_authorship_gate',
             'note_research_quality', 'note_footer_selection', 'image_reference_gate',
             'note_editor_prepublish_verify', 'note_editor_session_check', 'nps_script_loader']
    fake = {}
    for name in names:
        fake[name] = ModuleType(name)
        fake[name].__file__ = str(source / (name + '.py'))
        monkeypatch.setitem(sys.modules, name, fake[name])
    original_path = sys.path[:]
    load = bootstrap(source)
    load(first)
    for name in names[:-1]:
        module = load(name)
        assert Path(module.__file__) == source / (name + '.py')
    workflow = load('note_workflow_gate')
    feedback = load('note_feedback')
    assert workflow.check_input_capture is feedback.check_input_capture
    assert load('pre_publish_check').read_workspace_settings is workflow.read_workspace_settings
    assert load('note_research_quality').valid_http_url is load('note_footer_selection')._url
    assert load('note_editor_prepublish_verify').parse_json is load('note_footer_selection').parse_json
    with pytest.raises(FileNotFoundError):
        feedback.read_history_sources(source / 'absent.json', {})
    result = load('note_authorship_gate').check_history_learning_from_settings(source / 'absent.md', None, None)
    assert result['status'] == 'blocked'
    with pytest.raises(ValueError):
        workflow.read_workspace_settings(None, 'article')
    assert sys.path == original_path
    assert all(sys.modules[name] is fake[name] for name in names)
    assert bootstrap(source) is load


def test_state_class_identity_root_separation_and_parallel_bootstrap(source, tmp_path):
    (source / 'identity_probe.py').write_text('state = []\nclass Marker: pass\n')
    other = tmp_path / 'other'
    shutil.copytree(source, other)
    with ThreadPoolExecutor(max_workers=2) as pool:
        loaders = list(pool.map(bootstrap, [source, source]))
        modules = list(pool.map(lambda load: load('identity_probe'), loaders))
    assert loaders[0] is loaders[1]
    assert modules[0] is modules[1]
    modules[0].state.append('kept')
    assert loaders[0]('identity_probe').state == ['kept']
    assert loaders[0]('identity_probe').Marker is modules[0].Marker
    foreign = bootstrap(other)('identity_probe')
    assert foreign.Marker is not modules[0].Marker
    assert foreign.state == []


def test_failure_cleanup_cycle_retry_missing_and_invalid_names(source, monkeypatch):
    load = bootstrap(source)
    probe = source / 'failure_probe.py'
    probe.write_text('raise RuntimeError("initialization failed")\n')
    key = '_nps_script_' + hashlib.sha256(str(probe).encode()).hexdigest()
    with pytest.raises(RuntimeError):
        load('failure_probe')
    assert key not in sys.modules
    probe.write_text('value = "retry succeeded with a different source size"\n')
    assert load('failure_probe').value.startswith('retry succeeded')
    probe = source / 'cycle_probe.py'
    probe.write_text((source / 'note_feedback.py').read_text().split('SCHEMA =')[0] + '\n_load_sibling_module("cycle_probe")\n')
    key = '_nps_script_' + hashlib.sha256(str(probe).encode()).hexdigest()
    with pytest.raises(ImportError, match='circular initialization'):
        load('cycle_probe')
    assert key not in sys.modules
    monkeypatch.setitem(sys.modules, 'missing_probe', ModuleType('missing_probe'))
    with pytest.raises(ModuleNotFoundError) as exc:
        load('missing_probe')
    assert exc.value.name == 'missing_probe'
    for name in ['../note_feedback', 'note_feedback.py', '/tmp/probe', '']:
        with pytest.raises(ImportError):
            load(name)


def test_foreign_private_cache_is_not_overwritten(source, monkeypatch):
    load = bootstrap(source)
    path = source / 'note_feedback.py'
    key = '_nps_script_' + hashlib.sha256(str(path).encode()).hexdigest()
    fake = ModuleType(key)
    fake.__file__ = str(path)
    monkeypatch.setitem(sys.modules, key, fake)
    with pytest.raises(ImportError, match='cache source mismatch'):
        load('note_feedback')
    assert sys.modules[key] is fake


def test_actual_postpublish_entry_binds_all_dependencies(source, monkeypatch):
    fake = {}
    for name in ("note_feedback", "pre_publish_check", "sync_note_public_snapshot"):
        fake[name] = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, fake[name])
    load = bootstrap(source)
    review = load("note_postpublish_review")
    assert review.record_feedback is load("note_feedback").record_feedback
    assert review.collect_issues is load("pre_publish_check").collect_published_issues
    assert review.ledger_file_lock is load("sync_note_public_snapshot").ledger_file_lock
    assert all(sys.modules[name] is module for name, module in fake.items())


def test_missing_image_dependency_does_not_use_ambient_package(source, monkeypatch):
    (source / "image_reference_gate.py").unlink()
    foreign = ModuleType("scripts.image_reference_gate")
    foreign.check_settings = lambda *a, **k: pytest.fail("foreign image checker executed")
    monkeypatch.setitem(sys.modules, "scripts.image_reference_gate", foreign)
    draft = source / "draft.md"
    draft.write_text("---\narticle_lane: exploratory_draft\n---\n# Draft\nBody\n")
    check = bootstrap(source)("pre_publish_check")
    with pytest.raises(ModuleNotFoundError) as exc:
        check.check_draft(draft)
    assert exc.value.name == "image_reference_gate"


ENTRYPOINTS = ['post_publish', 'note_article_version', 'verify_published_update', 'note_interview_packet',
               'note_editor_apply', 'note_editor_pdca_cycle_check', 'fetch_note_official_specs',
               'note_workflow_gate', 'note_editor_prepublish_verify', 'note_authorship_gate']


@pytest.mark.parametrize('entry', ENTRYPOINTS)
def test_entrypoint_ignores_decoy_modules_ahead_on_sys_path(source, tmp_path, monkeypatch, entry):
    decoys = tmp_path / 'decoys'
    decoys.mkdir()
    siblings = [path.stem for path in source.glob('*.py') if not path.name.startswith('test_')]
    for name in siblings:
        (decoys / (name + '.py')).write_text('raise RuntimeError("decoy module imported")\n')
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(decoys))
    load_script = bootstrap(source)
    module = load_script(entry)
    assert Path(module.__file__).resolve() == (source / (entry + '.py')).resolve()
    assert not any(name in sys.modules and Path(getattr(sys.modules[name], '__file__', '') or '').parent == decoys
                   for name in siblings)
