from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from test_note_workflow_gate import approve, gate, packet  # noqa: F401


SLOTS = ['channel_one', 'channel_two', 'channel_three']


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure(packet, tmp_path, *, required=True):
    settings = tmp_path / 'workspace-settings.json'
    config = json.loads(settings.read_text())
    config['publication_drafts_policy'] = {
        'schema': 'nps-publication-drafts-policy/v1',
        'required': required,
        'required_slots': SLOTS,
    }
    settings.write_text(json.dumps(config))
    packet['ssot_readback'], _ = gate.read_workspace_settings(settings, 'article')
    return settings


def make_bundle(packet, tmp_path):
    article_sha = digest(Path(packet['draft']))
    items = []
    for slot in SLOTS:
        draft = tmp_path / (slot + '.md')
        draft.write_text('Prepared draft for ' + slot, encoding='utf-8')
        review = tmp_path / (slot + '.review.json')
        review.write_text(json.dumps({
            'schema': 'nps-publication-draft-review/v1',
            'article_id': 'article', 'article_draft_sha256': article_sha,
            'slot': slot, 'draft_sha256': digest(draft),
            'status': 'confirmed', 'actor': 'assistant',
            'reviewer_id': 'fixture-reviewer', 'reviewed_at': '2020-01-01T00:00:00+00:00',
            'evidence_ref': 'fixture://review', 'summary': 'Reviewed this exact draft.',
        }))
        items.append({'slot': slot, 'path': draft.name, 'sha256': digest(draft),
                      'review': {'path': review.name, 'sha256': digest(review)}})
    bundle = tmp_path / 'publication-drafts.json'
    bundle.write_text(json.dumps({'schema': 'nps-publication-drafts/v1',
        'article_id': 'article', 'article_draft_sha256': article_sha, 'items': items}))
    packet['publication_drafts_manifest'] = str(bundle)
    return bundle


def result(packet):
    return gate.check_packet(packet, 'publish', 'current')


def test_required_missing_bundle_blocks_before_publication(packet, tmp_path):
    configure(packet, tmp_path)
    checked = approve(packet, 'publish')
    assert checked['status'] == 'blocked'
    assert any('publication_drafts' in reason for reason in checked['reasons'])


@pytest.mark.parametrize('mode', ['immediate', 'scheduled'])
def test_three_confirmed_drafts_bind_publish_approval(packet, tmp_path, mode):
    configure(packet, tmp_path)
    make_bundle(packet, tmp_path)
    packet['settings'].update(publish_mode=mode,
        schedule_at='2030-01-01T12:00:00+00:00' if mode == 'scheduled' else None)
    checked = approve(packet, 'publish')
    assert checked['status'] == 'approved'
    assert checked['publication_drafts']['status'] == 'ok'
    assert checked['publication_drafts']['semantic_quality_verified'] is False
    assert checked['manual_publish_required'] is True
    assert checked['automation_allowed'] is False


@pytest.mark.parametrize('stage', ['edit', 'research', 'layout', 'settings'])
def test_drafts_need_not_exist_during_preparation(packet, tmp_path, stage):
    configure(packet, tmp_path)
    assert approve(packet, stage)['status'] == 'approved'


def test_absent_and_disabled_policy_keep_legacy(packet, tmp_path):
    assert approve(packet, 'publish')['status'] == 'approved'
    configure(packet, tmp_path, required=False)
    packet['receipts'] = []  # A changed external settings file invalidates prior receipts.
    assert approve(packet, 'publish')['status'] == 'approved'
    assert result(packet)['publication_drafts']['status'] == 'not_required'


@pytest.mark.parametrize('change', ['missing_slot', 'duplicate', 'unknown_slot', 'article',
    'article_version', 'missing_file', 'empty_file', 'bad_draft_hash', 'missing_review',
    'bad_review_hash', 'unconfirmed', 'review_version', 'review_article', 'review_slot',
    'review_actor', 'review_future', 'unknown_schema', 'malformed_json', 'duplicate_json_key'])
