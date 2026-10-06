# 変更履歴

このファイルは `note-publishing-suite` パッケージの版管理正本。
GitHub リリースやタグは別の公開操作として扱い、ここにはパッケージ内の
変更内容と検証範囲だけを記録する。

## 0.2.42

日付: 2026-10-06

変更:
- 初めて使う人がローカルだけで主要な流れと公開直前の停止位置を確かめる受け入れテスト手順書 `USER_TEST.md`（4ケース）を追加し、README と package.yaml から参照できるようにした。受け入れテストの合格は Note 公開の承認ではないことを明記した。
- 公開パッケージ検証スクリプトで、ローカル下書きQAの証跡を一時ファイルへ出力して終了後に削除し、検証後もリポジトリ内の追跡ファイルが変わらないことをテストで確かめるようにした。
- CHANGELOG の版の並びを新しい順に直し、その順序を確かめるテストを追加した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `sh scripts/verify_public_package.sh`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.41

日付: 2026-10-06

変更:
- macOSのクリップボード同意ファイル検査で、ACL属性が存在しないことを同じファイル記述子で確かめてから許可するようにした。ACL非対応や判定失敗は従来どおり拒否する。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/check_version_bump.py`（基準: `origin/main`）
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.40

日付: 2026-10-06

変更:
- 内部ブラウザのローカル証跡による公開snapshot／台帳更新を追加。dry-runを既定にし、記事IDの冪等更新と未知field保持、二台帳の中断復旧を実装。
- 現在版の承認一覧、目次・末尾カードの独立採否、外部の記事別feedback読戻しを追加。
- タグ候補と選択済みタグを区別し、同時変更を検出する純粋事前照合と回帰検証を追加。
- 利用者固有の編集CLI・個人設定・台帳・実記事の証跡は配布へ含めない。
- 原稿・証跡・snapshotと台帳・journalのalias衝突を拒否し、SHA-256形式検査を保持。

検証:
- 全体実行では既存clipboardのDarwin ACL検査17件が失敗。今回の配送差分に含まない環境依存の未解決事項として扱う。
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 -m pytest scripts/test_skill_integration.py tests --ignore=tests/test_clipboard_bridge.py -q`
- `sh scripts/verify_public_package.sh --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.39

日付: 2026-10-05

変更:
- 記事制作の3経路と版ごとの人間承認・外部設定読戻しcheckerを追加
- 著者性APIからの呼出しにも原資料と短縮予算の検査を適用

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.38

日付: 2026-10-02

変更:
- レビュー表示が `--!>` で閉じた由来コメントを認識し（検査器と同じ）、先頭の BOM があっても frontmatter を外すようにした。未知の種類は色なしの塊にする。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.37

日付: 2026-10-02

変更:
- 通常本文の空行を段落境界、段落内の原稿改行をbrへ変換。期待・観測soft-break配列の欠落、型不正、段落別不一致を改行gateで拒否し、外部記事カードのDOM検査契約を同期。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`: 364件合格、10件skip、18件失敗。ACL17件は変更前にも再現。standalone fixtureの生成物drift1件は単独再検査で合格。
- `python3 -m pytest tests/test_note_linebreak_gate.py tests/test_note_virtual_preview.py tests/test_note_editor_prepublish_verify.py tests/test_docs_sync_check.py -q: 92件合格。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.36

日付: 2026-10-02

変更:
- 内部ブラウザ指定を最初の接続確認から保持し、内部Playwrightと外部MCPを区別。内部限定時のChrome切替質問を候補から除外。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python3 scripts/note_editor_pdca_failure_check.py --json`
- `独立担当による操作手順差分レビュー。ブラウザ実行による再発防止は未実測。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.35

日付: 2026-10-02

変更:
- Note読書用プレビューのMarkdown画像を既存の安全な画像処理で描画。相対パスとHTTPS画像、代替テキストの保護、リンク誤変換を検証。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `画像と装飾の回帰テストおよび文書同期テスト: 34件合格。全体テスト: 349件合格、10件skip、macOSクリップボード権限検査17件失敗は変更前にも再現。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.34

日付: 2026-10-02

変更:
- Note読書用プレビューの背景を白にし、light表示を明示。公開ページCSSの再照合値と近似の限界を記録。
- 制作スキルで、読書表示・由来レビュー・編集診断の入口を区別。

検証:
- `python3 -m pytest tests/test_note_virtual_preview.py -q`: 12件PASS。
- 作成担当セルフレビューと主担当の独立差分レビュー: 指摘なし。
- GitHub CIの初回で版更新不足とdocs-sync不足を検出し、既存の版管理契約に従い修正。

