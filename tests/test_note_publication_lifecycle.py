from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lifecycle', ROOT / 'scripts/note_publication_lifecycle.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def put(root, name, value):
    data = value if isinstance(value, bytes) else json.dumps(value).encode()
    (root / name).write_bytes(data)
    return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}


def fixture(root):
    body = put(root, 'body.md', b'# Title\n\nReader text')
    reader = put(root, 'reader.txt', b'Title Reader text')
    reader_hash = hashlib.sha256(b'TitleReadertext').hexdigest()
    body['reader_text_sha256'] = reader_hash
    packet = {'status': 'collected', 'lifecycle': {'schema_version': 'note-publication-lifecycle/v1',
               'article_id': 'a8', 'body_sha256': body['sha256'], 'actions': []}}
    profile = {'body': body, 'actions': []}
    settings = {'publication_lifecycle_policy': {'required': True, 'profiles': {'a8': profile}}}
    draft = put(root, 'announcement.md', b'Please read the article')
    ledger = put(root, 'ledger.json', {'article_id': 'a8', 'body_sha256': body['sha256']})
    commit = 'a' * 40
    delivery = put(root, 'delivery.json', {'article_id': 'a8', 'body_sha256': body['sha256'],
                                          'commit': commit, 'remote_commit': commit})
    results = {
        'note_save': {'saved_body_sha256': reader_hash, 'readback_complete': True, 'artifact': reader},
        'note_publication': {'public_url': 'https://note.com/u/n/n123', 'public_body_sha256': reader_hash,
                             'published': True, 'readback_complete': True, 'artifact': reader},
        'postpublish_review': {'postpublication_complete': True,
                              'published_entry': {'note_id': 'n123', 'article_id': 'a8', 'body_sha256': body['sha256']}},
        'announcement_draft': {'draft_sha256': draft['sha256'], 'card_url': 'https://note.com/u/n/n123',
                               'card_title': 'Title', 'card_description': 'Description', 'reviewed': True,
                               'artifact': draft},
        'announcement_send': {'message_id': '1', 'url': 'https://example.test/messages/1',
                              'destination_id': 'channel-1', 'sent': True, 'readback_complete': True,
                              'body_sha256': body['sha256'], 'payload_sha256': draft['sha256']},
        'ledger_update': {'entry_article_id': 'a8', 'entry_body_sha256': body['sha256'],
                          'readback_complete': True, 'artifact': ledger},
        'git_delivery': {'commit': commit, 'remote_commit': commit, 'executed': True,
                         'repository': 'example/articles', 'branch': 'main',
                         'exit_code': 0, 'clean': True, 'artifact': delivery,
                         'remote_artifact': put(root, 'remote-delivery.json', (root / delivery['path']).read_bytes())},
    }
    results = {kind: results[kind] for kind in ['note_save', 'announcement_draft', 'note_publication',
               'announcement_send', 'postpublish_review', 'ledger_update', 'git_delivery']}
    prev = []
    for kind, result in results.items():
        target = {'url': 'https://note.com/u/n/n123', 'destination_id': 'channel-1',
                  'repository': 'example/articles', 'branch': 'main',
                  'message_url_template': 'https://example.test/messages/{message_id}'}
        profile['actions'].append({'id': kind, 'kind': kind, 'stage': kind,
                                   'depends_on': prev, 'target': target, 'authorized': True})
        binding = {'action_id': kind, 'kind': kind, 'article_id': 'a8',
                   'body_sha256': body['sha256'], 'target': target}
        original = {**binding, 'schema_version': 'note-lifecycle-observation/v1',
                    'body_text': 'Title Reader text', 'result': result}
        source = {**binding, 'result': result, 'result_paths': {k: '/result/' + k for k in result},
                  'observation_body_field': 'body_text',
                  'original_observation': put(root, kind + '-original.json', original)}
        if kind == 'announcement_send':
            source['approval_ref'] = put(root, 'approval.json', {**binding, 'actor': 'human',
                'decision': 'approved', 'payload_sha256': draft['sha256']})
        evidence = {**binding, 'schema_version': 'note-lifecycle-evidence/v1',
                    'source': put(root, kind + '-source.json', source)}
        packet['lifecycle']['actions'].append({'id': kind, 'status': 'verified',
                                               'evidence': put(root, kind + '-evidence.json', evidence)})
        prev = [kind]
    return packet, settings


