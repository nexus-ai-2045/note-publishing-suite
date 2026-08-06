# 変更履歴

このファイルは `note-publishing-suite` パッケージの版管理正本。
GitHub リリースやタグは別の公開操作として扱い、ここにはパッケージ内の
変更内容と検証範囲だけを記録する。

## 0.2.20

日付: 2026-08-06

変更:
- 問答・著者性・短縮防止・改行・図版・Browser復旧ゲートとWindows Codex配布経路を追加した。
- 問答packet APIの質問数を1〜5件へ制限し、dirty worktreeにだけ残っていた回帰テストを正規候補へ回収した。
- Browser復旧はread-only計画専用にし、自己申告JSONによるprocess終了機能を公開packageから除外した。
- Linuxの通常テストとWindows installer smokeをCIで分離し、既存のpointer検査と公開package verifierを再利用した。
- 初回PR CIで検出したpointer path終端の部分一致と、Windows cloneの生成HTML改行driftを回帰テスト付きで修正した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `python scripts/package_consistency_check.py --json`
- `python -m pytest tests/test_note_interview_packet.py tests/test_note_browser_transport_recovery.py tests/test_windows_skill_installer.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.19

日付: 2026-08-05

変更:
- プロジェクト正本境界をPROJECT_SSOT.mdへ集約し、内部設計文書を公開packageから分離した。根拠ラベル対応の下書きレビュー経路を取り込んだ。
- 版はpatchに留める。`0.3.0`はrelease判断と同時に別レビューで扱う。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.18

日付: 2026-08-05

変更:
- README冒頭に公開停止線を示すワークフロー図を追加。
- ローカルREADMEレンダラーへ安全な画像表示を追加。

検証:
- `python3 -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.17

日付: 2026-08-05

変更:
- `package.yaml`にドキュメント同期契約を追加した。
- 生成物差分、関連文書レビュー漏れ、必須文書欠損をread-onlyで検出するcheckerとPR workflowを追加した。
- CI失敗時に検査JSONと生成物patchをartifactとして取得できるようにした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- CI権限は`contents: read`。commit、push、PR編集は行わない。
- Note投稿、予約投稿、SNS共有、外部告知、GitHub release、tag、repository visibility変更は未実行。

## 0.2.16

日付: 2026-08-05

変更:
- READMEの視覚的な階層と折りたたみ表示を改善

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `README renderer contract tests`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.15

日付: 2026-08-05

変更:
- 内部のドキュメント同期設計を公開パッケージからProjects側の設計正本へ移し、パッケージには実装済みの契約だけを置く境界へ修正した。
- 0.2.14のREADME改善と0.2.13のGitHub公開名義修正は維持した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.14

日付: 2026-08-05

変更:
- README の初回導線を短く再構成

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `README contract tests`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.13

日付: 2026-08-04

変更:
- GitHubの非公開メール保護と両立するよう、公開commitの正規名義をnexus_aiのnoreplyアドレスへ更新した。

検証:
- `python -m pytest scripts/test_skill_integration.py -q`（34件）
- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`（265項目）
- `public-readiness readiness_scan.py`（人間レビュー前の停止条件を確認）

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.11

日付: 2026-07-16

変更:
- Note editorのBrowser能力表を読み取り、入力、file upload、手動操作に分けて整理した。
- 別note、tab、Browser surface、accountの切替、または現在の会話で未承認のread-onlyからwriteへの変更前にユーザー確認を必須化した。
- 能力非対応は再試行0回、同一対象の接続・DOM状態ズレは1回までとし、fallback順を固定した。

検証:
- 人間レビュー前にpackage contract testとpublic package verificationを実行する。

公開境界:
- Note投稿、予約投稿、SNS共有、外部告知は未実行。
- package変更はcommit、pushし、Draft PRとして人間レビューへ提出した。GitHubリリース、tag作成は未実行。

## 0.2.10

日付: 2026-07-16

変更:
- `post_publish.py --ledger-dir`でworkspace固有のprivate台帳を注入可能にした。
- draft ledgerを追記ではなく一意な公開状態遷移として更新するようにした。
- 公開本文snapshot、SHA-256、公開版との差分、見出し画像確認をledgerへ記録可能にした。
- `note_diff_check.py --snapshot-out`で公開本文snapshotとSHA-256を同時に生成可能にした。

検証:
- 人間レビュー前に実行し、結果をレビューpacketへ記録する。

公開境界:
- Note投稿、予約投稿、SNS共有、外部告知は未実行。
- commit、push、PR、GitHubリリース、tag作成は人間レビュー後まで未実行。

## 0.2.9

日付: 2026-07-14

変更:
- READMEの初見導線とHTMLレンダリングを改善

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pytest 72 passed / public package 31 checks passed`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

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

## 0.2.8

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
