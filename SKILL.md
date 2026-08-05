---
name: note-publishing-suite
description: "Use when the user wants repo-local, end-to-end Note publishing support or asks to write, assemble, or revise an article/draft from conversation or notes. Also use for Japanese requests such as \"記事を書いて\", \"文章にまとめて\", \"会話を記事に\", \"メモを記事に\", \"下書きを直して\", \"note投稿を一気通貫\", \"Note投稿パッケージ\", or \"note公開前チェック\"."
---

# Note Publishing Suite

## 役割

このスキルは repo root 内で、Note 投稿の「企画 → 素材探索 → 下書き → 公開前検査 → Note editor 反映 → 公開直前停止 → 公開後確認 → ローカル台帳更新」を束ねる親スキル。

正の作業場所はこの repo の `content/drafts/`、`content/assets/`、`published/`、`data/`、`scripts/`。新しい helper 名を勝手に作らず、まず既存 script を使う。

子スキル実体は `skills/` 配下に置く。実行時はこの親スキルで全体 gate を確認してから、該当する子スキルを読む。

## Routing

ユーザーの依頼を次の phase に分ける。複数 phase にまたがる場合も、公開/外部送信 gate は最後まで保持する。

「記事を書いて」「文章にまとめて」「会話を記事に」「メモを記事に」
「下書きを直して」など、Note を明記しない作文・編集依頼でも、公開候補へ
つながるローカル記事制作なら本スキルを自動発火する。

| phase | 子スキル | 主な成果物 | 停止条件 |
|---|---|---|---|
| idea | `note-idea-intake` | 記事候補、読者、リスク | 読んでよい素材が未指定 |
| draft | `note-draft-production` | skeleton、本文、画像案、タグ案 | 根拠不足、権利/秘密情報リスク |
| qa | `note-prepublish-qa` | preview、検査結果、fact check | 警告、未確認、内部メモ残り |
| editor | `note-editor-prepublish` + `note-editor-ops` | Note editor 下書き保存証跡 | browser/画像 upload 境界 |
| official-guidance | `note-official-guidance-intake` | note 公式一次情報の取り込み | 一次情報なし、公式未確認 |
| editor-debug | `note-editor-constraint-debug` | 埋め込み/目次/改行などの実測境界 | attach不可、公開操作が必要 |
| gate | `note-publication-gate` | 公開直前停止メッセージ | 明示承認なし |
| ledger | `note-postpublish-ledger` | 公開確認、台帳更新案 | 公開URL/status 未確認 |

## Runtime Guarantee

この package は、Codex だけ、または Claude Code だけで動くことを前提にする。Linear、GitHub Issues、Slack、Drive、別 runtime は必須ではない。

- Spark / Sonnet worker は速度改善の任意手段。無くても workflow は止めない。
- Codex では Spark くん相当の worker があれば使ってよい。
- Claude Code では Sonnet 相当の worker があれば使ってよい。
- worker が使えない場合は、親 runtime が同じ分担粒度で順に処理する。
- 親 runtime は問い、採否、設計、Type1 境界、公開/外部送信 gate、最終報告に集中する。
- worker へ渡す範囲は、素材要約、候補抽出、表化、diff/log 圧縮、QA観点洗い出し、単純な実装 slice に限る。
- worker には credential、Cookie、非公開URL、公開/予約/送信権限、repository visibility 変更権限を渡さない。
- worker 出力は raw のまま採用せず、親 runtime が source、diff、test、publication gate を確認してから反映する。
- worker が使えない tool surface では、理由を closeout に残し、親 runtime が同じ分担粒度で順に処理する。

### MPC型フィードバックとFDE分割

複数の問題を一度に総当たりすると、組合せが急増する「次元の呪い」が起きる。
これを消せるとは主張せず、FDEで同時に探索する軸を分割する。

- 観測: 現在の原稿、検査、Browser、runtime、公開境界を別々に測る。
- 予測: 各軸の次の一手が改善する範囲と、壊し得る範囲を記録する。
- 局所最適化: 内容品質、記事構造、UI復旧、runtime配布などを独立担当へ分ける。
- 一歩実行: 各軸で最小の検証可能な変更だけを反映する。
- 再観測: focused testと統合testを測り、失敗した軸だけ計画を更新する。