def check(root, packet, settings, stage='closeout'):
    return mod.check_lifecycle(packet, settings, root, article_id='a8', stage=stage)


def mutate_source(root, packet, aid, mutate):
    action = next(a for a in packet['lifecycle']['actions'] if a['id'] == aid)
    ev = json.loads((root / action['evidence']['path']).read_text())
    source = json.loads((root / ev['source']['path']).read_text())
    mutate(source)
    ev['source'] = put(root, ev['source']['path'], source)
    action['evidence'] = put(root, action['evidence']['path'], ev)


def test_complete_fixture_and_original_reader_version(tmp_path):
    packet, settings = fixture(tmp_path)
    assert check(tmp_path, packet, settings)['ok']
    packet['status'] = 'closed'
    assert check(tmp_path, packet, settings)['remaining'] == []


def test_arbitrary_success_field_cannot_replace_failed_send(tmp_path):
    packet, settings = fixture(tmp_path)
    def change(source):
        original = json.loads((tmp_path / source['original_observation']['path']).read_text())
        original['result']['sent'] = False
        source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
        source['result_paths']['sent'] = '/result/readback_complete'
    mutate_source(tmp_path, packet, 'announcement_send', change)
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('differs from original observation' in s or 'field mapping cannot be changed' in s for s in result['stop_causes'])


def test_new_draft_cannot_reuse_old_reader_projection(tmp_path):
    packet, settings = fixture(tmp_path)
    body = put(tmp_path, 'body.md', b'# Completely changed\n\nA different article')
    profile = settings['publication_lifecycle_policy']['profiles']['a8']
    profile['body']['sha256'] = body['sha256']
    packet['lifecycle']['body_sha256'] = body['sha256']
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert 'reader hash does not derive from current draft' in result['stop_causes']


def test_other_article_review_cannot_complete_current_article(tmp_path):
    packet, settings = fixture(tmp_path)
    def change(source):
        source['result']['published_entry']['note_id'] = 'other-note'
        original = json.loads((tmp_path / source['original_observation']['path']).read_text())
        original['result'] = source['result']
        source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
    mutate_source(tmp_path, packet, 'postpublish_review', change)
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('another article/version' in s for s in result['stop_causes'])


def test_article_plan_cannot_remove_a_required_kind(tmp_path):
    packet, settings = fixture(tmp_path)
    policy = settings['publication_lifecycle_policy']
    policy['required_kinds'] = ['ledger_update']
    policy['profiles']['a8']['actions'] = [a for a in policy['profiles']['a8']['actions'] if a['kind'] != 'ledger_update']
    packet['lifecycle']['actions'] = [a for a in packet['lifecycle']['actions'] if a['id'] != 'ledger_update']
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert 'required action kind removed from article plan' in result['stop_causes']


def test_announcement_selection_can_omit_unneeded_media_with_reason(tmp_path):
    packet, settings = fixture(tmp_path)
    policy = settings['publication_lifecycle_policy']
    policy['announcement_selection_required'] = True
    profile = policy['profiles']['a8']
    profile['actions'] = profile['actions'][:1]
    packet['lifecycle']['actions'] = packet['lifecycle']['actions'][:1]
    profile['announcement_selection'] = {'state': 'not_required', 'reason': 'This article needs no announcement'}
    assert check(tmp_path, packet, settings)['ok']
    profile['announcement_selection']['reason'] = ''
    assert not check(tmp_path, packet, settings)['ok']


def test_selected_announcement_cannot_drop_send_action(tmp_path):
    packet, settings = fixture(tmp_path)
    policy = settings['publication_lifecycle_policy']
    policy['announcement_selection_required'] = True
    policy['profiles']['a8']['announcement_selection'] = {'state': 'selected', 'slots': ['one-medium']}
    for action in policy['profiles']['a8']['actions']:
        if action['kind'] == 'announcement_draft':
            action['slot'] = 'one-medium'
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert 'unselected announcement action' in result['stop_causes']


