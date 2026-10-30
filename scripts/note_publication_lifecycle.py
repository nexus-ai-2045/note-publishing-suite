"""Read-only, policy-bound closeout checks; local evidence is not authentication."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

MAX_BYTES = 4 * 1024 * 1024
KINDS = {'note_save', 'note_publication', 'postpublish_review', 'announcement_draft',
         'announcement_send', 'ledger_update', 'git_delivery'}
STATUSES = {'prepared', 'sent', 'verified', 'awaiting_human', 'pending', 'unknown',
            'blocked', 'not_applicable'}
EXTERNAL = {'note_publication', 'announcement_send', 'git_delivery'}


class _ProseText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get('class') or '').split())
        hidden = tag in {'figure', 'iframe', 'script', 'style', 'table-of-contents'} or bool(classes & {
            'embed-card', 'toc-block', 'heading-warn', 'warn-note', 'figure-placeholder__label',
            'figure-placeholder__missing', 'figure-placeholder__detail'})
        if tag not in {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr'}:
            if len(self.stack) >= 256:
                raise ValueError('HTML nesting exceeds safe limit')
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        caption = any(tag == 'figcaption' for tag, _ in self.stack)
        if not any(hidden and (tag != 'figure' or not caption) for tag, hidden in self.stack):
            self.parts.append(data)


def prose_sha256(text: str, *, html: bool = False) -> str:
    if html:
        parser = _ProseText()
        parser.feed(text)
        text = ''.join(parser.parts)
    return hashlib.sha256(re.sub(r'\s+', '', text).encode('utf-8')).hexdigest()


def draft_reader_sha256(data: bytes) -> str:
    spec = importlib.util.spec_from_file_location('_lifecycle_preview', Path(__file__).with_name('note_virtual_preview.py'))
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    body = preview.strip_frontmatter(data.decode('utf-8'))
    rendered = preview.render_body_html(body, {})
    rendered = rendered.replace('\\_', '_')
    return prose_sha256(rendered, html=True)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def strict_json(data: bytes | str) -> dict:
    try:
        value = json.loads(data, object_pairs_hook=_object,
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except RecursionError as exc:
        raise ValueError('JSON nesting exceeds safe limit') from exc
    if not isinstance(value, dict):
        raise ValueError('JSON root must be an object')
    return value


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def read_artifact(root: Path, ref: dict) -> tuple[bytes, Path]:
    if not isinstance(ref, dict) or not _text(ref.get('path')) or not _digest(ref.get('sha256')):
        raise ValueError('artifact requires path and sha256')
    data, path = _read_regular(root, Path(ref['path']))
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError('artifact hash mismatch')
    return data, path


def _read_regular(root: Path, path: Path) -> tuple[bytes, Path]:
    root = root.resolve(strict=True)
    path = path if path.is_absolute() else root / path
    if '..' in path.parts or not path.is_relative_to(root):
        raise ValueError('artifact escapes workspace')
    parts = path.relative_to(root).parts
    _require(bool(parts), 'artifact must name a file')
    _require(hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY') and os.open in os.supports_dir_fd,
             'safe artifact reading is unavailable on this platform')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('artifact must be a bounded regular file')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('artifact size exceeded')
    return data, path


def load_input_json(path: Path) -> dict:
    absolute = path.absolute()
    data, _ = _read_regular(absolute.parent.resolve(strict=True), Path(absolute.name))
    return strict_json(data)


def _require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def _result_check(kind: str, result: dict, target: dict, body_hash: str,
                  article_id: str, root: Path, reader_hash: str | None):
    _require(isinstance(result, dict), 'source result must be an object')
    if kind == 'note_save':
        _require(_digest(reader_hash) and result.get('saved_body_sha256') == reader_hash and result.get('readback_complete') is True,
                 'saved body readback is incomplete or stale')
    elif kind == 'note_publication':
        _require(result.get('published') is True and result.get('readback_complete') is True
                 and _digest(reader_hash) and result.get('public_body_sha256') == reader_hash
                 and _text(target.get('url')) and result.get('public_url') == target['url'],
                 'public page readback is missing or mismatched')
    elif kind == 'postpublish_review':
        entry = result.get('published_entry')
        _require(result.get('postpublication_complete') is True and isinstance(entry, dict)
                 and _text(target.get('url')) and entry.get('note_id') == target['url'].rstrip('/').split('/')[-1]
                 and entry.get('article_id') == article_id and entry.get('body_sha256') == body_hash,
                 'postpublication review incomplete or for another article/version')
    elif kind == 'announcement_draft':
        _require(result.get('reviewed') is True and _digest(result.get('draft_sha256'))
                 and _text(target.get('url')) and result.get('card_url') == target['url']
                 and _text(result.get('card_title')) and _text(result.get('card_description')),
                 'announcement draft or card is incomplete')
    elif kind == 'announcement_send':
        _require(result.get('sent') is True and result.get('readback_complete') is True
                 and _text(result.get('message_id')) and _text(result.get('url'))
                 and _text(target.get('destination_id'))
                 and result.get('destination_id') == target['destination_id']
                 and result.get('body_sha256') == body_hash,
                 'announcement send/readback is absent or wrong destination/version')
        template = target.get('message_url_template')
        _require(_text(template) and template.startswith('https://') and template.count('{message_id}') == 1
                 and not any(char in template.replace('{message_id}', '') for char in '{}')
                 and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', result['message_id']) is not None
                 and result['url'] == template.replace('{message_id}', result['message_id']),
                 'announcement message URL does not match its destination and message ID')
    elif kind == 'ledger_update':
        _require(result.get('entry_article_id') == article_id
                 and result.get('entry_body_sha256') == body_hash
                 and result.get('readback_complete') is True, 'ledger readback is missing or stale')
    elif kind == 'git_delivery':
        _require(isinstance(result.get('commit'), str)
                 and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', result['commit']) is not None
                 and result.get('remote_commit') == result['commit']
                 and result.get('clean') is True and result.get('executed') is True
                 and type(result.get('exit_code')) is int and result['exit_code'] == 0,
                 'Git execution/remote readback is incomplete')
        _require(_text(target.get('repository')) and _text(target.get('branch'))
                 and result.get('repository') == target['repository'] and result.get('branch') == target['branch'],
                 'Git repository or branch mismatch')
    if kind in {'note_save', 'note_publication', 'announcement_draft', 'ledger_update', 'git_delivery'}:
        data, _ = read_artifact(root, result.get('artifact'))
        actual_hash = hashlib.sha256(data).hexdigest()
        if kind in {'note_save', 'note_publication'}:
            _require(prose_sha256(data.decode('utf-8'), html=result.get('artifact_format') == 'html') == reader_hash,
                     'readback artifact differs from reader body')
        if kind == 'announcement_draft':
            _require(actual_hash == result['draft_sha256'], 'draft artifact differs from reviewed draft')
        if kind == 'ledger_update':
            entry = strict_json(data)
            _require(entry.get('article_id') == article_id and entry.get('body_sha256') == body_hash,
                     'ledger artifact differs from expected entry')
        if kind == 'git_delivery':
            remote_data, remote_path = read_artifact(root, result.get('remote_artifact'))
            _require(remote_path != read_artifact(root, result.get('artifact'))[1] and remote_data == data,
                     'remote delivery artifact differs or reuses local artifact')
            receipt = strict_json(data)
            _require(receipt.get('commit') == result['commit'] and receipt.get('remote_commit') == result['commit']
                     and receipt.get('article_id') == article_id and receipt.get('body_sha256') == body_hash,
                     'Git artifact differs from delivery result')


def check_lifecycle(packet: dict, settings: dict, workspace_root: Path, *,
                    article_id: str | None, stage: str = 'closeout') -> dict[str, Any]:
    """Check policy-selected prerequisites, or all actions at accepted/closed closeout."""
    errors: list[str] = []
    remaining: list[dict] = []
    outcome = {'ok': False, 'enabled': True, 'stage': stage, 'stop_causes': errors,
               'remaining': remaining, 'current': None, 'next': None,
               'authenticity_notice': 'Local artifact consistency only; no proof of remote authenticity.'}
    try:
        _require(isinstance(packet, dict) and isinstance(settings, dict), 'packet/settings must be objects')
        policy = settings.get('publication_lifecycle_policy')
        if policy is None and 'lifecycle' not in packet:
            return {**outcome, 'ok': True, 'enabled': False}
        _require(isinstance(policy, dict) and type(policy.get('required')) is bool,
                 'publication_lifecycle_policy requires boolean required')
        if not policy['required'] and 'lifecycle' not in packet:
            return {**outcome, 'ok': True, 'enabled': False}
        _require(_text(article_id), 'article_id is required')
        profiles = policy.get('profiles')
        _require(isinstance(profiles, dict) and isinstance(profiles.get(article_id), dict),
                 'article lifecycle profile is required')
        profile = profiles[article_id]
        body, _ = read_artifact(Path(workspace_root), profile.get('body'))
        body_hash = hashlib.sha256(body).hexdigest()
        release_hash = None
        if policy.get('asset_selection_required') is True or 'artifacts' in profile:
            artifacts = profile.get('artifacts')
            _require(isinstance(artifacts, list) and len(artifacts) <= 64, 'release artifact selection is required')
            _require(bool(artifacts) or _text(profile.get('asset_omission_reason')), 'asset omission requires a reason')
            manifest = {}
            for ref in artifacts:
                asset_bytes, asset_path = read_artifact(Path(workspace_root), ref)
                name = asset_path.relative_to(Path(workspace_root).resolve()).as_posix()
                _require(name not in manifest, 'duplicate release artifact')
                manifest[name] = hashlib.sha256(asset_bytes).hexdigest()
            release_hash = hashlib.sha256(json.dumps({'body_sha256': body_hash, 'artifacts': manifest},
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            outcome['release_sha256'] = release_hash
        reader_hash = draft_reader_sha256(body)
        declared_reader_hash = profile['body'].get('reader_text_sha256')
        _require(declared_reader_hash is None or declared_reader_hash == reader_hash,
                 'reader hash does not derive from current draft')
        specs = profile.get('actions')
        _require(isinstance(specs, list) and 0 < len(specs) <= 128, 'policy actions must contain 1 to 128 actions')
        by_id = {}
        for spec in specs:
            _require(isinstance(spec, dict) and _text(spec.get('id')), 'invalid policy action')
            aid = spec['id']
            _require(aid not in by_id, 'duplicate policy action')
            _require(isinstance(spec.get('kind'), str) and spec['kind'] in KINDS, 'unknown action kind')
            _require(_text(spec.get('stage')) and spec['stage'] != 'closeout', 'invalid action stage')
            _require(isinstance(spec.get('target'), dict) and bool(spec['target']), 'target must be non-empty object')
            deps = spec.get('depends_on')
            _require(isinstance(deps, list) and all(_text(d) for d in deps)
                     and len(set(deps)) == len(deps), 'invalid dependencies')
            _require('authorized' not in spec or type(spec['authorized']) is bool, 'authorized must be boolean')
            by_id[aid] = dict(spec)
        required_kinds = policy.get('required_kinds', [])
        _require(isinstance(required_kinds, list) and all(isinstance(k, str) and k in KINDS for k in required_kinds),
                 'required action kinds are invalid')
        _require(set(required_kinds).issubset({s['kind'] for s in specs}),
                 'required action kind removed from article plan')
        if policy.get('announcement_selection_required') is True:
            selection = profile.get('announcement_selection')
            _require(isinstance(selection, dict), 'announcement selection is required')
            announcement_specs = [s for s in specs if s['kind'].startswith('announcement_')]
            if selection.get('state') == 'not_required':
                _require(_text(selection.get('reason')) and not announcement_specs,
                         'announcement omission needs a reason and no selected actions')
            else:
                slots = selection.get('slots')
                _require(selection.get('state') == 'selected' and isinstance(slots, list)
                         and bool(slots) and all(_text(s) for s in slots) and len(set(slots)) == len(slots),
                         'announcement slots are invalid')
                _require(all(s.get('slot') in slots for s in announcement_specs), 'unselected announcement action')
                for slot in slots:
                    _require(sorted(s['kind'] for s in announcement_specs if s.get('slot') == slot)
                             == ['announcement_draft', 'announcement_send'],
                             'selected announcement requires draft and send actions')
        kind_ids = {kind: [aid for aid, s in by_id.items() if s['kind'] == kind] for kind in KINDS}
        for aid, spec in by_id.items():
            dependencies = list(spec['depends_on'])
            if spec['kind'] == 'note_publication':
                _require(bool(kind_ids['note_save']), 'publication requires a saved-body readback')
                dependencies += kind_ids['note_save'] + kind_ids['announcement_draft']
            if spec['kind'] in {'announcement_send', 'postpublish_review', 'ledger_update'}:
                _require(bool(kind_ids['note_publication']), 'operation requires a publication readback')
                dependencies += kind_ids['note_publication']
            spec['depends_on'] = list(dict.fromkeys(dependencies))
        visited, active = set(), set()
        def visit(aid):
            _require(aid in by_id, 'unknown dependency')
            _require(aid not in active, 'dependency cycle')
            if aid in visited:
                return
            active.add(aid)
            for dep in by_id[aid]['depends_on']:
                visit(dep)
            active.remove(aid)
            visited.add(aid)
        for aid in by_id:
            visit(aid)
        stage_targets = ([aid for aid, s in by_id.items() if s['kind'] == 'note_publication'] if stage == 'publish'
                         else kind_ids[stage] if stage in KINDS
                         else [aid for aid, s in by_id.items() if s['stage'] == stage])
        _require(stage == 'closeout' or bool(stage_targets), 'unknown stage')
        lifecycle = packet.get('lifecycle')
        _require(isinstance(lifecycle, dict), 'lifecycle is required')
        _require(lifecycle.get('schema_version') == 'note-publication-lifecycle/v1'
                 and lifecycle.get('article_id') == article_id
                 and lifecycle.get('body_sha256') == body_hash, 'lifecycle version/article/body mismatch')
        if release_hash is not None:
            _require(lifecycle.get('release_sha256') == release_hash, 'lifecycle release artifacts are stale')
        actions = lifecycle.get('actions')
        _require(isinstance(actions, list), 'lifecycle actions must be a list')
        state = {}
        for action in actions:
            _require(isinstance(action, dict) and _text(action.get('id')), 'invalid lifecycle action')
            aid = action['id']
            _require(aid in by_id and aid not in state, 'unknown or duplicate lifecycle action')
            _require(isinstance(action.get('status'), str) and action['status'] in STATUSES, 'unknown action status')
            state[aid] = action
        _require(set(state) == set(by_id), 'lifecycle action requirements removed or missing')
        required = set(by_id) if stage == 'closeout' or packet.get('status') in {'accepted', 'closed'} else set()
        def prerequisites(aid):
            for dep in by_id[aid]['depends_on']:
                if dep not in required:
                    required.add(dep)
                    prerequisites(dep)
        if not required:
            for aid in stage_targets:
                prerequisites(aid)
        used_receipts, used_sources, used_originals = set(), set(), set()
        verified = set()
        verified_results = {}
        for spec in specs:
            aid, kind = spec['id'], spec['kind']
            action = state[aid]
            status = action['status']
            if kind in EXTERNAL and spec.get('authorized') is not True:
                status = 'awaiting_human'
            issue = None
            if status == 'verified':
                try:
                    data, path = read_artifact(Path(workspace_root), action.get('evidence'))
                    _require(path not in used_receipts, 'receipt reused')
                    used_receipts.add(path)
                    evidence = strict_json(data)
                    _require(evidence.get('schema_version') == 'note-lifecycle-evidence/v1', 'invalid evidence schema')
                    binding = {'action_id': aid, 'kind': kind, 'article_id': article_id,
                               'body_sha256': body_hash, 'target': spec['target']}
                    if release_hash is not None:
                        binding['release_sha256'] = release_hash
                    _require(all(evidence.get(k) == v for k, v in binding.items()), 'evidence binding mismatch')
                    source_data, source_path = read_artifact(Path(workspace_root), evidence.get('source'))
                    _require(source_path != path and source_path not in used_sources, 'source observation reused')
                    used_sources.add(source_path)
                    source = strict_json(source_data)
                    _require(all(source.get(k) == v for k, v in binding.items()), 'source binding mismatch')
                    original_data, original_path = read_artifact(Path(workspace_root), source.get('original_observation'))
                    _require(original_path not in {path, source_path} and original_path not in used_originals, 'original observation must be separate and unused')
                    used_originals.add(original_path)
                    original = strict_json(original_data)
                    _require(original.get('schema_version') == 'note-lifecycle-observation/v1'
                             and all(original.get(k) == v for k, v in binding.items()),
                             'original observation article/version/target mismatch')
                    result = original.get('result')
                    mappings = source.get('result_paths')
                    _require(isinstance(result, dict) and isinstance(mappings, dict), 'result_paths required')
                    _require(source.get('result') == result, 'source result differs from original observation')
                    for field, value in result.items():
                        if kind in {'note_save', 'note_publication'} and field in {'saved_body_sha256', 'public_body_sha256'}:
                            body_field = 'body_html' if 'body_html' in original else 'body_text'
                            text = original.get(body_field)
                            _require(_text(text), 'original body missing')
                            observed_hash = prose_sha256(text, html=body_field == 'body_html')
                            _require(observed_hash == value, 'original reader body mismatch')
                            continue
                        pointer = mappings.get(field)
                        _require(pointer == '/result/' + field, 'result field mapping cannot be changed: ' + field)
                        observed = original['result'][field]
                        _require(type(observed) is type(value) and observed == value, 'original result mismatch: ' + field)
                    if kind == 'announcement_send':
                        approval_data, _ = read_artifact(Path(workspace_root), source.get('approval_ref'))
                        approval = strict_json(approval_data)
                        _require(approval.get('actor') == 'human' and approval.get('decision') == 'approved'
                                 and _digest(result.get('payload_sha256'))
                                 and approval.get('payload_sha256') == result['payload_sha256']
                                 and all(approval.get(k) == binding[k] for k in ('article_id', 'body_sha256', 'target')),
                                 'human approval binding mismatch')
                        if release_hash is not None:
                            _require(approval.get('release_sha256') == release_hash, 'human approval release mismatch')
                    _result_check(kind, result, spec['target'], body_hash, article_id, Path(workspace_root), reader_hash)
                    verified.add(aid)
                    verified_results[aid] = result
                except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                    issue = str(exc)
                    status = 'blocked'
            if status != 'verified':
                remaining.append({'id': aid, 'kind': kind, 'stage': spec['stage'], 'status': status,
                                  'reason': issue or f'{aid}: {status}'})
        for aid in list(verified):
            if by_id[aid]['kind'] != 'announcement_send':
                continue
            ancestors = set()
            def collect_deps(key):
                for dep in by_id[key]['depends_on']:
                    if dep not in ancestors:
                        ancestors.add(dep)
                        collect_deps(dep)
            collect_deps(aid)
            drafts = [key for key in ancestors if by_id[key]['kind'] == 'announcement_draft'
                      and by_id[key].get('slot') == by_id[aid].get('slot')
                      and by_id[key]['target'] == by_id[aid]['target']]
            if not any(key in verified and verified_results[key].get('draft_sha256') ==
                       verified_results[aid].get('payload_sha256') for key in drafts):
                verified.remove(aid)
                remaining.append({'id': aid, 'kind': 'announcement_send', 'stage': by_id[aid]['stage'],
                                  'status': 'blocked', 'reason': 'sent payload differs from verified prerequisite draft'})
        # A claimed completion cannot outrun a failed prerequisite.
        for aid in list(verified):
            if any(dep not in verified for dep in by_id[aid]['depends_on']):
                errors.append(f'{aid}: prerequisite is not verified')
        for item in remaining:
            if item['id'] in required:
                errors.append(f"{item['id']}: {item['reason']}")
        outcome['current'] = remaining[0]['stage'] if remaining else 'complete'
        ready = [r['id'] for r in remaining if all(d in verified for d in by_id[r['id']]['depends_on'])]
        outcome['next'] = ready[0] if ready else None
        outcome['required_now'] = [s['id'] for s in specs if s['id'] in required]
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        errors.append(str(exc))
    outcome['ok'] = not errors
    return outcome
