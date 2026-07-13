# 変更履歴

このファイルは `note-publishing-suite` パッケージの版管理正本。
GitHub リリースやタグは別の公開操作として扱い、ここにはパッケージ内の
変更内容と検証範囲だけを記録する。

## 0.2.7

日付: 2026-06-22

変更:
- package version の自動採番スクリプトを追加し、README / rendered HTML / CHANGELOG の版管理メタデータを一括更新できるようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/check_version_bump.py`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.6

日付: 2026-06-22

変更:
- root `AGENTS.md` を追加し、公開、広域共有、repository visibility 変更の
  人間レビュー必須ゲートを repository 入口に明記した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- GitHub Actions `package-smoke`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.5

日付: 2026-06-22

変更:
- Windows / PowerShell 環境で `sh` が無い場合でも、
  standalone clone verifier lane が `scripts/verify_public_package.ps1 -Json`
  に fallback して動くようにした。
- standalone clone fixture の統合テストも、`sh` がある環境では
  `verify_public_package.sh`、無い環境では PowerShell verifier を使うようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py tests/test_review_draft_cli.py -q`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.5

日付: 2026-07-13

変更:
- `note-publishing-suite` の独立 repo worktree を復旧し、Claude Code pointer の
  package root を独立正本へ再インストールした。
- 2026-07-13 の Note editor 実測として、`text/html` paste、hidden WebView、
  DOM selection の tick、連続画像 separator、CDN 取りこぼしを正本へ反映した。
- `cmux_dom_file_paste` を明示確認必須の画像経路として追加し、OS clipboard、
  Cookie、note API を使わない browser-scoped route に限定した。
- `scripts/skill_pointer_check.py`、回帰テスト、CI、pre-commit hook template を追加し、
  正本 pointer の消失を fail-closed で検知するようにした。

検証:
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/skill_pointer_check.py --installed-root "$HOME/.claude/skills" --json`
- `python3 scripts/note_image_upload_boundary_check.py --json`

公開境界:
- Note 投稿、下書き保存、予約投稿、SNS 共有、外部告知は未実行。
- git push、GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.4

日付: 2026-06-20

変更:
- `scripts/review_draft.py` を追加し、`build-context-card` と
  `review-draft` の CLI flow を実装した。
- `review-draft` は `review-intent` ではなく、`build_context_card` /
  `review_draft` 経路で verdict、reason_codes、confirmation_questions、
  context_card を返す契約にした。
- `content/drafts/sample-note-prepublish-fixture.md` を使う fixture-backed
  local review を追加し、editor fixture は公開候補として進めず blocked にする。
- Mac / Linux 向けの `scripts/verify_public_package.sh` を primary verifier にし、
  PowerShell verifier は Windows / PowerShell equivalent として残した。
- `data/note_editor_prepublish_observation.fixture.json` を追加し、
  `<observation.json>` placeholder なしで公開前観測 checker を実行できるようにした。

検証:
- `sh scripts/verify_public_package.sh`
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json`

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
  GitHub identity guard 検証レーンを追加し、さらに standalone clone fixture 側から
  verifier 自身を再実行して、公開操作なしで両形態を確認できるようにした。
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

## 0.2.3

日付: 2026-06-18

変更:
- package version と README / CHANGELOG の整合性を公開検証の必須条件にした。
- verifier の実行要件を PowerShell、Python、git として明記し、
  Python なしで動くように読める誤保証を禁止語として検査するようにした。
- standalone clone fixture から verifier 自身を再実行し、単独 repo 形態でも
  公開操作なしで検証できることを確認するようにした。
- `scripts/provenance_label_check.py` を追加し、
  `source_pack_locked_with_user_speech_priority` の draft で `user-said`、
  `external-fact`、`assistant-organized`、`hold` の境界を検査できるようにした。
- Caramel 完全解説風の draft fixture を追加し、本人発言優先構成の
  provenance label 回帰ケースにした。

検証:
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_note_image_upload_boundary.py tests/test_note_editor_prepublish_verify.py`
- `python scripts/provenance_label_check.py content/drafts/caramel-provenance-label-fixture.md --json`

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