def test_cover_bytes_participate_in_every_release_binding(tmp_path):
    packet, settings = fixture(tmp_path)
    policy = settings['publication_lifecycle_policy']
    policy['asset_selection_required'] = True
    profile = policy['profiles']['a8']
    cover = put(tmp_path, 'cover.bin', b'cover bytes')
    profile['artifacts'] = [cover]
    release = hashlib.sha256(json.dumps({'body_sha256': profile['body']['sha256'],
        'artifacts': {'cover.bin': cover['sha256']}}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    packet['lifecycle']['release_sha256'] = release
    for action in packet['lifecycle']['actions']:
        evidence = json.loads((tmp_path / action['evidence']['path']).read_text())
        source = json.loads((tmp_path / evidence['source']['path']).read_text())
        original = json.loads((tmp_path / source['original_observation']['path']).read_text())
        original['release_sha256'] = source['release_sha256'] = evidence['release_sha256'] = release
        source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
        if 'approval_ref' in source:
            approval = json.loads((tmp_path / source['approval_ref']['path']).read_text())
            approval['release_sha256'] = release
            source['approval_ref'] = put(tmp_path, source['approval_ref']['path'], approval)
        evidence['source'] = put(tmp_path, evidence['source']['path'], source)
        action['evidence'] = put(tmp_path, action['evidence']['path'], evidence)
    assert check(tmp_path, packet, settings)['ok']
    (tmp_path / 'cover.bin').write_bytes(b'different cover')
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('artifact hash mismatch' in s for s in result['stop_causes'])


def test_cannot_replace_failed_original_ledger_artifact_with_good_source(tmp_path):
    packet, settings = fixture(tmp_path)
    def change(source):
        original = json.loads((tmp_path / source['original_observation']['path']).read_text())
        original['result']['artifact'] = put(tmp_path, 'other-entry.json', {'article_id': 'OTHER', 'body_sha256': '0' * 64})
        source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
    mutate_source(tmp_path, packet, 'ledger_update', change)
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('source result differs' in s for s in result['stop_causes'])


def test_deleting_dependencies_does_not_allow_publish_before_save_or_drafts(tmp_path):
    packet, settings = fixture(tmp_path)
    for spec in settings['publication_lifecycle_policy']['profiles']['a8']['actions']:
        spec['depends_on'] = []
    for action in packet['lifecycle']['actions']:
        action['status'] = 'pending'
    result = check(tmp_path, packet, settings, 'note_publication')
    assert not result['ok']
    assert {'note_save', 'announcement_draft'}.issubset(set(result['required_now']))


def test_valueless_html_attribute_does_not_crash_parser():
    assert mod.prose_sha256('<p class>Valid text</p>', html=True) == mod.prose_sha256('Valid text')


def test_excessive_html_nesting_is_rejected():
    with pytest.raises(ValueError, match='nesting'):
        mod.prose_sha256('<div>' * 257 + 'text' + '</div>' * 257, html=True)


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='FIFO is not available')
def test_selected_packet_input_fifo_is_rejected_without_wait(tmp_path):
    path = tmp_path / 'packet.json'
    os.mkfifo(path)
    with pytest.raises(ValueError, match='regular file'):
        mod.load_input_json(path)


@pytest.mark.parametrize('aid,field,value', [
    ('note_save', 'readback_complete', False),
    ('note_publication', 'public_url', 'https://wrong.test'),
    ('note_publication', 'published', False),
    ('postpublish_review', 'postpublication_complete', False),
    ('announcement_draft', 'card_title', ''),
    ('announcement_draft', 'card_description', ''),
    ('announcement_send', 'destination_id', 'wrong-channel'),
    ('announcement_send', 'sent', False),
    ('announcement_send', 'url', 'https://note.com/u/n/n123'),
    ('ledger_update', 'entry_body_sha256', '0' * 64),
    ('git_delivery', 'executed', False),
    ('git_delivery', 'remote_commit', 'b' * 40),
])
@pytest.mark.parametrize('change_original', [False, True])
def test_success_claim_does_not_override_original_or_requirements(tmp_path, aid, field, value, change_original):
    packet, settings = fixture(tmp_path)
    def change(source):
        source['result'][field] = value
        if change_original:
            original = json.loads((tmp_path / source['original_observation']['path']).read_text())
            original['result'][field] = value
            source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
    mutate_source(tmp_path, packet, aid, change)
    assert not check(tmp_path, packet, settings)['ok']


def test_next_stage_requires_only_prerequisites_and_closeout_all(tmp_path):
    packet, settings = fixture(tmp_path)
    for action in packet['lifecycle']['actions'][2:]:
        action['status'] = 'pending'
        action.pop('evidence')
    result = check(tmp_path, packet, settings, 'note_publication')
    assert result['ok'] and result['next'] == 'note_publication'
    assert not check(tmp_path, packet, settings)['ok']
    packet['status'] = 'accepted'
    assert not check(tmp_path, packet, settings, 'note_publication')['ok']


@pytest.mark.parametrize('status', ['pending', 'unknown', 'prepared', 'sent', 'awaiting_human', 'blocked', 'not_applicable'])
def test_every_nonverified_state_blocks_closeout(tmp_path, status):
    packet, settings = fixture(tmp_path)
    packet['lifecycle']['actions'][-1]['status'] = status
    assert not check(tmp_path, packet, settings)['ok']


@pytest.mark.parametrize('defect', ['missing', 'stale', 'cycle', 'removed', 'unknown_kind', 'duplicate', 'invalid_type'])
def test_contract_mutations_fail_closed(tmp_path, defect):
    packet, settings = fixture(tmp_path)
    actions = settings['publication_lifecycle_policy']['profiles']['a8']['actions']
    if defect == 'missing': packet.pop('lifecycle')
    if defect == 'stale': packet['lifecycle']['body_sha256'] = '0' * 64
    if defect == 'cycle': actions[0]['depends_on'] = [actions[-1]['id']]
    if defect == 'removed': packet['lifecycle']['actions'].pop()
    if defect == 'unknown_kind': actions[0]['kind'] = 'click'
    if defect == 'duplicate': packet['lifecycle']['actions'].append(copy.deepcopy(packet['lifecycle']['actions'][0]))
    if defect == 'invalid_type': actions[0]['depends_on'] = {}
    assert not check(tmp_path, packet, settings)['ok']


@pytest.mark.parametrize('defect', ['original_missing', 'original_hash', 'approval_missing', 'approval_wrong', 'body_wrong'])
def test_original_observation_and_human_approval_are_required(tmp_path, defect):
    packet, settings = fixture(tmp_path)
    if defect == 'original_missing':
        mutate_source(tmp_path, packet, 'announcement_send', lambda s: s.pop('original_observation'))
    if defect == 'original_hash':
        (tmp_path / 'announcement_send-original.json').write_text('{}')
    if defect == 'approval_missing':
        mutate_source(tmp_path, packet, 'announcement_send', lambda s: s.pop('approval_ref'))
    if defect == 'approval_wrong':
        approval = json.loads((tmp_path / 'approval.json').read_text())
        approval['actor'] = 'agent'
        ref = put(tmp_path, 'approval.json', approval)
        mutate_source(tmp_path, packet, 'announcement_send', lambda s: s.__setitem__('approval_ref', ref))
    if defect == 'body_wrong':
        original = json.loads((tmp_path / 'note_save-original.json').read_text())
        original['body_text'] = 'Old version'
        ref = put(tmp_path, 'note_save-original.json', original)
        mutate_source(tmp_path, packet, 'note_save', lambda s: s.__setitem__('original_observation', ref))
    assert not check(tmp_path, packet, settings)['ok']


def test_policy_does_not_authorize_unapproved_send(tmp_path):
    packet, settings = fixture(tmp_path)
    next(a for a in settings['publication_lifecycle_policy']['profiles']['a8']['actions']
         if a['kind'] == 'announcement_send')['authorized'] = False
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert result['remaining'][0]['status'] == 'awaiting_human'


@pytest.mark.parametrize('defect', ['symlink', 'fifo', 'outside', 'oversize', 'duplicate_json', 'reuse'])
def test_unsafe_evidence_is_rejected_without_hanging(tmp_path, defect):
    packet, settings = fixture(tmp_path)
    action = packet['lifecycle']['actions'][0]
    if defect == 'symlink':
        (tmp_path / 'link').symlink_to(tmp_path / 'note_save-evidence.json')
        action['evidence']['path'] = 'link'
    if defect == 'fifo':
        os.mkfifo(tmp_path / 'pipe')
        action['evidence']['path'] = 'pipe'
    if defect == 'outside': action['evidence']['path'] = '../outside'
    if defect == 'oversize': action['evidence'] = put(tmp_path, 'large', b'x' * (mod.MAX_BYTES + 1))
    if defect == 'duplicate_json': action['evidence'] = put(tmp_path, 'duplicate', b'{"x":1,"x":2}')
    if defect == 'reuse': packet['lifecycle']['actions'][1]['evidence'] = action['evidence']
    assert not check(tmp_path, packet, settings)['ok']


def test_cli_requires_lifecycle_when_policy_requires_it(tmp_path):
    packet, settings = fixture(tmp_path)
    packet.pop('lifecycle')
    packet.update(schema_version='note-work-packet/v1', task_id='a8', meta_label='note', fde_label='note',
                  owner='owner', chain_from='parent', return_to='parent', objective='finish', input=['body'],
                  expected_output=['receipt'], done_when=['verified'], stop_when=['missing'], evidence=['receipt'],
                  residual=[], next_action='verify')
    put(tmp_path, 'packet.json', packet)
    put(tmp_path, 'settings.json', settings)
    process = subprocess.run([sys.executable, str(ROOT / 'scripts/note_work_packet_check.py'),
        str(tmp_path / 'packet.json'), '--settings', str(tmp_path / 'settings.json'), '--article-id', 'a8', '--json'],
        capture_output=True, text=True)
    assert process.returncode == 1
    assert 'lifecycle is required' in json.loads(process.stdout)['stop_causes']


def test_send_must_match_verified_draft_and_approval(tmp_path):
    packet, settings = fixture(tmp_path)
    def change(source):
        source['result']['payload_sha256'] = 'b' * 64
        original = json.loads((tmp_path / source['original_observation']['path']).read_text())
        original['result']['payload_sha256'] = 'b' * 64
        source['original_observation'] = put(tmp_path, source['original_observation']['path'], original)
        approval = json.loads((tmp_path / source['approval_ref']['path']).read_text())
        approval['payload_sha256'] = 'b' * 64
        source['approval_ref'] = put(tmp_path, source['approval_ref']['path'], approval)
    mutate_source(tmp_path, packet, 'announcement_send', change)
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('sent payload differs' in issue for issue in result['stop_causes'])


def test_other_medium_draft_cannot_authorize_sent_payload(tmp_path):
    packet, settings = fixture(tmp_path)
    profile = settings['publication_lifecycle_policy']['profiles']['a8']
    draft_spec = next(s for s in profile['actions'] if s['kind'] == 'announcement_draft')
    send_spec = next(s for s in profile['actions'] if s['kind'] == 'announcement_send')
    draft_spec['slot'] = 'a'
    send_spec['slot'] = 'b'
    other = copy.deepcopy(draft_spec)
    other.update(id='other-draft', slot='b')
    other['target'] = copy.deepcopy(send_spec['target'])
    body = profile['body']['sha256']
    artifact = put(tmp_path, 'other-payload.txt', b'A different reviewed payload')
    binding = {'action_id': other['id'], 'kind': 'announcement_draft', 'article_id': 'a8',
               'body_sha256': body, 'target': other['target']}
    original = {**binding, 'schema_version': 'note-lifecycle-observation/v1', 'result': {
        'draft_sha256': artifact['sha256'], 'card_url': 'https://note.com/u/n/n123',
        'card_title': 'Title', 'card_description': 'Description', 'reviewed': True, 'artifact': artifact}}
    source = {**binding, 'result': original['result'],
              'result_paths': {key: '/result/' + key for key in original['result']},
              'original_observation': put(tmp_path, 'other-original.json', original)}
    evidence = {**binding, 'schema_version': 'note-lifecycle-evidence/v1',
                'source': put(tmp_path, 'other-source.json', source)}
    profile['actions'].insert(2, other)
    packet['lifecycle']['actions'].insert(2, {'id': other['id'], 'status': 'verified',
        'evidence': put(tmp_path, 'other-evidence.json', evidence)})
    result = check(tmp_path, packet, settings)
    assert not result['ok']
    assert any('sent payload differs' in issue for issue in result['stop_causes'])
