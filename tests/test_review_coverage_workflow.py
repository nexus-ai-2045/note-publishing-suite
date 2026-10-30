import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_note_review_coverage import case as case, decide, save
from test_note_workflow_gate import approve, gate, packet as packet


def configure(case, packet):
    save(case)
    settings = case['root'] / 'workspace-settings.json'
    config = json.loads(settings.read_text())
    config['review_coverage_policy'] = case['policy']
    settings.write_text(json.dumps(config))
    packet['ssot_readback'], dirs = gate.read_workspace_settings(settings, 'article')
    feedback = gate._load_sibling_module('note_feedback')
    packet['feedback_readback'] = feedback.record_feedback(
        dirs, 'article', Path(packet['source_snapshot']), Path(packet['draft']),
        Path(packet['source_snapshot']), [], conversation_id='current')
    return settings


@pytest.mark.parametrize('stage', ['edit', 'layout', 'publish'])
def test_pending_blocks_only_presentation_stages(case, packet, stage):
    configure(case, packet)
    result = approve(packet, stage)
    assert result['status'] == 'blocked'
    assert result['review_coverage']['remaining'] == ['R01', 'R02']
    assert any('decision_pending' in reason for reason in result['reasons'])


def test_research_and_readout_remain_available(case, packet):
    settings = configure(case, packet)
    assert approve(packet, 'research')['status'] == 'approved'
    rows = gate.list_gates(packet, 'current', settings_path=settings)['gates']
    assert rows[0]['review_coverage']['current'] == 'R01'
    assert rows[0]['review_coverage']['remaining'] == ['R01', 'R02']


def test_reasoned_decisions_allow_workflow_cli(case, packet):
    decide(case, 0, 'rejected')
    decide(case, 1, 'held')
    settings = configure(case, packet)
    checked = approve(packet, 'edit')
    assert checked['status'] == 'approved', (checked['reasons'], checked.get('review_coverage'))
    path = case['root'] / 'packet.json'
    path.write_text(json.dumps(packet))
    result = subprocess.run([sys.executable, str(gate.SCRIPT) if hasattr(gate, 'SCRIPT') else str(Path(gate.__file__)),
                             '--packet', str(path), '--settings', str(settings),
                             '--stage', 'edit', '--conversation-id', 'current'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['review_coverage']['status'] == 'coverage_verified'
    case['decisions']['issues'].pop()
    save(case)
    result = subprocess.run([sys.executable, str(Path(gate.__file__)), '--packet', str(path),
                             '--settings', str(settings), '--stage', 'edit', '--conversation-id', 'current'],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert any('issue_missing:R02' in error for error in json.loads(result.stdout)['review_coverage']['errors'])


def test_edit_verifies_proposed_text_not_baseline(case, packet):
    issue = decide(case, 0, 'adopted')
    issue['application']['quotes'] = ['draft']
    decide(case, 1, 'rejected')
    configure(case, packet)
    Path(packet['proposed_draft']).write_text('別の記述')
    result = approve(packet, 'edit')
    assert result['status'] == 'blocked'
    assert 'R01:application_missing_or_stale' in result['review_coverage']['errors']
    assert result['review_coverage']['issues'][0]['decision'] == 'adopted'


def test_feedback_readback_exposes_pending_without_claiming_adoption(case, packet):
    settings = configure(case, packet)
    feedback = gate._load_sibling_module('note_feedback')
    result = feedback.readback(settings, 'article', Path(packet['source_snapshot']), Path(packet['draft']))
    assert result['status'] == 'readback'
    assert result['review_coverage']['remaining'] == ['R01', 'R02']
    assert result['human_adoption_verified'] is False


@pytest.mark.parametrize('mutation,expected', [
    ('delete_issue', 'issue_missing:R02'),
    ('fake_quote', 'quote_missing'),
    ('source_hash', 'hash_mismatch'),
    ('ai_adoption', 'author_decision_evidence_invalid'),
    ('missing_application', 'application_mapping_unknown'),
    ('stale_verification', 'verification_missing_invalid_or_stale'),
])
def test_negative_cases_stop_actual_workflow_cli(case, packet, mutation, expected):
    issue = decide(case, 0, 'adopted')
    issue['application']['quotes'] = ['draft']
    decide(case, 1, 'rejected')
    packet['proposed_draft'] = packet['draft']
    configure(case, packet)
    approved = approve(packet, 'edit')
    assert approved['status'] == 'approved', approved['reasons']
    if mutation == 'delete_issue':
        case['decisions']['issues'].pop()
    elif mutation == 'fake_quote':
        case['catalog']['review_coverage']['sources'][0]['units'][0]['quote'] = '原回答に存在しない引用'
    elif mutation == 'source_hash':
        (case['root'] / 'review.txt').write_text('変更された原回答')
    elif mutation == 'ai_adoption':
        evidence = issue['decision_evidence']
        evidence['actor'] = 'ai'
    elif mutation == 'missing_application':
        issue['application']['quotes'] = ['現稿に存在しない採用表現']
    elif mutation == 'stale_verification':
        verification = case['root'] / issue['verification']['path']
        data = json.loads(verification.read_text())
        data['draft_sha256'] = 'a' * 64
        from test_note_review_coverage import write_json
        issue['verification']['sha256'] = write_json(verification, data)
    settings = configure(case, packet)
    path = case['root'] / 'packet.json'
    path.write_text(json.dumps(packet))
    result = subprocess.run([sys.executable, str(Path(gate.__file__)), '--packet', str(path),
                             '--settings', str(settings), '--stage', 'edit', '--conversation-id', 'current'],
                            capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    checked = json.loads(result.stdout)
    assert any(expected in error for error in checked['review_coverage']['errors']), checked['review_coverage']
