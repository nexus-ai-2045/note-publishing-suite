"""全文原資料からの抜け・追加・古い説明の再使用を既存gateで止める。"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fidelity_contract', ROOT / 'scripts/provenance_label_check.py')
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

@pytest.fixture
def case(tmp_path):
    log = tmp_path / 'session.jsonl'
    events = [{'type':'session_meta','payload':{'id':'thread'}}]
    for role, text in [('user','朝は急いで決めたい。'),('assistant','成果と責任は別々に評価できます。'),
                       ('user','朝は急がず考えたい。\n\n一人でもみんなでも考えるが、一人の方が集中できる。\n\n来週は散歩する時間をとれそうな気がする。')]:
        events.append({'type':'response_item','payload':{'type':'message','role':role,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}]}})
    log.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events))
    source_path = tmp_path / 'source.json'
    source = module.capture_conversation(log,'thread','sample-essay')
    write(source_path,source)
    draft=tmp_path/'draft.md'
    draft.write_text('---\narticle_id: sample-essay\nsource_mode: conversation_reflection\narticle_lane: production_candidate\n---\n\n朝は急がず考えたい。\n\n一人でもみんなでも考えるが、一人の方が集中できる。\n\n来週は散歩する時間をとれそうな気がする。')
    units=module.conversation_units(source['messages'])
    blocks=[]
    for i,p in enumerate(module.fidelity_paragraphs(draft.read_text())):
        blocks.append(dict(index=i,text=p,kind='user-said',reason='最新の本人発言の意味と強さを保持',source_refs=[dict(unit_id=units[i+1]['id'],quote=units[i+1]['quote'])]))
    coverage=[dict(unit_id=u['id'],quote=u['quote'],disposition='represented',reason='現在の本文に保持',draft_quotes=[u['quote']]) for u in units]
    coverage[0].update(disposition='superseded',superseded_by=units[1]['id'],reason='本人が後で立場を訂正',draft_quotes=[])
    review_path=tmp_path/'review.json'
    review=dict(reviewer_id='independent-worker',draft_sha256=sha(draft),source_sha256=sha(source_path),
                source_results=[dict(unit_id=u['id'],verdict='supported',reason='訂正・理由・予感を確認、旧発言は訂正を優先') for u in units],
                block_results=[dict(index=i,verdict='supported',reason='原発言と意味・条件・強度が一致') for i in range(len(blocks))])
    write(review_path,review)
    mapping=dict(schema_version='note-conversation-fidelity/v1',article_id='sample-essay',source_sha256=sha(source_path),draft_sha256=sha(draft),writer_id='writer',source_coverage=coverage,blocks=blocks,review_path=str(review_path),review_sha256=sha(review_path))
    review['mapping_sha256']=module.fidelity_mapping_digest(mapping);write(review_path,review)
    mapping['review_sha256']=sha(review_path)
    map_path=draft.with_suffix('.fidelity.json');write(map_path,mapping)
    return dict(draft=draft,source=source,source_path=source_path,log=log,units=units,mapping=mapping,map_path=map_path,review=review,review_path=review_path,
                policy=dict(schema='note-conversation-fidelity-policy/v1',required=True,source=str(source_path),sha256=sha(source_path)))

def check(c):
    write(c['map_path'],c['mapping'])
    return module.check_conversation_fidelity(c['draft'],c['policy'],'sample-essay','thread')

def test_full_conversation_and_paragraphs_pass_without_claiming_human_adoption(case):
    result=check(case)
    assert result['status']=='mechanical_ok',result
    assert result['semantic_review']=='independent_review_recorded'
    assert result['human_adoption_verified'] is False

def test_missing_reason_unit_blocks(case):
    case['mapping']['source_coverage'].pop(2)
    assert '未分類' in check(case)['errors'][0]

def test_general_ai_judgment_without_mapping_blocks(case):
    case['draft'].write_text(case['draft'].read_text()+'\n\n成果と責任は別々に評価できるはずです。')
    case['mapping']['draft_sha256']=sha(case['draft'])
    assert '本文段落' in check(case)['errors'][0]

def test_assistant_quote_cannot_be_claimed_as_user_speech(case):
    case['mapping']['blocks'][0]['source_refs']=[dict(unit_id='m0002:p1',quote='成果と責任は別々に評価できます。')]
    assert '本人発言でない' in check(case)['errors'][0]

def test_old_position_cannot_be_reused(case):
    case['mapping']['blocks'][0]['source_refs']=[dict(unit_id=case['units'][0]['id'],quote=case['units'][0]['quote'])]
    assert '失効' in check(case)['errors'][0]

def test_nonexistent_quote_blocks(case):
    case['mapping']['blocks'][1]['source_refs'][0]['quote']='静かに考えるのは嫌い。'
    assert '引用' in check(case)['errors'][0]

def test_edited_source_extract_cannot_replace_full_log(case):
    case['source']['messages'].pop()
    write(case['source_path'],case['source']);case['policy']['sha256']=sha(case['source_path'])
    assert '選択抜粋' in check(case)['errors'][0]

def test_prediction_strength_change_report_blocks(case):
    case['review']['block_results'][2].update(verdict='meaning_changed',reason='予感が確定予測へ変わっている')
    write(case['review_path'],case['review']);case['mapping']['review_sha256']=sha(case['review_path'])
    assert '意味変化' in check(case)['errors'][0]

def test_self_review_is_not_independent(case):
    case['review']['reviewer_id']='writer';write(case['review_path'],case['review']);case['mapping']['review_sha256']=sha(case['review_path'])
    assert '自己申告' in check(case)['errors'][0]

def test_hold_blocks(case):
    case['mapping']['blocks'][0]['kind']='hold'
    assert '未採用' in check(case)['errors'][0]

def test_changed_draft_invalidates_mapping(case):
    case['draft'].write_text(case['draft'].read_text()+'\n追記')
    assert '版不一致' in check(case)['errors'][0]

def test_source_prefix_allows_appended_turns_but_not_rewritten_history(case):
    with case['log'].open('a') as f:f.write(json.dumps({'type':'event_msg','payload':{'message':'later'}})+'\n')
    assert check(case)['status']=='mechanical_ok'
    raw=case['log'].read_bytes();case['log'].write_bytes(raw.replace(b'thread',b'xxxxxx',1))
    assert 'prefix' in check(case)['errors'][0]

def test_intentional_omission_requires_reason_and_review(case):
    row=case['mapping']['source_coverage'][0]
    row.update(disposition='omitted',reason='後の説明を優先し旧立場は本文から省く')
    case['review']['mapping_sha256']=module.fidelity_mapping_digest(case['mapping'])
    write(case['review_path'],case['review']);case['mapping']['review_sha256']=sha(case['review_path'])
    assert check(case)['status']=='mechanical_ok'
    row['reason']=''
    assert '理由' in check(case)['errors'][0]

@pytest.mark.parametrize('mode',['conversation_reflection','source_pack_locked_with_user_speech_priority','other'])
@pytest.mark.parametrize('lane',['production_candidate','exploratory_draft','continuation_article'])
def test_mode_or_lane_change_does_not_disable_required_check(case,mode,lane):
    case['draft'].write_text(f'---\nsource_mode: {mode}\narticle_lane: {lane}\n---\n\n文章')
    assert check(case)['status']=='blocked'

def test_absent_policy_preserves_legacy_behavior(case):
    assert module.check_conversation_fidelity(case['draft'],None,'sample-essay')['status']=='not_required'


def test_new_author_correction_invalidates_old_source(case):
    with case['log'].open('a') as f:
        f.write(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'一人の方が集中できるという点を追加して。'}]}},ensure_ascii=False)+'\n')
    assert '最新' in check(case)['errors'][0]

def test_mapping_change_invalidates_review(case):
    case['mapping']['source_coverage'][1]['reason']='変更された理由'
    assert '対応表が変更' in check(case)['errors'][0]

def test_other_conversation_blocks(case):
    assert module.check_conversation_fidelity(case['draft'],case['policy'],'sample-essay','other')['status']=='blocked'

@pytest.mark.parametrize('field,value',[('source_coverage',[1]),('blocks',[1]),('source_coverage',{}),('blocks',None)])
def test_malformed_mapping_blocks_without_crash(case,field,value):
    case['mapping'][field]=value
    assert check(case)['status']=='blocked'

@pytest.mark.parametrize('lane',['production_candidate','exploratory_draft','continuation_article'])
def test_prepublish_runs_workspace_required_fidelity_for_every_lane(case,monkeypatch,lane):
    pre=module.__dict__.get('_pre_test')
    if pre is None:
        spec=importlib.util.spec_from_file_location('fidelity_pre_test',ROOT/'scripts/pre_publish_check.py')
        pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(pre)
    case['draft'].write_text(f'---\narticle_id: sample-essay\narticle_lane: {lane}\nsource_mode: other\n---\n\nこの記事で平和を整理します。')
    monkeypatch.setattr(pre,'read_workspace_settings',lambda *a,**k:({'conversation_fidelity_policy':case['policy']},{}))
    result=pre.check_draft(case['draft'],article_id='sample-essay',conversation_id='thread',settings_path=case['draft'].parent/'settings.json')
    assert any(i['code']=='conversation_fidelity_blocked' for i in result['issues'])


def test_assistant_explanation_needs_correct_role_quote(case):
    block = case['mapping']['blocks'][0]
    block.update(kind='assistant-organized', assistant_refs=[dict(message_id='m0002',quote='存在しない説明')])
    assert 'AI説明の引用' in check(case)['errors'][0]


def test_assistant_reference_cannot_launder_user_judgment(case):
    case['mapping']['blocks'][0]['assistant_refs']=[dict(message_id='m0002',quote='成果と責任は別々に評価できます。')]
    assert '本人判断の根拠' in check(case)['errors'][0]


def test_authorship_cli_cannot_override_history_version_mismatch(tmp_path,monkeypatch,capsys):
    import types
    spec=importlib.util.spec_from_file_location('fidelity_authorship_cli_test',ROOT/'scripts/note_authorship_gate.py')
    auth=importlib.util.module_from_spec(spec);spec.loader.exec_module(auth)
    draft=tmp_path/'draft.md';draft.write_text('一般的な説明です。')
    settings=tmp_path/'settings.json';settings.write_text('{}')
    monkeypatch.setattr(auth,'check_history_learning_from_settings',lambda *a,**k:dict(status='mechanical_ok',hashes={'target':'different-version'},settings_readback={'conversation_fidelity_policy':{'required':True}}))
    original=auth._load_sibling_module
    fake=types.SimpleNamespace(check_conversation_fidelity=lambda *a,**k:dict(status='mechanical_ok',hashes={'draft':sha(draft)},errors=[]))
    monkeypatch.setattr(auth,'_load_sibling_module',lambda name:fake if name=='provenance_label_check' else original(name))
    monkeypatch.setattr(sys,'argv',['note_authorship_gate.py',str(draft),'--settings',str(settings),'--article-id','sample-essay','--conversation-id','thread','--json'])
    assert auth.main()==1
    assert json.loads(capsys.readouterr().out)['overall']=='blocked'


def test_prepublish_cannot_exempt_heuristics_with_different_review_version(case,monkeypatch):
    import types
    spec=importlib.util.spec_from_file_location('fidelity_pre_version_test',ROOT/'scripts/pre_publish_check.py')
    pre=importlib.util.module_from_spec(spec);spec.loader.exec_module(pre)
    case['draft'].write_text('---\narticle_id: sample-essay\narticle_lane: production_candidate\n---\n\nこの記事で整理します。\n\n僕は今日、役に立ったと感じました。')
    monkeypatch.setattr(pre,'read_workspace_settings',lambda *a,**k:({'conversation_fidelity_policy':case['policy']},{}))
    original=pre._load_sibling_module
    fake=types.SimpleNamespace(check_conversation_fidelity=lambda *a,**k:dict(status='mechanical_ok',hashes={'draft':'wrong'},errors=[]))
    monkeypatch.setattr(pre,'_load_sibling_module',lambda name:fake if name=='provenance_label_check' else original(name))
    result=pre.check_draft(case['draft'],article_id='sample-essay',conversation_id='thread',settings_path=case['draft'].parent/'settings.json')
    codes={i['code'] for i in result['issues']}
    assert 'conversation_fidelity_version_mismatch' in codes
    assert 'unverified_personal_voice' in codes


def append_user(c, text):
    with c['log'].open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'type':'response_item','payload':{'type':'message','role':'user',
            'content':[{'type':'input_text','text':text}]}}, ensure_ascii=False)+'\n')


def reviewed_tail(c, text='急いで'):
    from datetime import datetime, timezone
    append_user(c, text)
    c['policy']['allow_reviewed_progress_tail'] = True
    latest = module.capture_conversation(c['log'], 'thread', 'sample-essay')
    latest_path = c['source_path'].with_name('latest.json')
    write(latest_path, latest)
    added = module.conversation_units(latest['messages'])[len(c['units']):]
    tail = dict(schema_version='note-conversation-fidelity-tail/v1', article_id='sample-essay',
        conversation_id='thread', base_source_sha256=sha(c['source_path']),
        base_prefix_sha256=c['source']['capture']['prefix_sha256'],
        base_mapping_sha256=module.fidelity_mapping_digest(c['mapping']),
        base_review_sha256=sha(c['review_path']), draft_sha256=sha(c['draft']),
        latest_source=str(latest_path), latest_source_sha256=sha(latest_path),
        reviewer_id='tail-independent-worker', reviewed_at=datetime.now(timezone.utc).isoformat(),
        review_scope='all_new_user_units_and_article_constraints',
        units=[dict(unit_id=u['id'], quote=u['quote'], quote_sha256=hashlib.sha256(u['quote'].encode()).hexdigest(),
                    classification='progress_only', reason='原文全体と記事への影響を独立確認',
                    unaffected=['body','adoption','conditions','strength','placement','settings','authority']) for u in added])
    write(c['draft'].with_suffix('.fidelity-tail.json'), tail)
    return tail


def test_strict_default_rejects_even_progress_request(case):
    append_user(case, '急いで')
    assert check(case)['status'] == 'blocked'


def test_reviewed_progress_tail_preserves_immutable_material_hashes(case):
    before = check(case)
    reviewed_tail(case)
    after = check(case)
    assert after['status'] == 'mechanical_ok', after
    assert after['approval_hashes'] == before['hashes']
    assert after['hashes']['tail_review']
    assert after['tail_unit_count'] == 1
    assert after['human_adoption_verified'] is False


@pytest.mark.parametrize('text,classification', [
    ('急いで、最終章を削除','content_instruction'),
    ('SEOを、タイトル変更禁止','condition_change'),
    ('前の承認取り消す','authority_change'),
    ('設定を変えて','settings_change'), ('判断できない','unknown'),
    ('採用を変更','adoption_change'), ('見出しへ移動','placement_change'),
    ('SEOチェックして公開して','authority_change'),
    ('末尾にはこの3カードを入れて','placement_change'),
    ('平和について新しい考えがある','content_instruction')])
def test_non_progress_classifications_reject(case, text, classification):
    tail = reviewed_tail(case, text)
    tail['units'][0]['classification'] = classification
    write(case['draft'].with_suffix('.fidelity-tail.json'), tail)
    assert check(case)['status'] == 'blocked'


@pytest.mark.parametrize('mutation', ['self_review','quote','quote_hash','missing','duplicate','base_source',
    'base_prefix','base_mapping','base_review','draft','future','unknown_effect','scope','stale','log'])
def test_tail_proof_mutations_reject(case, mutation):
    tail = reviewed_tail(case, '続けて\n\n進捗を教えて')
    if mutation == 'self_review': tail['reviewer_id'] = 'writer'
    elif mutation == 'quote': tail['units'][0]['quote'] = '別の原文'
    elif mutation == 'quote_hash': tail['units'][0]['quote_sha256'] = '0'*64
    elif mutation == 'missing': tail['units'].pop()
    elif mutation == 'duplicate': tail['units'][1] = tail['units'][0]
    elif mutation.startswith('base_'): tail[mutation+'_sha256'] = '0'*64
    elif mutation == 'draft': case['draft'].write_text(case['draft'].read_text()+'変更')
    elif mutation == 'future': tail['reviewed_at'] = '2999-01-01T00:00:00+00:00'
    elif mutation == 'unknown_effect': tail['units'][0]['unaffected'].remove('authority')
    elif mutation == 'scope': tail['review_scope'] = 'keyword_scan'
    elif mutation == 'stale': append_user(case, 'さらに続けて')
    elif mutation == 'log':
        latest_path = Path(tail['latest_source'])
        latest = json.loads(latest_path.read_text())
        other = latest_path.with_name('other.jsonl'); other.write_bytes(case['log'].read_bytes())
        latest['capture']['log_path'] = str(other)
        write(latest_path, latest); tail['latest_source_sha256'] = sha(latest_path)
    write(case['draft'].with_suffix('.fidelity-tail.json'), tail)
    assert check(case)['status'] == 'blocked'


def test_optin_without_actual_review_stays_blocked(case):
    append_user(case, '急いで')
    case['policy']['allow_reviewed_progress_tail'] = True
    assert check(case)['status'] == 'blocked'


@pytest.mark.parametrize('reviewer', ['unknown', '不明', ' writer ', ' WRITER '])
def test_unknown_or_disguised_writer_reviewer_rejected(case, reviewer):
    tail = reviewed_tail(case)
    tail['reviewer_id'] = reviewer
    write(case['draft'].with_suffix('.fidelity-tail.json'), tail)
    assert check(case)['status'] == 'blocked'


def test_sidecar_cannot_supply_arbitrary_approval_hashes(case):
    before = check(case)['hashes']
    tail = reviewed_tail(case)
    tail['approval_hashes'] = {'draft': 'forged', 'source': 'forged'}
    write(case['draft'].with_suffix('.fidelity-tail.json'), tail)
    result = check(case)
    assert result['status'] == 'mechanical_ok'
    assert result['approval_hashes'] == before


def test_material_source_change_still_invalidates_full_review(case):
    reviewed_tail(case)
    source = dict(case['source'])
    source['messages'] = list(source['messages'])
    source['messages'][0] = {**source['messages'][0], 'text': '素材を改変'}
    write(case['source_path'], source)
    case['policy']['sha256'] = sha(case['source_path'])
    assert check(case)['status'] == 'blocked'


@pytest.mark.parametrize('timestamp', ['2026-01-01T00:00:00', 'not-a-timestamp'])
def test_tail_review_requires_valid_timezone_aware_time(case, timestamp):
    tail = reviewed_tail(case)
    tail['reviewed_at'] = timestamp
    write(case['draft'].with_suffix('.fidelity-tail.json'), tail)
    assert check(case)['status'] == 'blocked'


def test_progress_tail_policy_requires_explicit_boolean(case):
    reviewed_tail(case)
    case['policy']['allow_reviewed_progress_tail'] = 'true'
    assert check(case)['status'] == 'blocked'
