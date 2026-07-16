---
title: Note Publishing Suite README
type: スキルパッケージREADME
status: active
created: 2026-06-08
publication_gate: human_review_required
---

# Note Publishing Suite

ローカル素材から Note の下書きを作り、検査し、エディタへ反映するための
Codex 向けパッケージです。**公開・予約投稿・SNS 共有は自動で行わず、
必ず公開直前で止まります。**

パッケージ版: `0.2.10`

## できること

| できる | 自動では行わない |
| --- | --- |
| 指定したローカル素材から記事候補と下書きを作る | 指定外のフォルダや private URL を読む |
| プレビュー、投稿前検査、根拠ラベル確認を行う | 記事内容が正しいと断定する |
| Note エディタへ反映し、下書き保存まで進める | 公開、予約投稿、SNS 共有、外部告知 |
| 公開後の確認内容を台帳更新案にする | PV、SEO、おすすめ掲載などの成果を保証する |

Note 公開、予約投稿、SNS 共有、リポジトリ公開範囲変更には、
現在の会話で対象と操作を特定した人間レビューと明示承認が必要です。

## 3分で始める

必要なものは POSIX sh、Python、git です。

```bash
git clone https://github.com/nexus-ai-2045/note-publishing-suite.git
cd note-publishing-suite
sh scripts/verify_public_package.sh
```

Windows で POSIX sh がない場合は、PowerShell verifier を使います。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

`-ExecutionPolicy Bypass` はこの PowerShell プロセスだけに適用され、
端末の永続設定は変更しません。実行前にスクリプトの内容を確認してください。

この verifier は Python と git も使って各 checker を実行するため、
どちらの環境でも先に利用可能であることを確認してください。
検証は公開操作を行わず、`embedded copy` と `standalone clone` の
両方でパッケージ契約を確認します。

## 基本ワークフロー

```text
素材を指定 → 記事候補 → 下書き → ローカル検査 → Note 下書き保存 → 公開直前で停止
```

| 段階 | すること | 主な入口 |
| --- | --- | --- |
| 1. idea | 読んでよい素材から記事候補を出す | `skills/note-idea-intake/SKILL.md` |
| 2. draft | 根拠と構成を分けて下書きを作る | `skills/note-draft-production/SKILL.md` |
| 3. qa | プレビュー、投稿前検査、根拠確認を行う | `skills/note-prepublish-qa/SKILL.md` |
| 4. editor | Note エディタへ反映し、下書き保存まで確認する | `skills/note-editor-prepublish/SKILL.md` |
| 5. gate | 公開・投稿・予約確定ボタンの手前で止める | `skills/note-publication-gate/SKILL.md` |
| 6. ledger | 公開後にだけ台帳更新案を作る | `skills/note-postpublish-ledger/SKILL.md` |

固定の `ネタ帳.md` はありません。最初にユーザーが指定した
`読んでよい素材フォルダ` だけを入力として扱います。

## 目的別ナビ

| 目的 | 最初に読むもの |
| --- | --- |
| 全体像を知りたい | この README の「基本ワークフロー」と「安全設計」 |
| 今後の計画を知りたい | [ROADMAP.md](ROADMAP.md) |
| Codex から使いたい | [SKILL.md](SKILL.md) |
| 機械可読の契約を確認したい | [package.yaml](package.yaml) |
| 公開前の準備を確認したい | [PUBLIC_READY.md](PUBLIC_READY.md) / [PUBLIC_RELEASE_CHECKLIST.md](PUBLIC_RELEASE_CHECKLIST.md) |
| セキュリティ方針を確認したい | [SECURITY.md](SECURITY.md) |
| 版ごとの差分を知りたい | [CHANGELOG.md](CHANGELOG.md) |

## 安全設計

### 根拠と構成を混ぜない

記事制作の材料を次の単位に分けます。

| 単位 | 役割 | 事実根拠にできるか |
| --- | --- | --- |
| `source_database` | 最初に読んでよい材料 | はい |
| `source_pack` | 記事単位に切り出した根拠 | はい |
| `series_plot` / `article_plot` | 連載・記事の展開案 | いいえ |
| `skeleton` | 見出しと流れの骨格 | いいえ |
| `wall_bang` | 壁打ち、問い、言い回し候補 | いいえ |
| `editor_fixture` | Note エディタ操作の検証用記事 | いいえ |