局所担当は他軸の変更を決めず、親runtimeが合流点、Type1境界、公開判断を統合する。
これはMPC（モデル予測制御）のように、有限範囲を予測して一歩進み、結果から再計画する運用契約である。

## Guarantee Ratchet

Note editor 実測で見つかった失敗、手動境界、復旧手順、成功条件は、その場限りの会話メモで終わらせない。

壁打ち、問答、口調・著者性、短縮防止、改行、図、キャプションの共通契約は
`references/note-draft-authority-and-layout-contract.md` を正本にする。

- 失敗した操作は、原因、復旧方法、次回の禁止事項を短く記録する。
- 再発防止できるものは、既存 script の checker、package contract test、または子スキルの境界文言へ落とす。
- 記事が何を元に作られたかは `references/note-article-provenance-design.md`
  を正本にし、`article_lane`、`source_mode`、`based_on`、`allowed_use`、
  `not_allowed`、`editor_test_allowed` を draft frontmatter で固定する。
- `source_mode: source_pack_locked_with_user_speech_priority` の draft では、
  `scripts/provenance_label_check.py <draft.md> --json` で `user-said`、
  `external-fact`、`assistant-organized`、`hold` の境界を検査する。
- ローカル Markdown の由来情報は公開本文へ見せる注記ではない。
  `note_preview.py --review-provenance` で人間レビュー用 HTML を作り、
  修正指示は内部 ID ではなく見出しまたは本文の短い引用で受ける。
- `hold` がゼロになり検査が通った後だけ、
  `provenance_label_check.py --public-output` で由来コメントを除いた本文候補を作る。
- note editor の埋め込み、目次、Shift+Enter の live 実測境界は
  `references/note-editor-live-constraint-boundaries.md` を正本にし、
  `figure[data-src]`、`iframe.note-embed`、`table-of-contents`、`toc`、
  `H2` / `H3`、`<br>`、Undo 手動境界を contract test で保持する。
- checker に落とす場合は、実記事 draft への実行結果まで確認する。
- UI やブラウザ状態に依存して自動保証できないものは、手動境界として明記し、公開 gate の確認項目へ残す。
- 追加した保証は、closeout で「増やした保証」「実行したテスト」「まだ保証しないもの」に分けて報告する。
- packageやworkflowを変更するPRでは、`scripts/docs_sync_check.py`で生成物と関連文書を検査する。通常検査はread-onlyとし、修復は明示的な`--fix-generated`だけに限定する。
- docs-sync CIは`contents: read`を保ち、artifact以外の外部書き込み、commit、push、PR編集を行わない。
- ユーザーが日本語運用を指定している場合、完了報告や PR 報告の
  状態語を CLI 表示の英語のまま出さない。これは謝罪文ではなく
  `output_language_gate` の構造バグとして扱う。

## Hard Gates