公開境界:
- Note投稿、SNS共有、GitHubリリース・タグ作成、公開範囲変更は未実行。

## 0.2.33

日付: 2026-10-02

変更:
- 読書用プレビューから設定と内部コメントと診断枠を除外し、編集診断を --diagnostics に分離。由来レビューとQA手順を統一。本人確認と保留の停止条件は維持。
- 既存の設定解析を再利用し、コメント終端・空設定・リンクの二重エスケープを修正。原稿非変更を含む回帰テストを追加。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_note_virtual_preview.py tests/test_provenance_draft_review.py tests/test_docs_sync_check.py -q`
- `独立レビュー完了。全体テストのmacOSクリップボード権限検査17失敗は変更前にも再現。`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.32

日付: 2026-10-02

変更:
- `note_preview.py` が下書き冒頭の frontmatter（先頭の `---` 行から次の `---` 行まで）を本文から外すように修正。設定の行が段落・箇条書きとして出ていた。本文中の区切り線は従来どおり。
- `--review-provenance` の表示を、由来ごとの色の塊（本人=緑、AIのつなぎ=黄、資料の事実=青、保留=赤）に変更。見出しは塊の外に出し、種類ごとの件数と本文の字数（空白・リンク先・見出し・保留を除く）を上に出す。1文1行の改行は `<br>` で残し、リンクは別タブで開く。ダークモードに対応。
- リンク先 URL の `&` などが二重に escape されて開けなかった問題を修正。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `sh scripts/verify_public_package.sh`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.31

日付: 2026-09-29

変更:
- 記事ごとの末尾選定計画とDOM順snapshotの照合を実入口へ接続。空計画・未レビュー・不一致・手動境界を停止し、live観測や公開承認とは分ける。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.30

日付: 2026-09-24

変更:
- 開発保証スイート（repo-preflight + ai-ratchet-gate）を ai-round-table と同じ吸収パターンで追加。workflow_dispatch のみ。inspection ロジックは持ち込まない。
- PREFLIGHT.md・.repo-preflight-consistency.json・.ai-ratchet-gate/baseline.txt・requirements-tools.txt・repository-guarantees.yml を追加。

検証:
- `python -m pip install --require-hashes -r requirements-tools.txt && python -m ai_ratchet_gate --repo .`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.29

日付: 2026-09-21

変更:
- Noteエディタ作業の記事ごとPDCA cycle受領JSONを scripts/note_editor_pdca_cycle_check.py で検査する経路を追加した。
- 1 action・前後DOM証跡・非公開・routeあたり最大2回試行の契約を package.yaml / note-editor-ops / PDCA orchestration に配線した。
- cycle受領検査で top-level state と終端 cycle の整合、および証跡の非空文字列/非負整数型を fail-closed にした。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest -q tests/test_note_editor_pdca_cycle_check.py`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `VERSION_BUMP_BASE_REF=origin/main python scripts/check_version_bump.py`
- `python scripts/note_editor_pdca_failure_check.py --json`

公開境界:
- 人間承認後に公開PR #27を更新。マージ・リリース・タグ作成は未実行。
- Note 投稿、予約投稿、SNS 共有、外部告知、リポジトリ公開範囲変更は未実行。
- PR #27 のタイトル・本文はリポジトリ契約どおり日本語へ書き換える必要がある（エージェント権限では編集不可）。推奨タイトル: 「Noteエディタ作業向けの検証済みPDCA cycle受領検査を追加」。

日付: 2026-09-13

変更:
- OSクリップボードの全入口に利用者・端末・期限・操作範囲の事前同意ゲートを追加。共同利用者へ承認を継承せず、未確認なら副作用前に停止する。
- 画像upload境界の文書・policy・checkerを条件付き経路に統一。
- 同意記録の保存先・ファイルの所有者と権限を検査し、別OS利用者による記録の差し替えを防ぐ。

検証:
- `python -m pytest -q`（Windows、保存権限修正後: 296 passed / 16 skipped）
- `python3 -m pytest tests/test_clipboard_bridge.py -q`（Linux: 123 passed / Mac専用2 skipped）
- `python scripts/note_image_upload_boundary_check.py --json`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `python scripts/package_consistency_check.py --json`
- `python scripts/check_version_bump.py`（Windowsでは `PYTHONUTF8=1`）
- Macの実クリップボード操作は未検証。別途利用者が実機確認する。