詳しい契約は
`references/note-article-provenance-design.md` を参照してください。
`production_candidate` と `editor_fixture` は混ぜません。

### 公開直前で必ず止める

次のどれかに当てはまる場合は公開操作へ進みません。

- 対象記事、対象操作、公開方式のいずれかが `Unknown`。
- QA、画像権利、秘密情報除外、内部メモ除外が未確認。
- 現在の会話で、対象記事と操作を特定した明示承認がない。
- Note エディタや画像アップロードの状態を実測確認できない。

「公開して」「投稿して」だけでは承認として扱いません。

### 秘密情報と個人情報を残さない

- PR 前に `scripts/provenance_leak_check.py --scope changed` を実行します。
- ユーザー固有 denylist は gitignored の
  `data/provenance_leak_policy.local.json` に置き、公開パッケージへ直書きしない設計です。
- GitHub account、email、private owner の denylist は
  `data/github_identity_guard_policy.local.json` に置きます。
- 公開リポジトリには `data/github_identity_guard_policy.example.json` だけを含めます。
- credential、Cookie、非公開 URL、公開・送信権限を worker に渡しません。

### 本人発言、外部事実、AI の整理を分ける

`source_pack_locked_with_user_speech_priority` の下書きでは、次を実行します。

```bash
python scripts/provenance_label_check.py <draft.md> --json
```

`user-said`、`external-fact`、`assistant-organized`、`hold` の境界を確認し、
本人の発言と AI の構成整理を混ぜません。

## Note エディタで扱う範囲

接続・確認できる場合に限り、タイトル、本文、見出し、リンク、画像、タグ、
マガジン、公開範囲の反映または確認を行います。

- 低レベル操作は `skills/note-editor-ops/SKILL.md` を使います。
- 公式機能とローカル観測の区別は
  `references/note-editor-capability-inventory.md` で確認します。
- 操作は `references/note-editor-pdca-orchestration.md` に沿って
  1 cycle / 1 action で進めます。
- 埋め込み、目次、Shift+Enter の実測境界は
  `references/note-editor-live-constraint-boundaries.md` を参照します。
- 公式ノウハウは `note-official-guidance-intake` で一次情報化し、
  未確認を公式扱いしません。
- 実画面の制約は `note-editor-constraint-debug` で確認します。
- 画像アップロードの停止線は
  `references/note-image-upload-automation-boundary.md` と
  `scripts/note_image_upload_boundary_check.py` で確認します。

リンクカードは URL を単独行で入力し、その行末で Enter を押します。
成功は表示だけでなく `figure[data-src]` などの DOM で確認し、`href` だけが
残る場合は通常リンクとして扱います。固定座標に依存せず、同期しない場合は
手動境界へ切り替えます。下書き保存までで止まり、公開・投稿・予約確定ボタンは
押しません。

画像アップロードの完全自動化、Note ログイン、常時接続成功は保証しません。

## 主なファイル

| 場所 | 役割 |
| --- | --- |
| `SKILL.md` | 親スキル。全体ゲートと子スキルのルーティング |
| `package.yaml` | 入口、ワークフロー、検証コマンドの機械可読契約 |
| `skills/` | idea / draft / qa / editor / gate / ledger の実行手順 |
| `references/` | Note エディタ制約、出典設計、画像アップロード境界 |
| `scripts/` | ローカル QA、検査器、台帳更新ツール |
| `tests/` | パッケージ契約と停止線の回帰テスト |
| `data/` | 初期台帳、fixture、ローカル evidence |
| `content/` | 下書きと画像素材 |
| `published/` | 公開後の記録 |

主要なローカルツール:

