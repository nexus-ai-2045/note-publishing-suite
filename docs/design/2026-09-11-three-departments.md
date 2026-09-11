---
title: note-publishing-suite の 3 部門設計
type: design
status: draft
created: 2026-09-11
publication_gate: human_review_required
external_action: none
scope_route: local_note_prep_only
---

# note-publishing-suite の 3 部門設計 (2026-09-11)

## 背景

2026-09-11 に本人 (nexus_ai) から次の指示を受けた。

- NPS (note-publishing-suite) を 3 部門に分ける。
- 操作部門は note editor / ブラウザ操作を担当し、Computer Use は使わない。
  note の UI 更新は自分で検知して直す PDCA (セレクタの実測 → 差分検知 →
  更新提案) を持つ。
- 操作部門の入力はクリップボード経由 (`pbcopy` → 貼り付け) を標準関数にする。
  画像はクリップボードに画像を入れて ProseMirror へ paste する経路を本命とし、
  ファイル選択ダイアログに依存しない。ダイアログを開く操作は禁止する。
  2026-09-11 にダイアログが開いてユーザーの作業を妨げたため。
- 文書作成部門は素材 → 構成 → 本文 → 制作パック → 仮想 note プレビューを担当する。
- 学習部門は口調・読者反応から書き方を更新する PDCA を担当し、口調は最後に直す。

この file はこの指示を設計として固定する。実装は既存 script /
既存子スキルへの追記・新規 helper で進め、この file 自体は正の運用手順を
持たない (手順は各子スキル SKILL.md / references / scripts を正本とする)。

## 3 部門と既存子スキルの対応

| 部門 | 主な役割 | 対応する既存子スキル | 対応する既存 references / scripts |
|---|---|---|---|
| 操作部門 (Operation) | note editor / ブラウザ操作の実行、UI 変化の検知と復旧、クリップボード経由の入力 | `note-editor-prepublish`、`note-editor-ops`、`note-editor-constraint-debug`、`note-official-guidance-intake` | `references/note-editor-capability-inventory.md`、`references/note-editor-pdca-orchestration.md`、`references/note-editor-live-constraint-boundaries.md`、`references/note-image-upload-automation-boundary.md`、`scripts/note_image_upload_boundary_check.py`、`scripts/note_editor_prepublish_verify.py` |
| 文書作成部門 (Authoring) | 素材選定、構成 (skeleton)、本文、制作パック、仮想 note プレビュー | `note-idea-intake`、`note-draft-production`、`note-prepublish-qa` | `scripts/note_preview.py`、`scripts/pre_publish_check.py`、`scripts/note_fact_check.py`、`scripts/note_diff_check.py`、`references/note-article-provenance-design.md` |
| 学習部門 (Learning) | 口調・読者反応から書き方を更新する PDCA (口調は最後に直す)、公開後の記録 | `note-postpublish-ledger` (実測データ源)、`note-publication-gate` (承認境界を維持したまま学習対象を確定) | `scripts/engagement_tracker.py`、`data/published_notes.json`、`data/note_drafts.json` |

`note-publication-gate` は 3 部門どれの作業でも公開直前で必ず経由する横断 gate
であり、単一部門には属さない。この設計では部門をまたぐ「最終停止線」として
維持し、どの部門からの依頼でも公開/予約直前の停止義務は変えない。

学習部門は現時点で専用の子スキル実体を持たない。既存の
`note-postpublish-ledger` が持つ engagement / diff データを入力にして、
書き方 (構成、主張の出し方、根拠の配置など) を先に更新し、口調は最後に
直す運用ルールをこの file で新設する。専用スキル化は別途判断する。

## 操作部門 (Operation)

### Principle

note editor の UI は運営側の変更で予告なく変わる。操作部門は「一度作った
セレクタや操作手順が永久に正しい」と仮定せず、実行前に実測し、ズレを検知
したら自動で直す提案を出す PDCA を持つ。実行手段は、ユーザーの画面操作を
妨げない経路 (クリップボード経由の貼り付け) を優先し、Computer Use や
ファイル選択ダイアログのような画面占有・フォーカス奪取を伴う経路は使わない。

### Invariant

- Computer Use (`mcp__computer-use__*` 相当の画面操作 API) は使わない。
- テキスト入力の標準関数は「クリップボードへ置く → 対象要素へ貼り付ける」
  経路であり、`scripts/clipboard_bridge.py` の `put_text` / CLI
  `put-text` を正本とする。