- ユーザーが明示的に選んだローカル資料フォルダだけ読む。
- 公開、予約投稿、投稿、共有、告知、SNS 同時投稿、外部送信、公開範囲変更は、現在の会話で対象記事と操作を特定した明示承認があるまで実行しない。
- `note_browser_transport_recovery.py` はread-only計画専用とし、process終了や人間承認の真正性確認をこの公開packageだけで行ったとみなさない。
- Note 画面では、公開ボタン、投稿ボタン、予約確定ボタンを押す手前で停止する。
- X 投稿、いいね、キャンペーン、自動告知、Discord/Slack 共有はこの汎用 Note パッケージ外。別依頼と別承認で扱う。
- 内部ブラウザだけで画像アップロードを完全自動化できる前提にしない。失敗時は手動または supervised 操作に分け、未設定ならその状態を報告する。
- Note editor の write 前に対象ロックを置く。別note、別draft、別tab、別Browser surface、別accountへの切替は、理由と予定操作を示してユーザーの事前確認を得る。同一対象へのwriteが現在の会話で承認済みなら、read-onlyからwriteへ進むためだけの重複確認は不要とする。未承認ならwrite前に確認する。Chrome、Computer Use、manual browserへ自動fallbackしない。
- 能力非対応は再試行0回、同一対象の接続失敗またはDOM状態ズレは再確認後1回までとする。復旧できなければ、対象pathと未実行操作を返して手動境界または保留へ落とす。
- 画像 upload 境界は `references/note-image-upload-automation-boundary.md` と `scripts/note_image_upload_boundary_check.py` で確認する。画面に見えている Windows ファイル選択ダイアログだけを扱う場合も、現在会話での明示確認があるまで実行しない。
- Windows / Mac 環境差は `references/note-image-upload-automation-boundary.md` の matrix に従う。公式推奨環境でも成功保証ではなく、stopline と禁止経路を保証する。
- ログ、成果物、台帳に Cookie、token、非公開 URL、秘密情報を含めない。
- `data/note_drafts.json` は Note editor 下書きや stale/superseded 状態の台帳、`data/published_notes.json` は公開済み Note の一次台帳として扱う。

## State Labels

成果物には必要に応じて frontmatter を置く。

- `publication_gate: human_review_required`
- `external_action: none`
- `platform: note`
- `status: draft` / `ready-before-human-review` / `editor-draft-saved` / `published`
- `scope_route: local_note_prep_only`

## 入力と出力

入力:
- 対象 draft path。未作成なら保存先候補は `content/drafts/<date>-<slug>.md`。
- 読んでよい素材フォルダ。
- Note draft/edit/preview URL。未作成なら Unknown とする。
- 公開方式。即時公開、予約投稿、下書き保存のみのいずれか。
- 公開/予約/共有の人間承認状態。

出力:
- 記事候補リスト、選定理由、リスク確認。
- skeleton、draft path、top-image 案、タグ案。
- preview HTML path、投稿前検査結果、fact check 結果、必要な差分確認結果。
- Note editor 反映結果。タイトル、本文、画像、リンク、目次、タグ、保存通知など。
- 公開前停止メッセージ。
- 公開後 URL/status/Note 表示日時の確認結果と ledger 更新案。

## Standard Closeout

各 phase の最後に、次を短く報告する。

- 読んだ主要ファイル。
- 作成/変更したローカルファイル。
- 実行したコマンドと結果。
- 未実行の外部 action。
- 次の gate または残り確認。

### 日本語完了報告ゲート

ユーザーに見える完了報告、PR 報告、マージ報告、停止理由は日本語で書く。
コマンド、ファイルパス、URL、SHA、package identifier は原文のまま使ってよい。
ただし CLI や GitHub の状態語は説明文にそのまま貼らない。

置換する状態語:

- `ready for review`: 下書き解除済み。
- `open PR`: 未マージPR。
- `MERGED`: マージ済み。
- `mergeable`: マージ可能。
- `success`: 成功。
- `failed`: 失敗。

違反した場合は「うっかり」や「謝罪」で閉じず、
`output_language_gate` の欠落として扱い、
`scripts/japanese_closeout_language_check.py --json` と contract test を通してから閉じる。

## 子スキル

### note-idea-intake

実体: `skills/note-idea-intake/SKILL.md`

- 選択されたローカル資料だけを対象に、記事候補、読者、今出す理由、未確認リスクを出す。
- 探索方法を短く説明する。例: ファイル名、更新日、見出し、未完成メモ、反応があった公開済み記事を見る。
- 個人情報、秘密情報、未承認の外部情報を素材化しない。

### note-draft-production

実体: `skills/note-draft-production/SKILL.md`