- `scripts/note_preview.py`: Markdown 下書きのローカルプレビュー。
- `scripts/pre_publish_check.py`: シークレット候補、内部メモ、未確認語の検出。
- `scripts/note_fact_check.py`: 要確認の主張を抽出。外部ファクトチェックはしません。
- `scripts/note_diff_check.py`: 指定された Note/public URL の本文差分確認。`--snapshot-out` で公開本文とSHA-256をローカル保存できます。
- `scripts/fetch_note_body.js`: Playwright で Note 公開記事の本文を取得。
- `scripts/review_draft.py`: `build-context-card` と `review-draft` を提供。
- `scripts/run_local_draft_qa_proof.py`: 公開前で止まるローカル QA 証跡を作成。
- `scripts/post_publish.py`: 既定はドライラン。`--write-ledger` 指定時だけ台帳更新。`--ledger-dir` でpackage外のprivate台帳を指定でき、同じdraftの状態遷移は一意に更新します。
- `scripts/engagement_tracker.py`: ローカル台帳件数だけを報告。
- `scripts/bump_package_version.py`: patch / minor / major を自動採番。
- `scripts/check_version_bump.py`: パッケージ実体変更時の version bump を確認。
- `scripts/skill_pointer_check.py`: スキル参照先の実在を確認。

## 開発者向けの確認

README の整形 HTML を更新します。

```bash
python scripts/render_readme.py
```

公開前検査器と重点テストを個別に実行する場合:

```bash
python scripts/provenance_leak_check.py --scope changed
python scripts/provenance_label_check.py <draft.md> --json
python scripts/review_draft.py build-context-card content/drafts/sample-note-prepublish-fixture.md --json
python scripts/review_draft.py review-draft content/drafts/sample-note-prepublish-fixture.md --json
python scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json
python scripts/run_local_draft_qa_proof.py --json
python scripts/japanese_closeout_language_check.py --json
python scripts/note_image_upload_boundary_check.py --json
python -m pytest scripts/test_skill_integration.py tests
```

クリーン環境では、まず次の包括検証を使ってください。

```bash
sh scripts/verify_public_package.sh
```

`verify:local` の基準は、公開操作なしでパッケージ構成、安全境界、
README 表示、公開前停止線を確認できることです。

日本語運用中に PR / GitHub / CLI の状態語を英語のまま報告した場合は、
文章ミスではなく出力ゲートの構造バグとして扱います。
`ready for review` は下書き解除済み、`open PR` は未マージPR、
`MERGED` はマージ済み、`mergeable` はマージ可能として報告します。
コマンド、ファイルパス、URL、SHA、パッケージ識別子は原文のまま扱います。

## 保証ラチェット

Note エディタで見つかった失敗や手動境界は、その場限りにしません。

- 原因、復旧方法、次回の禁止事項を短く残す。
- 再発防止できるものは検査器、契約テスト、子スキルへ落とす。
- 検査器を追加したら、fixture または実記事候補で結果を確認する。
- UI 状態に依存するものは、無理に自動化せず手動境界として残す。

## よくある質問

### ZIP は別で必要？

不要です。通常は repository を clone するか、GitHub の Download ZIP を使います。
ただし、clone や ZIP 取得だけで Codex に自動インストールされるわけではありません。

### 勝手な作文をしない？

指定素材だけを読み、根拠が見つからない主張は確認対象として残します。
文章化は行うため完全な作文ゼロではありませんが、事実、推定、意見を分け、
公開前 QA と人間レビューで止めます。

### script は外部送信する？

基本しません。`note_preview.py`、`pre_publish_check.py`、
`note_fact_check.py`、`engagement_tracker.py` はローカル処理です。
`note_diff_check.py` だけ、Note/public URL が指定された場合に取得確認を行います。

### 外部 tracker や connector は必要？

不要です。`tracker_required: false`、`external_connectors_required: false` の前提です。

### 何を保証しない？

Note ログイン、接続の常時成功、画像アップロードの完全自動化、公開成果、
PV、SEO、おすすめ掲載、記事内容の事実性は保証しません。

## ロードマップ

現在の優先順位と判断ルールは [ROADMAP.md](ROADMAP.md) に集約しています。
README は「初めて使う人が安全に始めるための入口」に絞り、詳細な計画は
ロードマップ側で管理します。

## 表示について

GitHub ではこの README をそのまま読めます。ローカルで整形表示したい場合は
`python scripts/render_readme.py` を実行し、`README.rendered.html` を開いてください。

公開、push、PR 作成、リポジトリ公開範囲変更は、この README の編集とは別の
人間レビュー対象です。