- 画像入力の本命経路は「画像をクリップボードに入れて ProseMirror へ paste」
  であり、`scripts/clipboard_bridge.py` の `put_image` / CLI `put-image`
  を正本とする。ファイル選択ダイアログを開く操作 (native file picker の
  起動) は禁止する。
- セレクタ、DOM 構造、ツールバー配置は実行前に実測し、前回の実測記録と
  差分がある場合は「差分あり」として報告し、無断で古いセレクタのまま
  実行しない。
- write 系操作 (paste、保存、editor 状態変更) の前にクリップボードの
  既存内容を退避し、操作後に `restore` で元へ戻す。ユーザーが操作前に
  クリップボードへ置いていた内容を上書きしたまま終わらない。
- attach/inspect できない、または実測差分が大きく復旧できない場合は
  1 回までの再確認で止め、Chrome や Computer Use へ無断で切り替えない
  (既存 Hard Gate を継承)。

### Detector

- セレクタ実測ログと前回実測ログの diff (`references/note-editor-*` 系
  ドキュメントに記録している既存セレクタ/構造メモとの比較)。
- `note_image_upload_boundary_check.py` 相当の boundary checker が
  `ok: false` を返す、または禁止経路 (ファイル選択ダイアログを開く操作、
  Computer Use 相当の呼び出し) が手順内に出現する。
- クリップボード操作前後で `get_text` の内容が想定と異なる (退避漏れ、
  他プロセスによる上書き)。

### Repair Path

- セレクタ差分を検知したら、まず実測結果を
  `references/note-editor-capability-inventory.md` または
  `references/note-editor-live-constraint-boundaries.md` へ追記し、
  古い記述を上書きせず「実測日・旧記述・新記述」を残す。
- 自動化できないズレ (UI の見た目変更、ボタン位置変更など) は手動境界として
  `note-editor-constraint-debug` へ渡し、公開 gate の確認項目に残す。
- クリップボードの内容が想定外だった場合は、退避していた元の内容を
  `restore` で戻し、対象操作を再実行しない。

### Evidence

- 2026-09-11: note editor の画像 upload でファイル選択ダイアログが開き、
  ユーザーの作業を妨げた (本人指摘)。この 1 件を根拠に、ダイアログを開く
  操作を新たに禁止経路へ追加する。
- 既存 `references/note-image-upload-automation-boundary.md` は
  `visible_windows_file_dialog` を `requires_user_confirmation` の
  許可経路として保持している。今回の指示とはこの 1 点で衝突している
  (詳細は本 file 末尾「既存境界との衝突点」)。

## 文書作成部門 (Authoring)

### Principle

記事の質は「素材の選定」「構成」「本文」「制作パック化」「公開前の
仮想プレビュー確認」という順序を飛ばさないことで決まる。文書作成部門は
この順序を守り、各段で根拠不明な主張を確認対象として残す。

### Invariant

- 選択されたローカル素材フォルダの外を読まない (既存 Hard Gate を継承)。
- skeleton は導入・読者の痛み・主張・根拠・具体例・反論処理・締め・CTA を
  含む。
- 本文は事実・推定・意見を混在させず、根拠が必要な主張は確認対象として
  残す。
- 公開前に `note-prepublish-qa` の既存 script 順序
  (`note_preview.py` → `pre_publish_check.py` → `note_fact_check.py` →
  `note_diff_check.py`) を通し、仮想 note プレビュー (`note_preview.py`
  が出す HTML) で見た目を確認してから editor phase へ渡す。
- 制作パック (素材要約、skeleton、本文、画像案、タグ案一式) は
  `content/drafts/` 配下にまとめ、editor phase 以降が同じ入力を再利用
  できる状態にする。

### Detector

- `pre_publish_check.py` / `note_fact_check.py` が警告・未確認表現・
  内部メモ残りを返す。
- 仮想プレビュー HTML と本文 draft の間に構成順序の欠落 (CTA なし、
  根拠なしの主張) がある。

### Repair Path

- 警告が出た段は draft phase へ差し戻す (既存 Routing の停止条件を継承)。
- 根拠不明の主張は削除するか、確認対象として明示ラベルを付けて残す。

### Evidence

- 既存 `note-prepublish-qa` / `note-draft-production` の SKILL.md に
  既に同等の手順があることを確認した (本タスクでは変更していない)。

### 口述モード