公開境界:
- 人間承認後に公開PR #26を作成。マージ・リリース・タグ作成は未実行。
- Note 投稿、予約投稿、SNS共有、外部告知、同意の代理発行は未実行。

## 0.2.27

日付: 2026-09-13

変更:
- 3部門設計ドキュメント、クリップボード橋渡し、仮想noteプレビュー移植、口述モードを追加
- package.yaml に clipboard_bridge / note_virtual_preview を宣言

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/docs_sync_check.py --base-ref origin/main --review-file /tmp/nps-doc-review.txt`
- `python scripts/package_consistency_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.26

日付: 2026-08-28

変更:
- サンプル下書き1本を着想→QA→公開直前停止まで通し、run_local_draft_qa_proof.py の証跡を再生成した（external_actions_performed: []）
- axis-2 の fixture パッケージ証跡を更新。実記事 live / エディタ引き継ぎは人間作業のまま

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/run_local_draft_qa_proof.py --json`
- `python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py tests/test_topic_status_check.py -q`
- `python scripts/topic_status_check.py --json`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.25

日付: 2026-08-25

変更:
- repo-preflight 整合性ゲートを shadow モードで採用

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `consistency_gate.py --repo . --json => status=pass`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.24

日付: 2026-08-06

変更:
- PR で package-smoke が確実に付くよう CI を強化し、NPS 運用スモーク手順を CONTRIBUTING に固定した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest scripts/test_skill_integration.py -q; python scripts/docs_sync_check.py --base-ref origin/main`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.23

日付: 2026-08-06

変更:
- README を動画なし運用を正面にし、デモ動画は任意枠に下げた。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/render_readme.py; python -m pytest scripts/test_skill_integration.py -q`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.22

日付: 2026-08-06

変更:
- NPSとして使う導線をREADMEに整理し、使い方動画の置き場 assets/demo を追加した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python scripts/render_readme.py; python -m pytest scripts/test_skill_integration.py tests/test_topic_status_check.py -q; pwsh -NoProfile -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- GitHub リリース作成、タグ作成、リポジトリ公開範囲変更は未実行。

## 0.2.21

日付: 2026-08-06

変更:
- PUBLIC_READY を v0.2.20 Release 反映済みの状態へ更新し、外部追加スキャナ候補（旧 CHINJU 記載）を採用しない方針に整理した。
- 話題統合台帳の停止線と worktree 方針を現状に合わせ、status 語彙検査を現行軸に追随した。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `python -m pytest tests/test_topic_status_check.py -q`
- `python scripts/topic_status_check.py --json`
- `python scripts/check_version_bump.py`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`

公開境界:
- Note 投稿、予約投稿、SNS 共有、外部告知は未実行。
- 追加の GitHub リリース作成、tag 作成、リポジトリ公開範囲変更は未実行。

## 0.2.20

日付: 2026-08-06

変更:
- 問答・著者性・短縮防止・改行・図版・Browser復旧ゲートとWindows Codex配布経路を追加した。
- 問答packet APIの質問数を1〜5件へ制限し、dirty worktreeにだけ残っていた回帰テストを正規候補へ回収した。
- Browser復旧はread-only計画専用にし、自己申告JSONによるprocess終了機能を公開packageから除外した。
- Linuxの通常テストとWindows installer smokeをCIで分離し、既存のpointer検査と公開package verifierを再利用した。
- 初回PR CIで検出したpointer path終端の部分一致と、Windows cloneの生成HTML改行driftを回帰テスト付きで修正した。
- PDCA failure ledger (`data/note_editor_pdca_failure_patterns.json`) と docs 配線を回収し、default path の運用保証テストを追加した。
- 話題統合台帳 (`references/topic-consolidation-ledger.md`) と `scripts/topic_status_check.py` で、ローカル話題の chat 化と fixture TODO 混同を止めた。
- issue-drafts の吸収済み課題 (1〜3 / 埋め込み制約) を ledger と揃えた。

検証:
- `python -m pytest scripts/test_skill_integration.py tests -q`
- `pwsh -NoProfile -File scripts/verify_public_package.ps1`
- `python scripts/docs_sync_check.py --base-ref origin/main`
- `python scripts/package_consistency_check.py --json`
- `python scripts/note_editor_pdca_failure_check.py --json`
- `python scripts/topic_status_check.py --json`
- `python -m pytest tests/test_note_interview_packet.py tests/test_note_browser_transport_recovery.py tests/test_windows_skill_installer.py tests/test_note_editor_pdca_failure_check.py tests/test_topic_status_check.py -q`

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
