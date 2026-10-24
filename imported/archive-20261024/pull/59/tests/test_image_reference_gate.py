import hashlib
import json
from pathlib import Path

import pytest

from scripts.image_reference_gate import check, check_settings, digest


def save(path, data):
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def pack(tmp_path):
    reference = tmp_path / 'reference.png'
    reference.write_bytes(b'reference')
    output = tmp_path / 'output.png'
    output.write_bytes(b'generated output')
    manifest = save(tmp_path / 'manifest.json', {'files': [{'path': reference.name, 'sha256': digest(reference), 'state': 'imported'}]})
    policy = save(tmp_path / 'policy.json', {'schema': 'image-reference-policy/v1', 'required_character_id': 'fixture-character', 'reference_manifest': manifest.name, 'required_roles': ['identity']})
    receipt = save(tmp_path / 'receipt.json', {'schema': 'image-reference-receipt/v1', 'character_id': 'fixture-character', 'policy_sha256': digest(policy), 'reference_manifest_sha256': digest(manifest), 'references': [{'path': reference.name, 'sha256': digest(reference), 'role': 'identity'}], 'referenced_image_paths': [reference.name], 'prompt': 'render supplied character', 'prompt_sha256': hashlib.sha256(b'render supplied character').hexdigest(), 'output': {'path': output.name, 'sha256': digest(output)}, 'visual_qa': {'output_sha256': digest(output), 'status': 'pass', 'reviewer': 'fixture-reviewer', 'observations': [{'criterion': 'identity', 'observation': 'Compared face shape against the supplied reference.', 'reference_path': reference.name}]}})
    return policy, receipt, reference, output


def test_current_evidence_and_imported_references_pass(pack):
    policy, receipt, _, output = pack
    assert check(policy, receipt, output_path=output)['status'] == 'ok'


@pytest.mark.parametrize('mutation', ['missing_reference', 'changed_reference', 'no_passed_reference', 'wrong_character', 'output_replaced', 'different_qa_output', 'checkbox_only', 'missing_role'])
def test_stale_or_missing_evidence_is_blocked(pack, mutation):
    policy, receipt, reference, output = pack
    data = json.loads(receipt.read_text())
    if mutation == 'missing_reference':
        reference.unlink()
    elif mutation == 'changed_reference':
        reference.write_bytes(b'changed')
    elif mutation == 'no_passed_reference':
        data['referenced_image_paths'] = []
    elif mutation == 'wrong_character':
        data['character_id'] = 'generic-person'
    elif mutation == 'output_replaced':
        output.write_bytes(b'replaced')
    elif mutation == 'different_qa_output':
        data['visual_qa']['output_sha256'] = '0' * 64
    elif mutation == 'checkbox_only':
        data['visual_qa']['observations'] = []
    else:
        data['references'][0]['role'] = 'irrelevant'
    save(receipt, data)
    assert check(policy, receipt)['status'] == 'blocked'


def test_pre_generation_needs_inputs_but_not_generated_output(pack):
    policy, receipt, _, _ = pack
    data = json.loads(receipt.read_text())
    del data['output'], data['visual_qa']
    save(receipt, data)
    assert check(policy, receipt, stage='pre_generation')['status'] == 'ok'
    assert check(policy, receipt)['status'] == 'blocked'


def test_declared_policy_missing_receipt_blocks_and_no_policy_is_compatible(pack):
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    assert check_settings(settings)['status'] == 'blocked'
    save(settings, {'workspace_root': '.'})
    assert check_settings(settings)['status'] == 'not_required'


def test_alternate_upload_output_blocks(pack):
    policy, receipt, _, output = pack
    alternate = output.with_name('other.png')
    alternate.write_bytes(output.read_bytes())
    assert check(policy, receipt, output_path=alternate)['status'] == 'blocked'


def test_pre_publish_entry_calls_same_validator(pack):
    from scripts.pre_publish_check import check_draft
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    draft = policy.parent / 'draft.md'
    draft.write_text('---\narticle_lane: exploratory_draft\n---\n# Example\n\nBody.\n')
    result = check_draft(draft, settings_path=settings)
    assert any(item['code'] == 'image_reference_blocked' for item in result['issues'])


