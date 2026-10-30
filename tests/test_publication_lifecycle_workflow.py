from __future__ import annotations

import hashlib
import json

from test_note_workflow_gate import approve, gate, packet  # noqa: F401
from test_note_work_packet_check import valid_packet


def put(root, name, value):
    data = value if isinstance(value, bytes) else json.dumps(value).encode()
    (root / name).write_bytes(data)
    return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}


def enable(root, workflow):
    body_hash = hashlib.sha256(b'draft').hexdigest()
    target = {'url': 'https://note.com/example/n/n123'}
    body = {'path': 'draft.md', 'sha256': body_hash, 'reader_text_sha256': body_hash}
    actions = [
        {'id': 'saved', 'kind': 'note_save', 'stage': 'save', 'target': target, 'depends_on': []},
        {'id': 'published', 'kind': 'note_publication', 'stage': 'publish', 'target': target,
         'depends_on': ['saved'], 'authorized': True},
    ]
    policy = {'required': True, 'required_kinds': ['note_save', 'note_publication'],
              'announcement_selection_required': True,
              'profiles': {'article': {'body': body, 'actions': actions,
                                      'announcement_selection': {'state': 'not_required', 'reason': 'No announcement'}}}}
    settings_path = root / 'workspace-settings.json'
    settings = json.loads(settings_path.read_text())
    settings['publication_lifecycle_policy'] = policy
    settings_path.write_text(json.dumps(settings))
    workflow['ssot_readback'], _ = gate.read_workspace_settings(settings_path, 'article')
    return policy


def test_publish_entry_requires_work_packet_even_after_human_approval(packet, tmp_path):
    enable(tmp_path, packet)
    result = approve(packet, 'publish')
    assert result['status'] == 'blocked'
    assert '必須工程のwork_packet_refまたは実証拠を確認できません' in result['reasons']


def test_publish_detects_cover_omitted_from_selected_release_artifacts(packet, tmp_path):
    policy = enable(tmp_path, packet)
    policy['asset_selection_required'] = True
    policy['profiles']['article']['artifacts'] = [put(tmp_path, 'other-asset.bin', b'other asset')]
    cover = tmp_path / 'cover.png'
    cover.write_bytes(b'cover bytes')
    packet['settings']['cover_image'] = str(cover)
    settings_path = tmp_path / 'workspace-settings.json'
    settings = json.loads(settings_path.read_text())
    settings['publication_lifecycle_policy'] = policy
    settings_path.write_text(json.dumps(settings))
    packet['ssot_readback'], _ = gate.read_workspace_settings(settings_path, 'article')
    packet['work_packet_ref'] = put(tmp_path, 'work.json', valid_packet())
    result = approve(packet, 'publish')
    assert result['status'] == 'blocked'
    assert '扉絵が配送対象の実体選定から抜けています' in result['reasons']


def test_publish_checks_saved_prerequisite_without_requiring_future_publication(packet, tmp_path):
    policy = enable(tmp_path, packet)
    body_hash = policy['profiles']['article']['body']['sha256']
    target = policy['profiles']['article']['actions'][0]['target']
    binding = {'action_id': 'saved', 'kind': 'note_save', 'article_id': 'article',
               'body_sha256': body_hash, 'target': target}
    result = {'saved_body_sha256': body_hash, 'readback_complete': True,
              'artifact': put(tmp_path, 'reader.txt', b'draft')}
    original = {**binding, 'schema_version': 'note-lifecycle-observation/v1', 'body_text': 'draft', 'result': result}
    source = {**binding, 'original_observation': put(tmp_path, 'original.json', original),
              'result': result, 'result_paths': {'readback_complete': '/result/readback_complete',
                                               'artifact': '/result/artifact'}}
    evidence = {**binding, 'schema_version': 'note-lifecycle-evidence/v1',
                'source': put(tmp_path, 'source.json', source)}
    work = valid_packet()
    work['lifecycle'] = {'schema_version': 'note-publication-lifecycle/v1', 'article_id': 'article',
                         'body_sha256': body_hash, 'actions': [
                             {'id': 'saved', 'status': 'verified', 'evidence': put(tmp_path, 'saved.json', evidence)},
                             {'id': 'published', 'status': 'pending'},
                         ]}
    packet['work_packet_ref'] = put(tmp_path, 'work.json', work)
    checked = approve(packet, 'publish')
    assert checked['status'] == 'approved', checked['reasons']
    assert checked['publication_lifecycle']['remaining'][0]['id'] == 'published'
    work['lifecycle']['actions'][0] = {'id': 'saved', 'status': 'pending'}
    packet['work_packet_ref'] = put(tmp_path, 'work.json', work)
    checked = approve(packet, 'publish')
    assert checked['status'] == 'blocked'
    assert any('saved: pending' in s for s in checked['reasons'])