- skeleton は導入、読者の痛み、主張、根拠、具体例、反論処理、締め、Call To Action（CTA）を含める。
- 本文は事実、推定、意見が混ざらないように書く。根拠が必要な主張は確認対象として残す。
- TOP 画像は 7 案を出す。実画像生成ができない場合は prompt、構図、避ける表現、適合理由を出す。
- タグ案は広い発見タグ、主題タグ、文脈タグ、所有シリーズタグを混ぜる。
- 本人の発言や素材が不足する場合は問答 intake に戻り、`voice_profile` を根拠に感想や体験を作文しない。`shortening_budget` を置き、省略候補は人間確認なしに削除しない。
- `production_candidate` は、問答packetまたは編集前正本を一意に示す
  `shortening_source` と `shortening_budget` をfrontmatterへ記録し、
  production QA で `note_authorship_gate.py` を実行する。
  `shortening.checked=true` と `overall=ok` を確認できなければ完了扱いにしない。

### note-prepublish-qa

実体: `skills/note-prepublish-qa/SKILL.md`

既存 script をこの順で使う。

```powershell
python scripts\note_preview.py <draft.md> -o <preview.html>
python scripts\pre_publish_check.py <draft.md>
python scripts\note_fact_check.py local <draft.md>
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...> --snapshot-out <local-snapshot.txt> --json
```

- `scripts/pre_publish_check.py --fix` はファイルを書き換えるため、ユーザーが明示した時だけ使う。
- `note_diff_check.py` は公開済み URL や editor 反映後の確認対象 phrase がある場合だけ使う。
- 未確認表現、数字、URL、内部メモ、HTML コメント、前回リンク不足が残る場合は公開 gate へ進まない。

### note-editor-prepublish

実体: `skills/note-editor-prepublish/SKILL.md`

- 既存 global skill `note-editor-prepublish` を参照して、Note editor 反映、目次、リンク、画像、埋め込み、タグ確認、下書き保存を行う。
- 低レベルの Browser 操作、埋め込み、DOM確認、Undo復旧、checkerラチェットは `skills/note-editor-ops/SKILL.md` を読む。
- note editor、埋め込み、URL単独行、Enter変換、DOM確認、figure/data-src、Undo、固定座標、CUA/Playwright、投稿確定後台帳のいずれかが出たら `note-editor-ops` を自動参照する。
- in-app Browser を優先する。attach/inspect できない場合は停止し、Chrome や Computer Use へ無断で切り替えない。
- 画像アップロード、目次位置、カーソル操作は実測確認し、うまくいかない場合は手動境界として報告する。画像 upload 境界の運用保証は `references/note-image-upload-automation-boundary.md` と `scripts/note_image_upload_boundary_check.py` で確認する。

### note-official-guidance-intake

実体: `skills/note-official-guidance-intake/SKILL.md`

- note 公式ヘルプ、公式マガジン、運営告知など一次情報だけを取り込む。
- タグ、目次、公開時間、推奨環境、画像、埋め込みなどを公式扱いする前に使う。
- 未確認や local observation を公式扱いしない。作文禁止。
- 実用できる情報だけ `references/note-editor-capability-inventory.md` へ反映する。

### note-editor-constraint-debug

実体: `skills/note-editor-constraint-debug/SKILL.md`

- 埋め込み、目次、Shift+Enter、画像 caption/alt、保存表示、toolbar 差分を実測する。
- `note-editor-ops` と組み合わせ、1 cycle 1 action で再現手順と復旧可否を残す。
- 自動化できるものは checker / contract test / skill 文言へ落とす。
- UI 状態に依存して保証できないものは手動境界として公開 gate に残す。
- 改行、図、キャプションは `references/note-draft-authority-and-layout-contract.md` と照合する。

### note-publication-gate

実体: `skills/note-publication-gate/SKILL.md`

公開または予約の直前に必ず停止し、次を確認する。

- note アカウント、対象記事、タイトル、本文、TOP 画像、画像権利。
- タグ、マガジン、公開範囲、無料/有料、価格、SNS 共有設定。
- 下書き保存、preview、事実確認、秘密情報除外、内部メモ除外。
- 即時公開か予約投稿か。予約なら日時と timezone。
- 現在の会話で「この対象記事のこの操作を実行してよい」という明示承認があるか。

承認がない場合の停止文:

