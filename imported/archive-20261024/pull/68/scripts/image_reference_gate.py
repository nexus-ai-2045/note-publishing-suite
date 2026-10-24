#!/usr/bin/env python3
"""Bind image references, generation input, output and visual review; never assert adoption."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

NOTICE = "Records bind files and declared observations; JSON cannot prove model attention, visual inspection, human approval or character adoption."
STAGES = {"pre_generation", "qa", "image_edit", "pre_save", "publish"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("non-empty path required")
    path = Path(value)
    return (path if path.is_absolute() else base / path).resolve()


def parse_bytes(raw: bytes) -> dict:
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError(f"duplicate key: {key}")
            out[key] = value
        return out
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if not isinstance(data, dict):
        raise ValueError("object required")
    return data


def load(path: Path) -> dict:
    return parse_bytes(path.read_bytes())


def check(policy_path: Path | None, receipt_path: Path | None, *, stage: str = "qa", output_path: Path | None = None, article_id: str | None = None) -> dict:
    errors: list[str] = []
    hashes = {}
    captured: dict[Path, bytes] = {}

    def snapshot(path: Path) -> bytes:
        if path not in captured:
            captured[path] = path.read_bytes()
        return captured[path]

    def sha(path: Path) -> str:
        return hashlib.sha256(snapshot(path)).hexdigest()

    def load_snapshot(path: Path) -> dict:
        return parse_bytes(snapshot(path))
    result = {"status": "blocked", "errors": errors, "hashes": hashes, "notice": NOTICE}
    if stage not in STAGES:
        errors.append("invalid stage")
        return result
    if policy_path is None:
        result["status"] = "not_required"
        return result
    if stage in {"image_edit", "pre_save"} and output_path is None:
        errors.append("actual output_path is required before image editing or saving")
        return result
    try:
        policy_path = policy_path.resolve()
        policy = load_snapshot(policy_path)
        if policy.get("schema") != "image-reference-policy/v1":
            raise ValueError("invalid policy schema")
        candidate_count = policy.get("draft_candidate_count")
        if "draft_candidate_count" in policy and (type(candidate_count) is not int or candidate_count != 3):
            raise ValueError("draft_candidate_countは整数3で指定してください")
        character = policy.get("required_character_id")
        roles = policy.get("required_roles")
        if not isinstance(character, str) or not character.strip():
            raise ValueError("required_character_id required")
        if not isinstance(roles, list) or not roles or any(not isinstance(role, str) or not role.strip() for role in roles) or len(set(roles)) != len(roles):
            raise ValueError("non-empty unique required_roles required")
        manifest_path = resolve(policy.get("reference_manifest"), policy_path.parent)
        manifest = load_snapshot(manifest_path)
        rows = manifest.get("files")
        if not isinstance(rows, list) or not rows:
            raise ValueError("manifest files required")
        references = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("manifest file must be an object")
            path = resolve(row.get("path"), manifest_path.parent)
            expected = row.get("sha256")
            if path in references or sha(path) != expected:
                raise ValueError("manifest reference duplicate or changed bytes")
            references[path] = expected
        hashes.update(policy=sha(policy_path), reference_manifest=sha(manifest_path))
        if receipt_path is None:
            raise ValueError("generation receipt required")
        receipt_path = receipt_path.resolve()
        receipt = load_snapshot(receipt_path)
        if receipt.get("schema") != "image-reference-receipt/v1" or receipt.get("character_id") != character:
            raise ValueError("receipt schema or required character mismatch")
        if receipt.get("policy_sha256") != hashes["policy"] or receipt.get("reference_manifest_sha256") != hashes["reference_manifest"]:
            raise ValueError("policy or manifest hash mismatch")
        if article_id is not None and (not isinstance(article_id, str) or not article_id.strip()
                or receipt.get("article_id") != article_id):
            raise ValueError("receipt article_id mismatch")
        prompt = receipt.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or hashlib.sha256(prompt.encode()).hexdigest() != receipt.get("prompt_sha256"):
            raise ValueError("prompt hash mismatch")
        used = receipt.get("references")
        passed = receipt.get("referenced_image_paths")
        if not isinstance(used, list) or not used or not isinstance(passed, list) or not passed:
            raise ValueError("references and actual referenced_image_paths required")
        paths, found_roles = set(), set()
        for row in used:
            if not isinstance(row, dict):
                raise ValueError("reference must be an object")
            path = resolve(row.get("path"), receipt_path.parent)
            if path in paths or path not in references or row.get("sha256") != references[path]:
                raise ValueError("used reference unknown, duplicate or hash mismatch")
            role = row.get("role")
            if not isinstance(role, str) or not role.strip():
                raise ValueError("reference role required")
            paths.add(path)
            found_roles.add(role)
        passed_paths = [resolve(value, receipt_path.parent) for value in passed]
        if set(passed_paths) != paths or len(passed_paths) != len(paths):
            raise ValueError("actual referenced_image_paths differ from recorded references")
        if not set(roles).issubset(found_roles):
            raise ValueError("required reference roles missing")
        if candidate_count is not None and stage == "pre_generation":
            planned = receipt.get("planned_candidate_count")
            if type(planned) is not int or planned != candidate_count:
                raise ValueError("生成前にplanned_candidate_count=3の計画が必要です")
        if stage != "pre_generation":
            output = receipt.get("output")
            if not isinstance(output, dict):
                raise ValueError("output required")
            path = resolve(output.get("path"), receipt_path.parent)
            output_hash = sha(path)
            if not snapshot(path) or output.get("sha256") != output_hash or (output_path is not None and (output_path.resolve() != path or sha(output_path) != output_hash)):
                raise ValueError("output file or hash mismatch")
            hashes["output"] = output_hash
            if candidate_count is not None:
                unresolved = {"pending", "unknown", "todo", "tbd", "none", "null", "n/a",
                              "未確認", "未定", "保留", "確認待ち", "未決定", "未承認", "検討中"}
                def resolved_text(value):
                    return isinstance(value, str) and bool(value.strip()) and value.strip().casefold() not in unresolved

                if "early_selection" in receipt:
                    early = receipt["early_selection"]
                    if (not isinstance(early, dict) or not resolved_text(receipt.get("article_id"))
                            or early.get("article_id") != receipt["article_id"]
                            or early.get("output_sha256") != output_hash
                            or early.get("actor") != "user" or early.get("status") != "approved"
                            or not all(resolved_text(early.get(key)) for key in ("reason", "evidence_ref"))):
                        raise ValueError("途中採用には記事・選択画像hashに一致する本人承認と理由・証拠参照が必要です")
                    observed = datetime.fromisoformat(early.get("observed_at"))
                    if observed.utcoffset() is None:
                        raise ValueError("途中採用の承認日時にはtimezoneが必要です")
                else:
                    candidates = receipt.get("draft_candidates")
                    if not isinstance(candidates, list) or len(candidates) != candidate_count:
                        raise ValueError("実生成した3種類のdraft_candidatesが必要です")
                    candidate_paths, candidate_hashes, compositions = set(), set(), set()
                    for candidate in candidates:
                        if not isinstance(candidate, dict) or not resolved_text(candidate.get("composition")):
                            raise ValueError("各候補の具体的な構図説明が必要です")
                        candidate_path = resolve(candidate.get("path"), receipt_path.parent)
                        candidate_sha = sha(candidate_path)
                        composition = " ".join(candidate["composition"].split()).casefold()
                        if (not snapshot(candidate_path) or candidate.get("sha256") != candidate_sha
                                or candidate_path in candidate_paths or candidate_sha in candidate_hashes
                                or composition in compositions):
                            raise ValueError("候補ファイル・hash・構図が欠落、変更または重複しています")
                        candidate_paths.add(candidate_path)
                        candidate_hashes.add(candidate_sha)
                        compositions.add(composition)
                    if path not in candidate_paths:
                        raise ValueError("選択画像が生成候補に含まれていません")

            qa = receipt.get("visual_qa")
            if not isinstance(qa, dict) or qa.get("output_sha256") != output_hash or qa.get("status") != "pass":
                raise ValueError("visual QA must pass for the current output hash")
            if not isinstance(qa.get("reviewer"), str) or not qa["reviewer"].strip():
                raise ValueError("visual QA reviewer required")
            observations = qa.get("observations")
            if not isinstance(observations, list) or not observations:
                raise ValueError("visual QA observations required, a checkbox is insufficient")
            observed_roles = set()
            for item in observations:
                if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item[key].strip() for key in ("criterion", "observation", "reference_path")):
                    raise ValueError("visual QA needs criterion, observation and reference_path")
                observed_path = resolve(item["reference_path"], receipt_path.parent)
                if observed_path not in paths:
                    raise ValueError("visual QA reference not in generation inputs")
                observed_roles.update(row["role"] for row in used if resolve(row["path"], receipt_path.parent) == observed_path)
            if not set(roles).issubset(observed_roles):
                raise ValueError("visual QA must compare all required reference roles")
        hashes["receipt"] = sha(receipt_path)
        for path, raw in captured.items():
            if path.read_bytes() != raw:
                raise ValueError("image inputs changed during validation")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(str(exc))
    result["status"] = "ok" if not errors else "blocked"
    return result


def check_settings(settings_path: Path | None, *, stage: str = "qa", output_path: Path | None = None, article_id: str | None = None) -> dict:
    """External settings own paths; absence of a declared policy preserves generic usage."""
    if settings_path is None:
        return check(None, None, stage=stage, output_path=output_path)
    try:
        settings_path = settings_path.resolve()
        raw_settings = settings_path.read_bytes()
        settings = parse_bytes(raw_settings)
        style = settings.get("style", {})
        if not isinstance(style, dict):
            raise ValueError("style must be an object")
        profiles = style.get("article_profiles", {})
        if not isinstance(profiles, dict):
            raise ValueError("article_profiles must be an object")
        scoped = any(isinstance(profile, dict) and "image_reference_policy" in profile for profile in profiles.values())
        if scoped and (not isinstance(article_id, str) or not article_id.strip()):
            raise ValueError("article_id required for scoped image policy")
        selected = profiles.get(article_id)
        selected_scoped = isinstance(selected, dict) and "image_reference_policy" in selected
        if selected_scoped:
            image_settings = selected
        else:
            image_settings = settings
        if "image_reference_policy" not in image_settings:
            if settings_path.read_bytes() != raw_settings:
                raise ValueError("settings changed during validation")
            return check(None, None, stage=stage, output_path=output_path)
        workspace = resolve(settings.get("workspace_root"), settings_path.parent)
        policy = resolve(image_settings["image_reference_policy"], workspace)
        value = image_settings.get("image_reference_receipt")
        receipt = resolve(value, workspace) if value is not None else None
        result = check(policy, receipt, stage=stage, output_path=output_path,
                       article_id=article_id if selected_scoped else None)
        if settings_path.read_bytes() != raw_settings:
            raise ValueError("settings changed during validation")
        return result
    except (OSError, ValueError, TypeError) as exc:
        return {"status": "blocked", "errors": [str(exc)], "hashes": {}, "notice": NOTICE}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--article-id")
    parser.add_argument("--stage", choices=sorted(STAGES), default="qa")
    args = parser.parse_args()
    if args.settings is not None and (args.policy is not None or args.receipt is not None):
        parser.error("settings and explicit policy/receipt cannot be combined")
    if args.settings is None and args.policy is None:
        parser.error("--settings or --policy required")
    result = check_settings(args.settings, stage=args.stage, output_path=args.output, article_id=args.article_id) if args.settings is not None else check(args.policy, args.receipt, stage=args.stage, output_path=args.output, article_id=args.article_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["status"] == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