def test_invalid_or_stale_artifacts_fail_closed(packet, tmp_path, change):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    item = obj['items'][0]
    review_path = tmp_path / item['review']['path']
    review = json.loads(review_path.read_text())
    if change == 'missing_slot': obj['items'].pop()
    elif change == 'duplicate': obj['items'][1] = copy.deepcopy(item)
    elif change == 'unknown_slot': item['slot'] = 'other'
    elif change == 'article': obj['article_id'] = 'other'
    elif change == 'article_version': obj['article_draft_sha256'] = '0' * 64
    elif change == 'missing_file': (tmp_path / item['path']).unlink()
    elif change == 'empty_file': (tmp_path / item['path']).write_text('  ')
    elif change == 'bad_draft_hash': item['sha256'] = '0' * 64
    elif change == 'missing_review': review_path.unlink()
    elif change == 'bad_review_hash': item['review']['sha256'] = '0' * 64
    elif change == 'unconfirmed': review['status'] = 'pending'
    elif change == 'review_version': review['draft_sha256'] = '0' * 64
    elif change == 'review_article': review['article_draft_sha256'] = '0' * 64
    elif change == 'review_slot': review['slot'] = 'other'
    elif change == 'review_actor': review['actor'] = 'unknown'
    elif change == 'review_future': review['reviewed_at'] = '2999-01-01T00:00:00+00:00'
    elif change == 'unknown_schema': obj['schema'] = 'unknown'
    if change.startswith('review_') or change == 'unconfirmed':
        review_path.write_text(json.dumps(review))
        item['review']['sha256'] = digest(review_path)
    manifest.write_text(json.dumps(obj))
    if change == 'malformed_json': manifest.write_text('{invalid')
    elif change == 'duplicate_json_key':
        manifest.write_text('{"schema":"nps-publication-drafts/v1","schema":"other"}')
    checked = approve(packet, 'publish')
    assert checked['status'] == 'blocked'
    assert any('publication_drafts' in reason for reason in checked['reasons'])


@pytest.mark.parametrize('value', [None, {}, {'schema': 'unknown', 'required': True},
    {'schema': 'nps-publication-drafts-policy/v1', 'required': 'true', 'required_slots': SLOTS},
    {'schema': 'nps-publication-drafts-policy/v1', 'required': True, 'required_slots': []},
    {'schema': 'nps-publication-drafts-policy/v1', 'required': True, 'required_slots': ['a', 'a']},
    {'schema': 'nps-publication-drafts-policy/v1', 'required': True, 'required_slots': SLOTS, 'waive': True}])
def test_unknown_or_invalid_policy_rejected(packet, tmp_path, value):
    settings = tmp_path / 'workspace-settings.json'
    config = json.loads(settings.read_text())
    config['publication_drafts_policy'] = value
    settings.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        gate.read_workspace_settings(settings, 'article')


@pytest.mark.parametrize('kind', ['manifest', 'draft', 'review'])
def test_external_storage_paths_rejected(packet, tmp_path, kind):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    foreign = tmp_path.parent / (tmp_path.name + '-foreign')
    foreign.mkdir()
    obj = json.loads(manifest.read_text())
    if kind == 'manifest':
        target = foreign / 'manifest.json'
        target.write_bytes(manifest.read_bytes())
        packet['publication_drafts_manifest'] = str(target)
    elif kind == 'draft':
        obj['items'][0]['path'] = str(foreign / 'draft.md')
        (foreign / 'draft.md').write_text('foreign')
    else:
        obj['items'][0]['review']['path'] = str(foreign / 'review.json')
        (foreign / 'review.json').write_text('{}')
    manifest.write_text(json.dumps(obj))
    assert approve(packet, 'publish')['status'] == 'blocked'


def test_same_file_cannot_fill_multiple_slots(packet, tmp_path):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    obj['items'][1]['path'] = obj['items'][0]['path']
    obj['items'][1]['sha256'] = obj['items'][0]['sha256']
    manifest.write_text(json.dumps(obj))
    assert approve(packet, 'publish')['status'] == 'blocked'