```text
ここで停止します。
- Note 画面: 公開/投稿/予約確定ボタンを押す手前
- 確認済み: タイトル / 本文 / TOP画像 / タグ / マガジン / 公開範囲 / 無料・有料 / 価格 / SNS共有設定 / 下書き保存 / プレビュー / 事実確認 / 秘密情報除外
- 未実行: 公開 / 予約投稿 / SNS共有 / 外部告知

対象記事と操作を明示して、最終承認をもらうまで押しません。
```

### note-postpublish-ledger

実体: `skills/note-postpublish-ledger/SKILL.md`

公開または予約が明示承認済みで完了した後だけ実行する。

- Note 側の完了表示、公開 URL、公開状態、予約日時、下書きに残っていないことを確認する。
- 公開本文の確認には既存 script を使う。

```powershell
python scripts\post_publish.py --url <note_url> --draft <draft.md> --dry-run
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...>
python scripts\engagement_tracker.py report
```

- `scripts/post_publish.py` は X 投稿や schedule option を持つため、`--x-text`、`--x-schedule` はこの suite から使わない。
- `data/published_notes.json` には公開済み URL、title、published_at、tags、image_url、local_source、source、plain_status を記録する。
- `data/note_drafts.json` は draft/stale/superseded/published_from_note_editor_record の状態を保ち、公開済み一次台帳に混ぜない。
- package 外の workspace 固有台帳を使う場合は `scripts/post_publish.py --ledger-dir <dir>` を使う。script の複製は作らない。
- editor で公開版が変わった場合は、公開本文 snapshot、SHA-256、`local_draft_differs_from_published` を ledger に残す。
- Note 表示日時はユーザーの手動確認値を優先して記録する。

## Issue Drafts

`issue-drafts.md` を正本にして、外部 tracker 非依存の issue draft を保持する。Linear などの tracker が使える状態でも、現在会話でユーザーが明示依頼するまでは外部登録せず local draft の更新だけで止める。

転記元: `issue-drafts.md`

1. `Validate package contract`
   - 親 routing、manifest workflow、6子 skill 契約、公開停止 gate、package verification test を確認する。
2. `Keep tracker-free runtime compatibility`
   - Linear などの外部 tracker がなくても、Codex または Claude Code 単体で workflow を進められることを保証する。
3. `Keep Spark/Sonnet worker acceleration optional`
   - Spark / Sonnet worker は任意の速度改善として残し、無い場合は親 runtime が順に処理する。
4. `Run one local Note draft through QA lane`
   - preview、pre-publish、fact check、diff check の実運用接続と、警告時の draft phase 差し戻しを確認する。
5. `Exercise Note editor handoff without publishing`
   - Note editor 反映、下書き保存、画像/タグ/マガジン確認、公開/予約確定手前停止を確認する。
6. `Define post-publish ledger procedure`
   - 公開後 URL/日時/status/ledger 更新と、SNS 共有 option の分離を確認する。
7. `Run note official guidance intake`
   - note 公式ノウハウは `note-official-guidance-intake` で一次情報化してから反映する。
8. `Debug practical editor constraints`
   - 埋め込み、目次、段落内改行などは `note-editor-constraint-debug` で実測境界へ落とす。
## 完了条件

- 親 `SKILL.md` が既存 QA scripts と既存 editor skill を参照している。
- 公開/予約/共有は明示承認なしに実行不可と明記されている。
- X 投稿、いいね、外部告知が Note 汎用パッケージ外として分離されている。
- `data/note_drafts.json` と `data/published_notes.json` の役割が明記されている。
- `package.yaml`、`README.md`、`issue-drafts.md` と、`package.yaml` の
  `skills` に列挙された全子スキルが存在する。
- 子スキルが入力、成果物、停止条件、closeout evidence を持つ。
- `references/note-image-upload-automation-boundary.md` と `scripts/note_image_upload_boundary_check.py` が存在し、画像 upload 境界の残務ゼロを確認できる。
- 検証コマンドは `package.yaml` の `verification` を正本とし、そこに列挙された
  公開package検証と必要な developer check が通る。
- プロジェクト境界と現在地は `PROJECT_SSOT.md` が単独で保持し、
  内部設計文書や private workspace の path を公開 package へ含めない。