def test_workflow_entry_blocks_missing_image_receipt(pack, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from scripts.note_workflow_gate import check_packet
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    packet = {'schema_version': 'note-workflow-review/v1', 'article_id': 'fixture', 'conversation_id': 'fixture', 'route': 'direct_draft', 'receipts': []}
    result = check_packet(packet, 'edit', 'fixture', settings_path=settings)
    assert any('image_reference:' in reason for reason in result['reasons'])


def test_editor_pre_save_entry_blocks_missing_image_receipt(pack):
    from scripts.note_editor_pdca_cycle_check import check as cycle_check
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    cycle = save(policy.parent / 'cycle.json', {'schema': 'note-editor-pdca-cycle-receipt/v1', 'state': 'open', 'cycles': []})
    result = cycle_check(cycle, settings_path=settings)
    assert any('image_reference:' in error for error in result['errors'])


@pytest.mark.parametrize('stage', ['image_edit', 'pre_save'])
def test_operation_stage_requires_actual_output(pack, stage):
    policy, receipt, _, output = pack
    assert check(policy, receipt, stage=stage)['status'] == 'blocked'
    assert check(policy, receipt, stage=stage, output_path=output)['status'] == 'ok'
    assert check(None, None, stage=stage)['status'] == 'not_required'


def test_qa_can_validate_recorded_output_without_upload_target(pack):
    policy, receipt, _, _ = pack
    assert check(policy, receipt, stage='qa')['status'] == 'ok'


def test_existing_article_profile_scopes_policy_without_other_article_leak(pack):
    policy, receipt, _, _ = pack
    data = json.loads(receipt.read_text()); data['article_id'] = 'target'; save(receipt, data)
    settings = save(policy.parent/'settings.json', {'workspace_root':'.', 'style':{'article_profiles':{'target':{'references':[], 'image_reference_policy':policy.name,'image_reference_receipt':receipt.name}, 'other':['voice.md']}}})
    assert check_settings(settings)['status']=='blocked'
    assert check_settings(settings, article_id='target')['status']=='ok'
    assert check_settings(settings, article_id='other')['status']=='not_required'
    assert check_settings(settings, article_id='unregistered')['status']=='not_required'


@pytest.mark.parametrize('wrong_id', [None, 'other'])
def test_scoped_receipt_must_match_article_id(pack, wrong_id):
    policy, receipt, _, _ = pack
    data = json.loads(receipt.read_text())
    data['article_id'] = wrong_id
    save(receipt, data)
    settings = save(policy.parent/'settings.json', {'workspace_root':'.', 'style':{'article_profiles':{
        'target': {'references': [], 'image_reference_policy':policy.name, 'image_reference_receipt':receipt.name}}}})
    assert check_settings(settings, article_id='target')['status'] == 'blocked'


@pytest.mark.parametrize('changed', ['policy', 'manifest', 'receipt', 'reference', 'output'])
def test_changed_input_during_validation_cannot_bind_unverified_bytes(pack, monkeypatch, changed):
    policy, receipt, reference, output = pack
    paths = {'policy':policy, 'manifest':policy.parent/'manifest.json', 'receipt':receipt,
             'reference':reference, 'output':output}
    target = paths[changed]
    original = Path.read_bytes
    swapped = False
    def racing_read(path):
        nonlocal swapped
        raw = original(path)
        if path.resolve() == target.resolve() and not swapped:
            swapped = True
            path.write_bytes(raw + b' changed')
        return raw
    monkeypatch.setattr(Path, 'read_bytes', racing_read)
    assert check(policy, receipt)['status'] == 'blocked'


@pytest.mark.parametrize('stage', ['edit', 'settings'])
def test_text_or_settings_operation_without_cover_uses_recorded_qa(pack, stage, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from note_workflow_gate import check_packet
    policy, receipt, _, _ = pack
    settings = save(policy.parent/'settings.json', {'workspace_root':'.',
        'image_reference_policy':policy.name, 'image_reference_receipt':receipt.name})
    packet = {'schema_version':'note-workflow-review/v1','article_id':'fixture','conversation_id':'fixture',
              'route':'direct_draft','receipts':[], 'settings':{'cover_image':None}}
    result = check_packet(packet, stage, 'fixture', settings_path=settings)
    assert not any(reason.startswith('image_reference:') for reason in result['reasons'])
    assert 'image_reference_evidence' in result['content_hashes']


def test_settings_swap_during_validation_is_blocked(pack, monkeypatch):
    policy, receipt, _, _ = pack
    settings = save(policy.parent/'settings.json', {'workspace_root':'.',
        'image_reference_policy':policy.name, 'image_reference_receipt':receipt.name})
    original = Path.read_bytes
    swapped = False
    def racing_read(path):
        nonlocal swapped
        raw = original(path)
        if path.resolve() == settings.resolve() and not swapped:
            swapped = True
            path.write_bytes(raw + b' changed')
        return raw
    monkeypatch.setattr(Path, 'read_bytes', racing_read)
    assert check_settings(settings)['status'] == 'blocked'
