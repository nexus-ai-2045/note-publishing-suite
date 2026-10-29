"""任意の外部policyで指定した公開前草稿と確認証拠を読取り専用で照合する。"""
from __future__ import annotations

import hashlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOADER_SPEC = importlib.util.spec_from_file_location(
    '_nps_loader_bootstrap', Path(__file__).with_name('nps_script_loader.py'))
if _LOADER_SPEC is None or _LOADER_SPEC.loader is None:
    raise ImportError('cannot load NPS script loader')
_LOADER_MODULE = importlib.util.module_from_spec(_LOADER_SPEC)
_LOADER_SPEC.loader.exec_module(_LOADER_MODULE)
_load_sibling_module = _LOADER_MODULE.load_script

_FEEDBACK = _load_sibling_module('note_feedback')
parse_json = _load_sibling_module('note_footer_selection').parse_json
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
POLICY_SCHEMA = 'nps-publication-drafts-policy/v1'
MANIFEST_SCHEMA = 'nps-publication-drafts/v1'
REVIEW_SCHEMA = 'nps-publication-draft-review/v1'
NOTICE = '草稿・確認証拠の版一致を検査します。意味の品質、確認者の真正性、送信許可、公開許可は保証しません。'


def validate_policy(value: Any) -> dict:
    """未設定は呼出元で区別し、宣言済みの未知policyは無効化しない。"""
    if (not isinstance(value, dict)
            or set(value) - {'schema', 'required', 'required_slots'}
            or value.get('schema') != POLICY_SCHEMA
            or type(value.get('required')) is not bool):
        raise ValueError('publication_drafts_policy_invalid')
    slots = value.get('required_slots', [])
    if (not isinstance(slots, list)
            or any(not isinstance(slot, str) or not slot.strip() for slot in slots)
            or len(slots) != len(set(slots))
            or value['required'] and not slots):
        raise ValueError('publication_drafts_required_slots_invalid')
    return {'schema': POLICY_SCHEMA, 'required': value['required'], 'required_slots': list(slots)}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check_manifest(policy: dict | None, manifest_path: Any, *, article_id: str,
                   draft_path: Path, storage_dirs: dict[str, Path],
                   base_dir: Path = Path('.'), expected_article_sha256: str | None = None) -> dict:
    """実体・確認証拠・現在の記事版だけを検査し、ファイルや台帳を更新しない。"""
    result = {'status': 'not_required', 'errors': [], 'hashes': {},
              'semantic_quality_verified': False, 'human_publication_authorized': False,
              'notice': NOTICE}
    if policy is None:
        return result
    try:
        policy = validate_policy(policy)
        if not policy['required']:
            return result
        capture: _FEEDBACK.InputCapture = ({}, {})

        def read(value: Any, owners: tuple[Path, ...], *, base: Path = base_dir) -> tuple[Path, bytes]:
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise ValueError('publication_drafts_path_missing')
            selected = Path(value)
            selected = (selected if selected.is_absolute() else base / selected).absolute()
            resolved = selected.resolve(strict=True)
            if (resolved.is_relative_to(PACKAGE_ROOT)
                    or not any(resolved.is_relative_to(owner) for owner in owners)
                    or not resolved.is_file()):
                raise ValueError('publication_drafts_path_outside_storage')
            _FEEDBACK.remember_input_path(capture, selected, resolved)
            raw = resolved.read_bytes()
            _FEEDBACK.remember_input_bytes(capture, resolved, raw)
            if not raw.strip():
                raise ValueError('publication_drafts_file_empty')
            raw.decode('utf-8')
            return resolved, raw

        drafts = (storage_dirs['drafts'],)
        review_owners = tuple(storage_dirs[key] for key in ('drafts', 'sources', 'feedback'))
        article_path, article_raw = read(draft_path, drafts)
        article_sha = _digest(article_raw)
        if expected_article_sha256 is not None and article_sha != expected_article_sha256:
            raise ValueError('publication_drafts_article_changed')
        manifest_actual, manifest_raw = read(manifest_path, drafts)
        manifest = parse_json(manifest_raw.decode('utf-8'))
        if (not isinstance(manifest, dict) or manifest.get('schema') != MANIFEST_SCHEMA
                or manifest.get('article_id') != article_id
                or manifest.get('article_draft_sha256') != article_sha):
            raise ValueError('publication_drafts_article_or_version_mismatch')
        items = manifest.get('items')
        if (not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
                or any(not isinstance(item.get('slot'), str) for item in items)):
            raise ValueError('publication_drafts_items_invalid')
        slots = [item['slot'] for item in items]
        if len(slots) != len(set(slots)) or set(slots) != set(policy['required_slots']):
            raise ValueError('publication_drafts_slots_missing_or_duplicate')
        hashes = {'manifest': _digest(manifest_raw), 'article_draft': article_sha}
        used = [article_path, manifest_actual]
        for item in items:
            path, raw = read(item.get('path'), drafts, base=manifest_actual.parent)
            if any(path.samefile(prior) for prior in used):
                raise ValueError('publication_drafts_file_alias')
            used.append(path)
            sha = _digest(raw)
            if item.get('sha256') != sha:
                raise ValueError('publication_drafts_draft_hash_mismatch')
            review = item.get('review')
            if not isinstance(review, dict):
                raise ValueError('publication_drafts_review_missing')
            review_path, review_raw = read(review.get('path'), review_owners, base=manifest_actual.parent)
            if any(review_path.samefile(prior) for prior in used):
                raise ValueError('publication_drafts_file_alias')
            used.append(review_path)
            if review.get('sha256') != _digest(review_raw):
                raise ValueError('publication_drafts_review_hash_mismatch')
            evidence = parse_json(review_raw.decode('utf-8'))
            if (not isinstance(evidence, dict) or evidence.get('schema') != REVIEW_SCHEMA
                    or evidence.get('article_id') != article_id
                    or evidence.get('article_draft_sha256') != article_sha
                    or evidence.get('slot') != item['slot']
                    or evidence.get('draft_sha256') != sha
                    or evidence.get('status') != 'confirmed'
                    or evidence.get('actor') not in {'assistant', 'user'}
                    or any(not isinstance(evidence.get(key), str) or not evidence[key].strip()
                           for key in ('reviewer_id', 'reviewed_at', 'evidence_ref', 'summary'))):
                raise ValueError('publication_drafts_review_unconfirmed_or_stale')
            stamp = datetime.fromisoformat(evidence['reviewed_at'].replace('Z', '+00:00'))
            if stamp.utcoffset() is None or stamp > datetime.now(timezone.utc):
                raise ValueError('publication_drafts_review_time_invalid')
            hashes['draft:' + item['slot']] = sha
            hashes['review:' + item['slot']] = _digest(review_raw)
        _FEEDBACK.check_input_capture(capture)
        result.update(status='ok', hashes=hashes, checked_slots=slots,
                      files_verified=True, review_receipts_matched=True)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        # Do not leak workspace paths or private draft contents into diagnostic output.
        result.update(status='blocked', errors=['publication_drafts_missing_invalid_or_stale'])
    return result
