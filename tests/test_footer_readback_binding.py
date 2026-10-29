"""既存カード選定検査の公開入口への束縛を検証する。"""
import copy
import hashlib
import json

import pytest
from test_note_workflow_gate import approve, gate, packet  # noqa: F401
footer = gate._load_sibling_module('note_footer_selection')

POLICY = {'schema': 'nps-footer-readback-policy/v1', 'required': True}
URL = 'https://note.com/example/m/m123'


def observation(article_sha, surface='reserved'):
    plan = {'article_id': 'article', 'reader': 'reader', 'series': 'series',
            'reader_action': 'read series', 'links': [dict(url=URL, registry_ref='fixture://series',
            reason='series navigation', presentation='card', required=True, require_rendered=True)]}
    plan['review'] = dict(status='approved', reviewer='fixture-user',
                         reviewed_at='2020-01-01T00:00:00+00:00', plan_sha256=footer.plan_sha256(plan))
    return dict(article_id='article', series='series', article_draft_sha256=article_sha,
                surface=surface, url='https://note.com/example/n/n123',
                captured_at='2020-01-01T00:00:00+00:00', production_plan=plan,
                footer={'nodes': [dict(tag='FIGURE', url=URL, rendered=True,
                                      title='Series', rendered_href=URL)]})


def configure(packet, tmp_path):
    path = tmp_path / 'workspace-settings.json'
    config = json.loads(path.read_text())
    profile = config['style']['article_profiles'].setdefault('article', [])
    if isinstance(profile, list):
        profile = {'references': profile}
        config['style']['article_profiles']['article'] = profile
    profile['footer_readback_policy'] = POLICY
    path.write_text(json.dumps(config))
    packet['ssot_readback'], _ = gate.read_workspace_settings(path, 'article')
    packet['layout']['footer_cards'].update(decision='include', urls=[URL])
    packet['footer_readback'] = observation(hashlib.sha256(open(packet['draft'], 'rb').read()).hexdigest())
    packet['edit_plan']['target_url'] = 'https://editor.note.com/notes/n123/edit/'
    return path


def test_article_policy_does_not_force_other_articles(packet, tmp_path):
    path = configure(packet, tmp_path)
    selected, _ = gate.read_workspace_settings(path, 'article')
    other, _ = gate.read_workspace_settings(path, 'unrelated')
    assert selected['footer_readback_policy'] == POLICY
    assert 'footer_readback_policy' not in other
    assert approve(packet, 'publish')['status'] == 'approved'


def test_text_links_only_footer_does_not_require_a_card(packet, tmp_path):
    configure(packet, tmp_path)
    data = packet['footer_readback']
    plan = data['production_plan']
    plan.update(decision='include', reason='Retain navigation through a text link')
    plan['links'][0].update(presentation='text_link', require_rendered=False)
    plan['review']['plan_sha256'] = footer.plan_sha256(plan)
    data['footer']['nodes'] = [dict(tag='A', href=URL, text='Series')]
    packet['layout']['footer_cards'].update(decision='omit', urls=[],
                                             reason='Text navigation is appropriate for this article')
    result = approve(packet, 'publish')
    assert result['status'] == 'approved', (result['reasons'], result['footer_readback'])


def test_wrapped_plan_uses_the_same_selected_cards_for_layout(packet, tmp_path):
    configure(packet, tmp_path)
    data = packet['footer_readback']
    data['production_plan'] = {'footer_selection': data['production_plan']}
    assert approve(packet, 'publish')['status'] == 'approved'
    packet['layout']['footer_cards'].update(decision='omit', urls=[],
                                             reason='Conflicting card omission in fixture')
    result = approve(packet, 'publish')
    assert result['status'] == 'blocked'
    assert 'footer_layout_plan_mismatch' in result['footer_readback']['errors']


@pytest.mark.parametrize('change', ['missing', 'wrong_version', 'wrong_article', 'editor', 'raw_url',
                                  'not_rendered', 'empty_title', 'wrong_href', 'extra', 'plan_changed'])
def test_incomplete_card_readback_blocks_publish(packet, tmp_path, change):
    configure(packet, tmp_path)
    data = packet['footer_readback']
    node = data['footer']['nodes'][0]
    if change == 'missing': packet.pop('footer_readback')
    elif change == 'wrong_version': data['article_draft_sha256'] = '0' * 64
    elif change == 'wrong_article': data['article_id'] = 'other'
    elif change == 'editor': data['surface'] = 'editor'
    elif change == 'raw_url': data['footer']['nodes'] = [dict(tag='A', href=URL, text=URL)]
    elif change == 'not_rendered': node['rendered'] = False
    elif change == 'empty_title': node['title'] = ''
    elif change == 'wrong_href': node['rendered_href'] = 'https://note.com/other'
    elif change == 'extra': data['footer']['nodes'].append(copy.deepcopy(node))
    else: data['production_plan']['links'][0]['reason'] = 'Changed reason'
    checked = approve(packet, 'publish')
    assert checked['status'] == 'blocked', checked
    assert checked['footer_readback']['status'] == 'blocked'