def test_valid_new_bundle_invalidates_old_publish_receipt(packet, tmp_path):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    assert approve(packet, 'publish')['status'] == 'approved'
    prior_subject = result(packet)['subject_hashes']['publish']
    obj = json.loads(manifest.read_text())
    item = obj['items'][0]
    path = tmp_path / item['path']
    path.write_text('New reviewed copy')
    item['sha256'] = digest(path)
    review_path = tmp_path / item['review']['path']
    review = json.loads(review_path.read_text())
    review['draft_sha256'] = item['sha256']
    review_path.write_text(json.dumps(review))
    item['review']['sha256'] = digest(review_path)
    manifest.write_text(json.dumps(obj))
    checked = result(packet)
    assert checked['subject_hashes']['publish'] != prior_subject
    assert checked['status'] == 'blocked'


def test_assistant_draft_confirmation_does_not_authorize_publication(packet, tmp_path):
    configure(packet, tmp_path)
    make_bundle(packet, tmp_path)
    checked = result(packet)
    assert checked['publication_drafts']['status'] == 'ok'
    assert checked['publication_drafts']['human_publication_authorized'] is False
    assert checked['status'] == 'blocked'
    assert any('publish' in reason for reason in checked['reasons'])


def test_packet_cannot_waive_external_policy(packet, tmp_path):
    configure(packet, tmp_path)
    packet['publication_drafts_policy'] = {'required': False}
    assert approve(packet, 'publish')['status'] == 'blocked'


def test_self_report_without_review_file_does_not_replace_confirmation(packet, tmp_path):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    obj['items'][0]['review'] = {'status': 'confirmed', 'semantic_check': True}
    manifest.write_text(json.dumps(obj))
    assert approve(packet, 'publish')['status'] == 'blocked'


def test_symlink_outside_adopted_storage_is_not_read(packet, tmp_path, monkeypatch):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    foreign = tmp_path.parent / (tmp_path.name + '-private.md')
    foreign.write_text('Outside adopted storage')
    link = tmp_path / obj['items'][0]['path']
    link.unlink()
    link.symlink_to(foreign)
    original = Path.read_bytes

    def read_bytes(path):
        assert path != foreign, 'outside file bytes must not be read'
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    assert approve(packet, 'publish')['status'] == 'blocked'


def test_hardlink_cannot_fill_multiple_slots(packet, tmp_path):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    first = tmp_path / obj['items'][0]['path']
    second = tmp_path / obj['items'][1]['path']
    second.unlink()
    second.hardlink_to(first)
    obj['items'][1]['sha256'] = digest(second)
    manifest.write_text(json.dumps(obj))
    assert approve(packet, 'publish')['status'] == 'blocked'


@pytest.mark.parametrize('change', ['bytes', 'symlink'])
def test_change_during_validation_is_rejected(packet, tmp_path, monkeypatch, change):
    configure(packet, tmp_path)
    manifest = make_bundle(packet, tmp_path)
    obj = json.loads(manifest.read_text())
    target = tmp_path / obj['items'][0]['path']
    alternate = tmp_path / 'alternate.md'
    alternate.write_bytes(target.read_bytes())
    if change == 'symlink':
        initial = tmp_path / 'initial.md'
        target.rename(initial)
        target.symlink_to(initial)
    trigger = tmp_path / obj['items'][-1]['review']['path']
    original = Path.read_bytes
    changed = False

    def read_bytes(path):
        nonlocal changed
        raw = original(path)
        if path == trigger and not changed:
            changed = True
            if change == 'bytes': target.write_text('Changed during read')
            else:
                target.unlink()
                target.symlink_to(alternate)
        return raw

    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    assert approve(packet, 'publish')['status'] == 'blocked'
    assert changed


def test_checker_is_local_and_does_not_update_workspace_files(packet, tmp_path, monkeypatch):
    import socket

    configure(packet, tmp_path)
    make_bundle(packet, tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    monkeypatch.setattr(socket, 'create_connection', lambda *args, **kwargs: pytest.fail('network access'))
    assert approve(packet, 'publish')['status'] == 'approved'
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
