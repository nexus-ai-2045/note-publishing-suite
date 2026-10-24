import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from image_reference_gate import check, check_settings, digest


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
    candidates = [dict(path=output.name, sha256=digest(output), composition="正面で対話する構図")]
    for index, composition in ((2, "窓辺で横を向く構図"), (3, "俯瞰で机全体を見せる構図")):
        candidate = tmp_path / f"candidate-{index}.png"
        candidate.write_bytes(f"different generated output {index}".encode())
        candidates.append(dict(path=candidate.name, sha256=digest(candidate), composition=composition))
    data = json.loads(receipt.read_text())
    data.update(planned_candidate_count=3, draft_candidates=candidates)
    save(receipt, data)
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
    from pre_publish_check import check_draft
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    draft = policy.parent / 'draft.md'
    draft.write_text('---\narticle_lane: exploratory_draft\n---\n# Example\n\nBody.\n')
    result = check_draft(draft, settings_path=settings)
    assert any(item['code'] == 'image_reference_blocked' for item in result['issues'])


@pytest.mark.parametrize('lane', ['exploratory_draft', 'editor_fixture'])
def test_generic_qa_image_only_settings_do_not_require_history(pack, lane):
    from pre_publish_check import check_draft
    policy, receipt, _, _ = pack
    settings = save(policy.parent / 'settings.json', {
        'workspace_root': '.', 'image_reference_policy': policy.name,
        'image_reference_receipt': receipt.name})
    draft = policy.parent / 'draft.md'
    draft.write_text(f'---\narticle_lane: {lane}\n---\n# Example\n\nBody.\n')
    result = check_draft(draft, settings_path=settings)
    assert not any(item['code'].startswith('history_') for item in result['issues'])


@pytest.mark.parametrize('lane', ['production_candidate', 'continuation_article'])
def test_production_qa_image_only_settings_still_require_history(pack, lane):
    from pre_publish_check import check_draft
    policy, receipt, _, _ = pack
    settings = save(policy.parent / 'settings.json', {
        'workspace_root': '.', 'image_reference_policy': policy.name,
        'image_reference_receipt': receipt.name})
    draft = policy.parent / 'draft.md'
    draft.write_text(f'---\narticle_lane: {lane}\n---\n# Example\n\nBody.\n')
    result = check_draft(draft, settings_path=settings, article_id='fixture')
    assert any(item['code'] == 'history_learning_context_unverified' for item in result['issues'])


def test_workflow_entry_blocks_missing_image_receipt(pack, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from note_workflow_gate import check_packet
    policy, _, _, _ = pack
    settings = save(policy.parent / 'settings.json', {'workspace_root': '.', 'image_reference_policy': policy.name})
    packet = {'schema_version': 'note-workflow-review/v1', 'article_id': 'fixture', 'conversation_id': 'fixture', 'route': 'direct_draft', 'receipts': []}
    result = check_packet(packet, 'edit', 'fixture', settings_path=settings)
    assert any('image_reference:' in reason for reason in result['reasons'])


def test_editor_pre_save_entry_blocks_missing_image_receipt(pack):
    from note_editor_pdca_cycle_check import check as cycle_check
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


def three_draft_policy(pack):
    policy, receipt, _, output = pack
    config = json.loads(policy.read_text())
    config['draft_candidate_count'] = 3
    save(policy, config)
    data = json.loads(receipt.read_text())
    data.update(policy_sha256=digest(policy), article_id='article', planned_candidate_count=3)
    data.pop('draft_candidates', None)
    save(receipt, data)
    return policy, receipt, output, data


def generated_candidates(output):
    rows = []
    for index in range(3):
        path = output if index == 0 else output.with_name(f'draft-{index}.png')
        if index: path.write_bytes(f'generated composition {index}'.encode())
        rows.append(dict(path=path.name, sha256=digest(path), composition=f'構図案{index}'))
    return rows


@pytest.mark.parametrize('stage', ['qa', 'pre_save', 'image_edit', 'publish'])
def test_three_drafts_policy_requires_actual_candidates(pack, stage):
    policy, receipt, output, data = three_draft_policy(pack)
    assert check(policy, receipt, stage=stage, output_path=output, article_id='article')['status'] == 'blocked'
    data['draft_candidates'] = generated_candidates(output)
    save(receipt, data)
    assert check(policy, receipt, stage=stage, output_path=output, article_id='article')['status'] == 'ok'


@pytest.mark.parametrize('problem', ['missing', 'changed', 'duplicate_bytes', 'duplicate_composition', 'placeholder', 'selected_missing'])
def test_three_drafts_rejects_plans_or_stale_files(pack, problem):
    policy, receipt, output, data = three_draft_policy(pack)
    rows = generated_candidates(output)
    path = output.with_name(rows[1]['path'])
    if problem == 'missing': path.unlink()
    elif problem == 'changed': path.write_bytes(b'changed')
    elif problem == 'duplicate_bytes':
        path.write_bytes(output.read_bytes()); rows[1]['sha256'] = digest(path)
    elif problem == 'duplicate_composition': rows[1]['composition'] = rows[0]['composition']
    elif problem == 'placeholder': rows[1]['composition'] = ' TODO '
    else: rows[0] = dict(path=path.name, sha256=digest(path), composition='別の構図')
    data['draft_candidates'] = rows
    save(receipt, data)
    assert check(policy, receipt, output_path=output, article_id='article')['status'] == 'blocked'


def early_selection(output):
    return dict(article_id='article', output_sha256=digest(output), actor='user', status='approved',
                reason='最初の候補を本人が採用', evidence_ref='conversation://selection/123',
                observed_at='2026-10-15T12:00:00+09:00')


def test_three_drafts_explicit_early_selection_allows_one(pack):
    policy, receipt, output, data = three_draft_policy(pack)
    data['early_selection'] = early_selection(output)
    save(receipt, data)
    assert check(policy, receipt, output_path=output, article_id='article')['status'] == 'ok'


@pytest.mark.parametrize('field,value', [('article_id','other'), ('output_sha256','0'*64),
    ('actor','assistant'), ('status','pending'), ('reason','TODO'), ('evidence_ref','unknown'),
    ('observed_at','2026-10-15T12:00:00'), ('observed_at','unknown')])
def test_three_drafts_early_selection_must_bind_human_receipt(pack, field, value):
    policy, receipt, output, data = three_draft_policy(pack)
    data['early_selection'] = early_selection(output)
    data['early_selection'][field] = value
    save(receipt, data)
    assert check(policy, receipt, output_path=output, article_id='article')['status'] == 'blocked'


@pytest.mark.parametrize('planned', [None, 1, True, '3', 3])
def test_three_drafts_pre_generation_requires_plan_only(pack, planned):
    policy, receipt, output, data = three_draft_policy(pack)
    data.pop('output'); data.pop('visual_qa')
    data['planned_candidate_count'] = planned
    output.unlink()
    save(receipt, data)
    assert check(policy, receipt, stage='pre_generation')['status'] == ('ok' if type(planned) is int and planned == 3 else 'blocked')


@pytest.mark.parametrize("stage", ["pre_generation", "qa", "publish"])
def test_existing_v1_policy_without_candidate_count_requires_three(pack, stage):
    policy, receipt, _, output = pack
    assert "draft_candidate_count" not in json.loads(policy.read_text())
    data = json.loads(receipt.read_text())
    if stage == "pre_generation":
        data.pop("planned_candidate_count")
    else:
        data.pop("draft_candidates")
    save(receipt, data)
    assert check(policy, receipt, stage=stage, output_path=output)["status"] == "blocked"
