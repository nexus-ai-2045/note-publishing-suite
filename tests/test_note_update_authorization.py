import hashlib
import json
import importlib.util
from pathlib import Path

import pytest
spec = importlib.util.spec_from_file_location('note_update_authorization', Path(__file__).resolve().parents[1] / 'scripts/note_update_authorization.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

@pytest.fixture
def setup_policy(tmp_path):
    evidence = tmp_path / 'adoption.md'
    evidence.write_text('本人が既存記事の更新操作を許可した記録', encoding='utf-8')
    policy = {'schema': 'nps-existing-update-policy/v1', 'enabled': True, 'account': 'writer',
              'approval_ref': 'adoption.md', 'approval_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps({'workspace_root': '.', 'publication_policy': {'existing_article_update': policy}}))
    obs = {'operation': 'update_existing', 'published_before': True, 'account': 'writer',
           'note_id': 'n123abc', 'public_url': 'https://note.com/writer/n/n123abc', 'action': '更新する',
           'new_publication': False, 'schedule_change': False, 'external_share': False,
           'approved_content_sha256': 'a'*64, 'editor_content_sha256': 'a'*64, 'saved_content_sha256': 'a'*64,
           'baseline_settings_sha256': 'b'*64, 'current_settings_sha256': 'b'*64,
           'edit_request_ref': 'current-user-turn', 'checks': dict.fromkeys((
               'requested_change_only', 'body_and_links_verified', 'layout_verified', 'saved_and_reloaded',
               'public_identity_verified', 'prepublish_qa_passed'), True)}
    return cfg, obs, evidence

def test_explicit_opt_in(setup_policy):
    cfg, obs, _ = setup_policy
    result = m.authorize_update(cfg, obs)
    assert result['automation_allowed'] and not result['manual_publish_required']
    assert result['authenticity_verified'] is False

@pytest.mark.parametrize('key,value', [('published_before', False), ('operation', 'new'),
    ('new_publication', True), ('schedule_change', True), ('external_share', True),
    ('account', 'other'), ('note_id', 'other'), ('public_url', 'https://note.com/other/n/n123abc'),
    ('action', '投稿する'), ('saved_content_sha256', 'c'*64), ('current_settings_sha256', 'c'*64),
    ('approved_content_sha256', ''), ('edit_request_ref', '')])
def test_invalid_or_changed_state_stops(setup_policy, key, value):
    cfg, obs, _ = setup_policy
    obs[key] = value
    assert m.authorize_update(cfg, obs)['automation_allowed'] is False

@pytest.mark.parametrize('key', ['requested_change_only', 'body_and_links_verified', 'layout_verified',
    'saved_and_reloaded', 'public_identity_verified', 'prepublish_qa_passed'])
def test_unverified_check_stops(setup_policy, key):
    cfg, obs, _ = setup_policy
    obs['checks'][key] = False
    assert not m.authorize_update(cfg, obs)['automation_allowed']

def test_default_and_revoked_policy_stop(setup_policy):
    cfg, obs, evidence = setup_policy
    assert not m.authorize_update(None, obs)['automation_allowed']
    evidence.write_text('変更された許可記録')
    assert not m.authorize_update(cfg, obs)['automation_allowed']
    cfg.write_text('{}')
    assert not m.authorize_update(cfg, obs)['automation_allowed']
