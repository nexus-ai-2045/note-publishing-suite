---
title: Note Publishing Suite README
type: スキルパッケージREADME
status: active
created: 2026-06-08
publication_gate: human_review_required
---

# Note Publishing Suite（NPS）

**書くところまで自動化。公開は、人が決める。**

![素材からNote下書き保存までは自動化し、公開直前で停止して人が判断するワークフロー](assets/note-publishing-workflow.svg)

## 概要

ローカル素材から Note の下書きを作り、検査し、エディタへ反映する
**NPS（Note Publishing Suite）** です。Codex / Claude Code から使えます。
公開・予約投稿・SNS 共有は自動で行わず、必ず公開直前で止まります。

パッケージ版: `0.2.71`

キャラクター画像の参照・生成添付・出力・目視観察を同じ版へ束縛する検査は `scripts/image_reference_gate.py` を使います。画像設定は利用者側の既存記事profileへ置き、packageに個人の画像や名前を保存しません。

読書用プレビューは `note_virtual_preview.py`、編集診断は同コマンドの `--diagnostics`、由来レビューは `note_preview.py --review-provenance` を使います。原稿の本人確認・保留は検査で維持します。

| すぐやる | あとで読む |
| --- | --- |
| [NPS として使う](#使い方-nps-として使う3分) | [できること](#できること) |
| [基本ワークフロー](#基本ワークフロー) | [安全設計](#制約と安全設計) |
| | [入口と詳しい資料](#入口と詳しい資料) |

**動画は不要です。** 下の 3 手順だけで NPS として使えます。

## 使い方: NPS として使う（3分）

必要なものは POSIX sh、Python、git です。

### 1. 取る・確かめる

```bash
git clone https://github.com/nexus-ai-2045/note-publishing-suite.git
cd note-publishing-suite
sh scripts/verify_public_package.sh
```

Windows では PowerShell verifier も使えます。

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

`-ExecutionPolicy Bypass` はこのプロセスだけに適用されます。
この verifier は Python と git も使って各 checker を実行するため、
先に利用可能か確認してください。
検証は公開操作を行わず、`embedded copy` と `standalone clone` の契約を確認します。
ローカル検証（`verify:local`）は上記の verifier で実行します。構成・安全境界・README表示・公開前停止線の確認範囲は開発・検証（参照資料: `docs/advanced-usage.md#開発検証`）を参照してください。
自動テストのあとに行うユーザー受け入れ確認は `USER_TEST.md` の4ケースを使います。
受け入れテストの合格は Note 公開の承認ではなく、公開操作は別の人間承認で扱います。

### 2. 保存先を選び、Codex に登録する

初回はAIが、保存先・読んでよい素材・本人の文体参照を案内します。
既存の個別設定は使い直し、なければ初回設定の案内（参照資料: `references/note-workflow-review-contract.md#初回設定の案内`）に沿ってpackage外のworkspaceへ保存します。画像・履歴・調査policyは用途に応じて選びます。

installerが行うのはpointer登録です。設定作成、Noteログイン、画像アップロードの対応確認まで完了するわけではありません。
例の `../my-note-workspace` は先に作成し、自分の保存先へ置き換えてください。


installer は実体を複製せず、package を指す pointer だけを置きます。

```powershell
pwsh -NoProfile -File adapters/codex/install.ps1 `
  -PackageRoot (Resolve-Path .) `
  -WorkspaceRoot (Resolve-Path ../my-note-workspace)
```

既定の配置先は `$env:CODEX_HOME\skills`、未設定なら `$HOME\.codex\skills` です。

macOS / LinuxのCodexは `NOTE_SKILL_RUNTIME=codex bash adapters/claude-code/install.sh ../my-note-workspace`、Claude Codeは `bash adapters/claude-code/install.sh ../my-note-workspace` を使います。

installerの終了時にも初回設定の案内先を表示します。Windowsの日本語案内はUTF-8で出力します。登録後の最初の依頼では「初回設定から案内して」と伝えてください。設定読戻しが失敗した場合は制作前に修正します。対話による案内であり、GUIの設定ウィザードはありません。

### 3. 最初の依頼例

Codex / Claude に、だいたい次のように頼むと NPS が起動しやすいです。

```text
note-publishing-suite で進めて。
読んでよい素材フォルダは <ここだけ>。
公開・予約・SNSはしない。下書き保存の手前まで。
```

| やりたいこと | 言うこと（例） |
| --- | --- |
| 記事のネタ出し | 「このフォルダから note 記事候補を3つ」 |
| 下書き | 「候補1で note 下書きを作って」 |
| 検査 | 「prepublish QA して」 |
| エディタ反映 | 「Note editor に反映。公開はしない」 |
| 公開判断 | 「publication gate で止まって」 |

固定の `ネタ帳.md` は使いません。入力は、ユーザーが最初に指定した
「読んでよい素材フォルダ」だけです。

全体像は上のワークフロー図だけで足ります。動画撮影は必須ではありません。

<details>
<summary>任意: 使い方動画を後から載せる場合</summary>

動画は **なくても運用できます**。人に見せたいときだけ足してください。

1. 1〜3 分の画面録画を `assets/demo/usage-walkthrough.mp4` に置く  
2. README に次を足す  

```markdown
[![NPS 使い方動画を再生](assets/demo/usage-walkthrough-thumb.svg)](assets/demo/usage-walkthrough.mp4)
```

置き場・台本・禁止事項: `assets/demo/README.md`（参照資料: `assets/demo/README.md`） / `assets/demo/storyboard.md`（参照資料: `assets/demo/storyboard.md`）

</details>

## できること

| できる | 自動では行わない |
| --- | --- |
| 指定素材から記事候補と下書きを作る | 指定外のフォルダや private URL を読む |
| プレビュー、投稿前検査、根拠確認を行う | 記事内容が正しいと断定する |
| Note エディタへ反映し、下書き保存まで進める | 公開、予約投稿、SNS 共有、外部告知 |
| 公開後の確認内容を台帳更新案にする | PV、SEO、おすすめ掲載などの成果を保証する |
| 問答packetと過去文体から、本人の口調・判断を残した下書きを作る | 本人が言っていない感想や結論を作文する |
| 無断短縮、改行、図・キャプション、目次、埋め込みを構造検査する | UI依存操作が常に成功すると断定する |
| Browser切断やtimeoutを分類し、安全な復旧経路へ戻す | processの一括終了や無制限retry |

公開操作には、対象と操作を特定した人間レビューと明示承認が必要です。
`publication_gate: human_review_required`

## 基本ワークフロー

```text
素材を指定 → 記事候補 → 下書き → ローカル検査 → Note 下書き保存 → 公開直前で停止
```

| 段階 | 入口 | 典型コマンド / skill |
| --- | --- | --- |
| 記事候補 | `note-idea-intake`（参照資料: `skills/note-idea-intake/SKILL.md`） | 素材フォルダを指定して候補出し |
| 下書き | `note-draft-production`（参照資料: `skills/note-draft-production/SKILL.md`） | 問答packet → 本文 |
| 投稿前QA | `note-prepublish-qa`（参照資料: `skills/note-prepublish-qa/SKILL.md`） | preview / pre_publish / fact |
| エディタ反映 | `note-editor-prepublish`（参照資料: `skills/note-editor-prepublish/SKILL.md`） | 下書き保存まで |
| 公開停止線 | `note-publication-gate`（参照資料: `skills/note-publication-gate/SKILL.md`） | 公開ボタン手前で停止 |
| 公開後台帳 | `note-postpublish-ledger`（参照資料: `skills/note-postpublish-ledger/SKILL.md`） | URL 確認後のみ |

公開済み記事を扉絵・本文だけ更新した場合は、元下書きを仮作成せず、`verify_published_update.py`（参照資料: `scripts/verify_published_update.py`）で公開APIの現在値を照合します。手順は`post-publish-context-proof.md`（参照資料: `references/post-publish-context-proof.md`）を参照してください。

下書き前には問答packetで本人の言葉、判断、避けたい断言、残したい脱線を確認し、
`voice_profile`と`shortening_budget`を固定します。詳しくは
`note-draft-authority-and-layout-contract.md`（参照資料: `references/note-draft-authority-and-layout-contract.md`）。

既存記事の起稿・修正前は、外部settingsから現在の文体参照本文と記事別の採否履歴を読みます。

```powershell
python scripts/note_feedback.py --readback --settings USER_SETTINGS_PATH --article-id ARTICLE_ID --source SOURCE_SNAPSHOT --draft CURRENT_DRAFT
```

この入口は既存履歴と現稿の一致を検査して内容を返す読取り専用処理です。標準出力JSONをjson.loadsやConvertFrom-Jsonで復号してから、元の参照本文を読みます。書く担当は、受け取った内容を先に読み、適用・保全・保留した具体的な直しを返します。hash一致だけで意味の適切な反映を証明しません。本人が話していない体験・感情・判断で空きを埋めるテンプレートは使いません。詳しくは設定・読戻し契約（参照資料: `references/note-workflow-review-contract.md#利用者が選ぶ設定正本と毎回の読戻し`）を参照してください。

## 制約と安全設計

要点だけ先に:

1. 読んでよい素材は、ユーザーが指定したフォルダだけ
2. 公開・予約・SNS は明示承認なしに押さない
3. 根拠ラベル（本人の言葉 / 外部事実 / AI整理）を混ぜない

保証ラチェットでは、失敗の原因・復旧方法・次回の禁止事項を残し、再発防止できるものを既存の検査器・契約テストへ反映します。UI依存の手動境界と自動検査の限界は保証ラチェットの詳細（参照資料: `docs/advanced-usage.md#保証ラチェット`）にまとめています。

<details>
<summary>根拠ラベル・provenance（詳細）</summary>

- 根拠は `source_database` / `source_pack`、構成案は `series_plot`、
  `article_plot`、`skeleton`、`wall_bang` として分離します。
- `production_candidate` と `editor_fixture` を混ぜません。詳しくは
  `note-article-provenance-design.md`（参照資料: `references/note-article-provenance-design.md`）。
- `source_pack_locked_with_user_speech_priority` では `user-said`、
  `external-fact`、`assistant-organized`、`hold` を区別します。
- 公開前に `scripts/provenance_leak_check.py --scope changed` を実行します。
  個別denylistは `data/provenance_leak_policy.local.json` に置き、
  公開パッケージへ直書きしない設計です。
- 公開、予約投稿、SNS共有、リポジトリ公開範囲変更は、対象・操作・方式の
  いずれかが不明、または現在の会話で明示承認がない場合は実行しません。

根拠ラベルの確認:

```bash
python scripts/provenance_label_check.py <draft.md> --json
```

AI 作文を含む下書きは、次の順でローカルレビューします。

```bash
python scripts/provenance_label_check.py <draft.md> --json
python scripts/note_preview.py <draft.md> --review-provenance -o <review.html>
python scripts/provenance_label_check.py <draft.md> --public-output <public-body.md>
```

- 「記事を書いて」「文章にまとめて」「会話を記事に」「メモを記事に」
  「下書きを直して」も下書き制作の自動発火対象です。
- レビュー HTML は本人=緑、AIのつなぎ=黄、資料の事実=青、保留=赤で塊を色分けし、
  上に種類ごとの件数と本文の字数を出します。下書きの frontmatter は表示しません。
- 修正対象は内部 ID ではなく、見出しまたは本文の短い引用で指定できます。
- `hold` が残る間は公開本文候補を書き出しません。公開本文候補では
  ローカル管理用の由来コメントを除去します。

</details>

<details>
<summary>Note エディタの詳しい境界</summary>

## Note エディタの境界

接続できる場合に限り、タイトル、本文、リンク、画像、タグなどを反映します。
下書き保存までで止まり、公開・投稿・予約確定ボタンは押しません。

- 低レベル操作: `note-editor-ops`（参照資料: `skills/note-editor-ops/SKILL.md`）
- 公式機能の棚卸し: `note-editor-capability-inventory.md`（参照資料: `references/note-editor-capability-inventory.md`）
- 1 cycle / 1 action: `note-editor-pdca-orchestration.md`（参照資料: `references/note-editor-pdca-orchestration.md`）
- 実画面の制約: `note-editor-live-constraint-boundaries.md`（参照資料: `references/note-editor-live-constraint-boundaries.md`）
- 画像アップロード停止線: `note-image-upload-automation-boundary.md`（参照資料: `references/note-image-upload-automation-boundary.md`） / `scripts/note_image_upload_boundary_check.py`
- 公式情報: `note-official-guidance-intake`、制約調査: `note-editor-constraint-debug`

リンクカードはURLを単独行に置いて Enter を押し、`figure[data-src]` などの
DOMで確認します。同期しない場合や固定座標が必要な場合は手動境界へ切り替えます。
Noteログイン、常時接続、画像アップロードの完全自動化は保証しません。

</details>

## 入口と詳しい資料

| 目的 | 参照先 |
| --- | --- |
| プロジェクト境界と現在地 | PROJECT_SSOT.md（参照資料: `PROJECT_SSOT.md`） |
| Codex から使う | SKILL.md（参照資料: `SKILL.md`） |
| 機械可読の契約 | package.yaml（参照資料: `package.yaml`） |
| 今後の計画 | ROADMAP.md（参照資料: `ROADMAP.md`） |
| 公開前の準備 | PUBLIC_READY.md（参照資料: `PUBLIC_READY.md`） / PUBLIC_RELEASE_CHECKLIST.md（参照資料: `PUBLIC_RELEASE_CHECKLIST.md`） |
| 初見ユーザーの受け入れテスト | USER_TEST.md（参照資料: `USER_TEST.md`） |
| セキュリティ | SECURITY.md（参照資料: `SECURITY.md`） |
| 変更履歴 | CHANGELOG.md（参照資料: `CHANGELOG.md`） |
| （任意）デモ動画の置き場 | assets/demo/README.md（参照資料: `assets/demo/README.md`） |

<details>
<summary>主な補助ツール一覧</summary>

- `scripts/note_preview.py`: ローカルプレビュー（旧・標準ライブラリのみの簡易版。廃止候補）。
- `scripts/note_virtual_preview.py`: note editor 実物の DOM/CSS 実測（`docs/note-preview/`）に基づく
  プレビュー。`note_preview.py` と違い、抽出済みの note 本物の CSS（`assets/note-preview/`）を
  `<link>` で読み込んで見た目を再現する。`note_preview.py` は本文リンクの色や見出しの余白が
  note 実物と一致しないため、乗り換え先はこちら。目次・アウトライン・（図: …）枠・
  H1→H2 丸めの警告なども合わせて出す。移植元: sample-project
  `sources/_tools/note-preview/render_note_preview.py`（v2、2026-09-11）。
  解析文書は `docs/note-preview/` にコピーしてある。
- `scripts/review_draft.py`: `build-context-card` と `review-draft`。
- `scripts/note_diff_check.py` / `scripts/fetch_note_body.js`: 公開本文の取得・差分確認。
- `scripts/post_publish.py`: 既定はドライランの台帳更新。
- `scripts/bump_package_version.py`: patch / minor / major を自動採番。
- `scripts/docs_sync_check.py`: 生成物と関連文書をread-onlyで同期検査。
- `scripts/note_interview_packet.py`: 低負担な問答packetを生成。
- `scripts/note_authorship_gate.py`: 本人発言にない作文や無断短縮を検査。
- `scripts/note_research_quality.py`: 任意の品質ポリシーに従い、調査報告の根拠・鮮度・採否と5段階のPDCA計画を読み取り専用で検査。実行入口は既存の `note_workflow_gate.py` のresearch段階。
- `scripts/note_linebreak_gate.py` / `scripts/note_figure_structure_gate.py`: 改行、図、captionを検査。改行gateは段落順の期待・観測soft-break配列を照合できる。プレビューは空行で段落を分け、同じ段落内の改行を `<br>` にする。
- `scripts/note_browser_transport_recovery.py` / `scripts/note_editor_timeout_recovery.py`: Browser切断とtimeoutを分類。前者はread-only復旧計画専用で、process終了や人間承認の真正性確認は行わない。
- `scripts/note_editor_pdca_failure_check.py`: Note editor 失敗パターン台帳を検査。
- `scripts/note_editor_pdca_cycle_check.py`: 記事ごとの PDCA cycle 受領JSONを検査（1 action・前後DOM証跡・非公開・routeあたり最大2回）。
- `scripts/topic_status_check.py`: 話題統合台帳の配線を検査。
- `scripts/package_consistency_check.py`: 宣言したスクリプトの実在を検査。
- `adapters/codex/install.ps1`: WindowsのCodex skill pointerを配置し、参照切れを検査。

</details>

## 詳しい制作・開発手順

ドキュメント同期・開発検証・制作と公開後の詳細（参照資料: `docs/advanced-usage.md`）を参照してください。
基本の開発検証は `python -m pytest scripts/test_skill_integration.py tests`、文書確認は `python scripts/docs_sync_check.py --base-ref origin/main` です。

公開前観測は `python scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json`、報告文は `python scripts/japanese_closeout_language_check.py --json` で検査します。
日本語報告の `ready for review` は下書き解除済み、`open PR` は未マージPR、`MERGED` はマージ済み、`mergeable` はマージ可能です。
これらを英語のまま報告した場合は構造バグとして出力ゲートを修正します。コマンド、ファイルパス、URL、SHA、識別子は原文のまま扱います。

## ライセンス

MIT License（参照資料: `LICENSE`）です。商用利用・改変・再配布を許可し、著作権表示と許諾表示を残します。利用者のworkspaceに保存する原稿・画像・採否履歴の権利を変更するものではありません。

## 毎回の開発検査

PRとmain/master更新の既存test workflowから、固定版のrepo-preflightとai-ratchet-gateを自動実行します。`package-smoke`はその成功が前提です。課金制限で開始されない場合はローカル相当の結果と区別し、設定や保護ルールを迂回しません。詳しくはPREFLIGHT.md（参照資料: `PREFLIGHT.md`）。
