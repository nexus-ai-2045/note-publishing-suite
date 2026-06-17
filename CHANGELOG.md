# 変更履歴

このファイルは `note-publishing-suite` パッケージの版管理正本。
GitHub リリースやタグは別の公開操作として扱い、ここにはパッケージ内の
変更内容と検証範囲だけを記録する。

## Unreleased

変更:
- 未定。

検証:
- 未実行。

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.2

日付: 2026-06-17

変更:
- Note 公開記事の本文取得補助として `scripts/fetch_note_body.js` を追加。
- Playwright の local / `platform/` fallback 読み込みを public package 用文言に整えた。
- README、`package.yaml`、公開検証器、統合テストへ script 契約を追加。

検証:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python scripts/provenance_leak_check.py --scope changed --json`
- `python scripts/check_version_bump.py`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.1

日付: 2026-06-17

変更:
- GitHub identity guard のユーザー固有 denylist を
  `data/github_identity_guard_policy.local.json` に分離し、公開パッケージには
  合成例の `data/github_identity_guard_policy.example.json` だけを含めるようにした。
- identity leak の回帰テストを、一時 local policy と一時 fixture ファイルで
  検出する形に戻した。
- Note エディタ公開手前の観測 JSON を検査する
  `scripts/note_editor_prepublish_verify.py` を追加。
- TOP 画像、目次、フッター埋め込み、マガジン、タグ重複、記事タイプ、
  最終投稿ボタン未操作を公開手前 QA として明示。
- in-app Browser の URL 制約、画像アップロード不可、リンクカード誤配置、
  タグ重複の停止線を editor / ops スキルへ反映。
- `scripts/verify_public_package.ps1` に embedded copy と standalone clone fixture の
  GitHub identity guard 検証レーンを追加し、公開操作なしで両形態を確認できるようにした。
- PR でパッケージ実体が変わった場合に、`package.yaml` の semver が
  base branch より上がっていることを確認する
  `scripts/check_version_bump.py` を追加。
- 採番検査を `0.2.0` 固定値ではなく、`package.yaml`、README、
  CHANGELOG の整合性と base branch からの増分確認に変更。

検証:
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py`
- `python scripts/github_identity_guard.py --json`
- `python scripts/github_identity_guard.py --policy data/github_identity_guard_policy.local.json --json`
- `python scripts/note_editor_prepublish_verify.py <observation.json> --json`
- `python scripts/check_version_bump.py`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.0

日付: 2026-06-16

変更:
- 公開ゲート、Note エディタ境界、保証ラチェット、根拠設計の運用文書を強化。
- `scripts/provenance_leak_check.py` を追加し、ローカルパス、実行時メモリ、
  非公開リポジトリ名、出典外の運用文字列を PR 前に検出できるようにした。
- ユーザー固有の denylist を
  `data/provenance_leak_policy.local.json` に分離し、公開パッケージへ直書きしない
  ルールを追加。
- 実記事下書きを契約テストの必須検査材料から外し、
  `content/drafts/sample-note-prepublish-fixture.md` を QA 確認の正規検査材料にした。
- `data/post_publish_check_results.jsonl` の確認結果を版管理対象として更新。

検証:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python scripts/provenance_leak_check.py --scope all --json`
- `python scripts/note_image_upload_boundary_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リポジトリ公開範囲の変更、GitHub リリース作成、タグ作成は未実行。

## 0.1.2

前版:
- Note 投稿一気通貫の親スキル、子スキル、README、ROADMAP、公開準備
  検証を持つ公開パッケージ基準線。
