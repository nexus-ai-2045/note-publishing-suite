"""外部マーケティング正本への接続を省略・古い読戻しで通さない。"""
from pathlib import Path
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nps_script_loader import load_script

verify = load_script('note_editor_prepublish_verify')
gate = load_script('note_workflow_gate')


def reference_context(tmp_path):
    files = {}
    for axis in ('content', 'discovery', 'branding'):
        path = tmp_path / f'{axis}.md'
        path.write_text(f'Adopted {axis} guidance.', encoding='utf-8')
        files[axis] = str(path)
    policy = dict(schema='nps-tag-reference-policy/v1', required=True,
                  strategy_sources={axis: [path] for axis, path in files.items()})
    hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in files.values()}
    design = dict(strategy={axis: dict(reason=f'Apply {axis} to this article.', evidence_ref=path)
                            for axis, path in files.items()},
                  reference_readback=hashes.copy(),
                  search_intents=['論理的 人間関係', 'ASD コミュニケーション'])
    return policy, hashes, design


def test_current_marketing_references_and_search_intents_are_accepted(tmp_path):
    policy, hashes, design = reference_context(tmp_path)
    assert verify.validate_tag_reference_readback(design, policy, hashes) == []


@pytest.mark.parametrize('problem', ['missing_readback', 'stale', 'foreign', 'missing_search', 'duplicate_search'])
def test_missing_stale_or_unadopted_marketing_inputs_block(tmp_path, problem):
    policy, hashes, design = reference_context(tmp_path)
    if problem == 'missing_readback': design.pop('reference_readback')
    if problem == 'stale': design['reference_readback'][next(iter(hashes))] = '0' * 64
    if problem == 'foreign': design['strategy']['discovery']['evidence_ref'] = '/unadopted.md'
    if problem == 'missing_search': design.pop('search_intents')
    if problem == 'duplicate_search': design['search_intents'] = ['同じ', ' 同じ ']
    assert verify.validate_tag_reference_readback(design, policy, hashes)


def test_existing_users_without_policy_are_unchanged():
    assert verify.validate_tag_reference_readback({}, None, {}) == []


def test_settings_load_required_sources_for_every_article_and_detect_change(tmp_path):
    policy, hashes, _ = reference_context(tmp_path)
    voice = tmp_path / 'voice.md'; voice.write_text('Author voice.', encoding='utf-8')
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile='voice.md', article_profiles={}), tag_reference_policy=policy)), encoding='utf-8')
    before, _ = gate.read_workspace_settings(cfg, 'new-article')
    assert before['tag_reference_policy'] == policy
    assert hashes.items() <= before['reference_hashes'].items()
    changed = Path(policy['strategy_sources']['discovery'][0])
    changed.write_text('New discovery guidance.', encoding='utf-8')
    after, _ = gate.read_workspace_settings(cfg, 'new-article')
    assert before['reference_hashes'][str(changed)] != after['reference_hashes'][str(changed)]
    changed.unlink()
    with pytest.raises((OSError, ValueError)):
        gate.read_workspace_settings(cfg, 'new-article')


def test_malformed_required_policy_is_rejected(tmp_path):
    policy, _, _ = reference_context(tmp_path)
    policy['strategy_sources'].pop('branding')
    assert verify.validate_tag_reference_policy(policy)


def test_editor_snapshot_cannot_disable_adopted_reference_policy(tmp_path):
    policy, _, design = reference_context(tmp_path)
    (tmp_path / 'voice.md').write_text('Voice.', encoding='utf-8')
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps(dict(schema_version='nps-workspace-settings/v1', workspace_root='.',
        storage=dict(drafts='drafts', sources='sources', feedback='feedback'),
        style=dict(default_profile='voice.md', article_profiles={}), tag_reference_policy=policy)), encoding='utf-8')
    design.pop('reference_readback')
    data = dict(stage='settings', article_id='article', tag_design=design,
                tag_reference_policy=dict(schema='nps-tag-reference-policy/v1', required=False))
    result = verify.build_result(data, settings_path=cfg, article_id='article')
    assert any(x['code'] == 'tag_reference_readback_missing_or_stale' for x in result['issues'])