def test_new_readback_invalidates_old_publish_receipt(packet, tmp_path):
    configure(packet, tmp_path)
    assert approve(packet, 'publish')['status'] == 'approved'
    packet['footer_readback']['captured_at'] = '2020-01-02T00:00:00+00:00'
    assert gate.check_packet(packet, 'publish', 'current')['status'] == 'blocked'


def test_missing_target_cannot_accept_another_articles_footer(packet, tmp_path):
    configure(packet, tmp_path)
    packet['edit_plan'].pop('target_url')
    packet['footer_readback']['url'] = 'https://note.com/other/n/n999'
    checked = approve(packet, 'publish')
    assert checked['status'] == 'blocked'
    assert checked['footer_readback']['status'] == 'blocked'


@pytest.mark.parametrize('edit_plan', [None, [], '', False])
def test_legacy_publish_without_footer_policy_accepts_optional_edit_plan(packet, edit_plan):
    packet['edit_plan'] = edit_plan
    assert approve(packet, 'publish')['status'] == 'approved'


@pytest.mark.parametrize('article_id', ['missing', None, [], '', False])
def test_invalid_article_identity_returns_a_blocked_publish_result(packet, article_id):
    if article_id == 'missing':
        packet.pop('article_id')
    else:
        packet['article_id'] = article_id
    assert gate.check_packet(packet, 'publish', 'current')['status'] == 'blocked'


@pytest.mark.parametrize('edit_plan', [None, [], '', False])
def test_required_footer_blocks_invalid_target_plan_without_crashing(packet, tmp_path, edit_plan):
    configure(packet, tmp_path)
    packet['edit_plan'] = edit_plan
    result = approve(packet, 'publish')
    assert result['status'] == 'blocked'
    assert result['footer_readback']['status'] == 'blocked'


def test_reserved_card_is_not_public_readback():
    data = observation('a' * 64)
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64,
                                 expected_url=data['url'])['status'] == 'ok'
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64,
                                 public_only=True)['status'] == 'blocked'


def test_different_public_article_cannot_supply_footer():
    data = observation('a' * 64, 'public')
    data['url'] = 'https://note.com/other/n/n999'
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64,
                                 public_only=True, expected_url='https://note.com/example/n/n123')['status'] == 'blocked'


def test_reserved_reader_matches_editor_for_same_note():
    data = observation('a' * 64)
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64,
                                 expected_url='https://editor.note.com/notes/n123/edit/')['status'] == 'ok'


def test_postpublish_rejects_nested_footer_for_other_note():
    module = gate._load_sibling_module('note_postpublish_review')
    observed = dict(schema='note-public-observation/v1', note_id='n123',
                    url='https://note.com/example/n/n123', body='A complete public article',
                    footer_readback=observation('a' * 64, 'public'))
    observed['footer_readback']['url'] = 'https://note.com/other/n/n999'
    context = dict(policy=POLICY, article_id='article', article_sha256='a' * 64)
    result = module.check_postpublish_review(observed, footer_context=context)
    assert result['footer_readback']['status'] == 'blocked'
    assert result['postpublication_complete'] is False


def test_omit_has_explicit_reason_and_empty_observation():
    data = observation('a' * 64)
    plan = data['production_plan']
    plan.update(decision='omit', reason='No relevant navigation for this article', links=[])
    plan['review']['plan_sha256'] = footer.plan_sha256(plan)
    data['footer']['nodes'] = []
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64,
                                 expected_url=data['url'])['status'] == 'ok'
    data.pop('footer')
    assert footer.check_readback(POLICY, data, article_id='article', article_sha256='a' * 64)['status'] == 'blocked'


def test_postpublish_entry_checks_cards_before_editorial_completion(tmp_path):
    note_postpublish_review = gate._load_sibling_module('note_postpublish_review')
    observed = dict(schema='note-public-observation/v1', note_id='n123',
                    url='https://note.com/example/n/n123', body='A complete public article')
    context = dict(policy=POLICY, article_id='article', article_sha256='a' * 64)
    checked = note_postpublish_review.check_postpublish_review(observed, footer_context=context)
    assert checked['status'] == 'blocked'
    assert checked['postpublication_complete'] is False
    observed['footer_readback'] = observation('a' * 64, 'public')
    checked = note_postpublish_review.check_postpublish_review(observed, footer_context=context)
    assert checked['footer_readback']['status'] == 'ok'
    assert checked['postpublication_complete'] is False