本人が口述した記事 (`source_mode: source_pack_locked_with_user_speech_priority`)
では、文書作成部門の手順そのものは変えないが、素材の作り方が逆転する。AI は
skeleton や言い回しを先に作らず、本人が話した言葉をそのまま本文化し、語尾・
誤変換・句読点だけを整える (作文禁止)。本文中の数字・固有名詞・日付・URL は
`scripts/note_fact_check.py` で抜き出し、事実確認は本体モデルではなく
Sonnet/Haiku 相当の worker (Operation 部門と同じ worker 分担方針) に委譲する。
確認できた項目は本文に一次情報リンクを付け、確認できない項目は本文に残さず
対になる notes file の未確認一覧へ移す (本文には空欄を残してよい)。構成・
言い回し・方針の判断は本人がする。詳細な運用は
`skills/note-draft-production/SKILL.md` の「口述モード」節を正本とし、
この段落はその要約に留める。

## 学習部門 (Learning)

### Principle

書き方の改善は「読者に伝わったかどうか」の実測 (公開後の反応、diff で
分かった修正点) から始める。口調は表層の調整なので最後に直す。書き方
(構成、主張の順序、根拠の出し方) を先に固定してから口調を合わせる。

### Invariant

- 学習の入力は実測データ (`data/published_notes.json` の
  engagement 記録、`note_diff_check.py` の diff 結果、
  `scripts/engagement_tracker.py report`) に限る。未確認の感想を
  書き方の変更根拠にしない。
- 更新順序は「構成・主張の出し方・根拠の配置」→「口調」の順を固定する。
  口調だけを最初に変える提案は差し戻す。
- 学習結果の反映先は既存子スキルの SKILL.md 本文または
  `references/` の運用メモとし、新しい正本 file を無断で増やさない。
- 公開/予約/共有の承認境界 (`note-publication-gate`) は学習部門の
  提案によって緩めない。

### Detector

- `engagement_tracker.py report` の傾向と、直近の draft/公開記事の
  構成差分を突き合わせ、同じ問題 (例: 根拠不足、CTA 弱い) が繰り返し
  出ているかを見る。
- 口調変更の提案が構成変更より先に出ていないか (順序チェック)。

### Repair Path

- 繰り返し出た問題は `note-draft-production` の skeleton 手順、または
  `note-prepublish-qa` の確認観点へ追記して再発防止に落とす。
- 口調の変更は、構成側の改善が反映された後の draft でのみ適用する。

### Evidence

- 現時点では専用の学習部門スキル実体がなく、`note-postpublish-ledger`
  のデータを入力にする設計止まり。運用 1 サイクル分の実測はまだない
  (未実測)。

## 既存境界との衝突点

- `references/note-image-upload-automation-boundary.md` と
  `scripts/note_image_upload_boundary_check.py` は、画面に見えている
  ファイル選択ダイアログ (`visible_windows_file_dialog`) を
  `requires_user_confirmation` の許可経路として維持している。
  一方で `scripts/note_image_upload_boundary_check.py` の
  `REQUIRED_PROHIBITIONS` は `clipboard_injection` を禁止経路として
  持っている (OS clipboard 経由の画像挿入は既存 checker 上は禁止扱い)。
  今回の指示 (クリップボード経由の paste を本命化し、ファイル選択
  ダイアログを禁止) はこの既存境界と正面から食い違う。この file は
  設計のみを固定し、既存 checker / reference の書き換えはこのタスクの
  スコープ外として扱う。次の対応候補を残す。
  - `note_image_upload_boundary_check.py` の `REQUIRED_ROUTES` /
    `REQUIRED_PROHIBITIONS` を、`scripts/clipboard_bridge.py` の
    `put_image` 経路 (browser 外の OS clipboard 経由) を許可経路として
    追加できるか検討する。
  - `visible_windows_file_dialog` を禁止経路へ落とすか、
    「ダイアログを自動で開く操作」と「すでに開いているダイアログを
    ユーザー監督下で操作する」を区別して残すかを判断する。
  - どちらも Type1 相当 (安全境界の変更) のため、本人の承認を得てから
    別 diff で反映する。

## 未実装・未実測

- クリップボード経由の paste が実際の note editor (ProseMirror) で
  成立するかは、実際の browser 上での実測 (`note-editor-ops` /
  `note-editor-constraint-debug` の PDCA サイクル) が必要。この file の
  時点では未実測。
- セレクタ差分検知の自動 PDCA (実測 → 差分検知 → 更新提案) は、この file
  で invariant / detector / repair path を定義しただけで、専用の
  checker script はまだない。
- 学習部門の専用子スキル化は未着手。
