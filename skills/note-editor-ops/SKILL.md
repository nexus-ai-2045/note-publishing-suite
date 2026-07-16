---
name: note-editor-ops
description: "Use inside note-publishing-suite for low-level Note editor browser operations: attach, safety gates, embeds, DOM verification, undo recovery, and editor-to-local guarantees."
---

# note-editor-ops

## 役割

Note editor で実際に必要になる低レベル操作を、機能ごとに分けて扱う。
`note-editor-prepublish` は editor phase の親手順、ここは Browser 操作の実務手順。

公式機能、画面幅、カーソル位置、ブラウザ面、AI操作面の棚卸しは
`../../references/note-editor-capability-inventory.md` を読む。
公式ノウハウを新しく取り込む時は `../note-official-guidance-intake/SKILL.md` を読む。
埋め込み、目次、Shift+Enter、画像 caption/alt、保存表示などを実測する時は
`../note-editor-constraint-debug/SKILL.md` を読む。
操作の分割、検証、差し戻しは
`../../references/note-editor-pdca-orchestration.md` を読む。
埋め込み、目次、Shift+Enter の live 実測境界は
`../../references/note-editor-live-constraint-boundaries.md` を読む。
画像 upload 境界は `../../references/note-image-upload-automation-boundary.md` を読み、
`../../scripts/note_image_upload_boundary_check.py` で保証する。

## 自動発火

次の語が依頼や作業内容に出たら、このスキルを読む。

- note editor、下書き、本文反映、サイドペイン本文。
- 埋め込み、リンクカード、URL単独行、Enter変換。
- note公式、公式ソース、公式ノウハウ、note-official-guidance-intake。
- 目次、Shift+Enter、段落内改行、画像 caption、画像 alt、
  note-editor-constraint-debug。
- 一時保存、公開に進む、投稿、予約、共有。
- DOM確認、figure、data-src、hrefだけ、通常リンク残り。
- Undo、ズレ、固定座標、CUA、Playwright。
- 画面幅、viewport、scroll、カーソル、selection。
- DOM変化、responsive、overflow menu、selector fallback。
- 内部ブラウザ、in-app Browser、Chrome extension、推奨ブラウザ。
- 操作対象ロック、対象切替、surface 切替、事前確認、fallback、再試行。
- 画像 upload、note-image-upload-automation-boundary、
  note_image_upload_boundary_check.py。
- Codex main、Spark、worker、human supervised。
- PDCA、Goal、Plan、Do、Check、Act、work packet、cycle、orchestration。
- 公開後、台帳、published_notes、note_drafts。

## 機能別操作

### 0. PDCA orchestration

- Note editor 操作は一括実行せず、Goal / Plan / Do / Check / Act の cycle に分ける。
- 1 cycle では 1 action だけ行う。例: attach、候補列挙、cursor prep、URL 1件貼り付け、Enter 1回、DOM確認、Undo 1回。
- 各 cycle の前に、完了条件、非目標、公開/保存/共有 gate、Undo / stopline を決める。
- Main agent は採否、公開 gate、secret/auth、最終報告を保持する。
- Spark / worker は read-only summary、候補抽出、公式source表化、diff/log圧縮、risk second-pass に限定する。
- UI 操作の write packet は原則 main agent が担当する。

### 1. Browser attach

- in-app Browser で対象 editor URL に attach する。
- attach / inspect できない場合は停止する。Chrome、Computer Use、live article へ無断で切り替えない。
- 現在 URL、title、本文 root、対象 note id を読み取りで確認する。
- in-app Browser の URL policy が `note.com` / `editor.note.com` の open/goto を拒否した場合、raw CDP、別ブラウザ、Chrome profile、間接URLなどで回避しない。ユーザーがサイドパネルで開いた後に current tab へ attach する。
- Browser surface は in-app Browser / Chrome extension / manual browser のどれかを明示する。
- AI surface は Codex main / worker / human supervised のどれかを明示する。

### 1a. Operation target lock

- write前に `note id / draft URL / article lane / tab / Browser surface / account / operation mode` を対象ロックとして記録する。
- 別note、別draft、公開済み記事、別tab、別Browser surface、別account、read-onlyからwriteへの変更は対象切替として扱う。
- 対象切替の前に、切替先、理由、予定操作、公開系操作は未実行のままであること、戻り先を示し、ユーザーの事前確認を得る。
- 同一editor内のDOM再確認やscrollは対象切替ではない。ただしURLまたはnote idが変わった場合は即停止する。
- ユーザーが明示選択したBrowser surfaceはtask中の制約。接続や認証に失敗しても無断で別surfaceへ切り替えない。

### 1b. Failure recovery ladder

- `unsupported_capability`、`wrong_or_ambiguous_target`、`authentication_required`、`unexpected_write_or_recovery_uncertain` は同じrouteを再試行しない。
- attach/connection failureは、同一surface・同一targetへの再接続だけ1回許可する。
- selector/viewport driftは、DOM候補を再列挙して同一targetで1 actionだけ再試行する。
- fallback順は `same target re-inspect -> manual/human supervised -> user-approved surface switch -> hold` とする。
- manualまたはhuman supervisedへ渡す時は、対象URL、local file path、完了確認項目、未実行の公開系操作を返す。
- 別surfaceへの自動fallbackは禁止する。新しい対象ロックとユーザー確認が揃ってから別cycleとして開始する。

### 2. Publication gate

- 公開、予約、共有、保存系ボタンは固定座標で押さない。
- `一時保存`、`公開に進む`、共有、予約、投稿は、明示承認がない限り表示確認まで。
- ボタン配置は動的に変わるため、座標ではなく DOM、ラベル、状態で識別する。
- 画面幅、scroll、選択状態により toolbar や button が畳まれる前提で扱う。
- viewport によって DOM 構造、role、aria-label、親子関係、overflow menu 内の位置が変わる前提で扱う。
- 固定 selector / XPath / nth-child だけで対象を決めない。role、label、visible text、aria 属性、disabled 状態、editor root との距離を複合して候補を絞る。
- viewport を変えた後は、前回の DOM path を再利用せず、候補要素を再列挙する。

### 3. Link card embed

- note 公式ヘルプでは、外部サービス URL の貼り付けで埋め込みまたはカード化され、URL 貼り付け後に Enter / Return が必要な場合がある。
- suite の local policy として、Markdown リンクや HTML ではなく、URL を独立段落として入力し、変換後の表示を確認する。
- 既存URL行をその場で自動カード化しない。既存行クリック後の挿入メニューはカーソル位置がずれ、本文上部など意図しない位置へカードや生URLを挿入することがある。
- in-app Browser 実測では、成功 DOM は `figure[data-src="<target URL>"]` と
  子要素 `iframe.note-embed`。raw URL や `a[href]` だけなら失敗扱い。
- 変換対象は、公式、リリース、Discord、マガジンなど、記事ごとの checker に落とせるものは checker に追加する。
- URL 行が通常リンクのまま残る、対象外段落へ入力される、または位置が崩れたら即 Undo で復旧する。
- 事前に cursor / selection が空段落にあることを確認する。本文中や選択ありなら埋め込み操作へ進まない。
- ただし live 実測では変換後の `Control+Z` 1回で embed DOM が残ったため、
  Undo 復旧は保証しない。誤位置なら手動削除/復旧確認へ切り替える。
- 誤位置にカードやURL断片が入ったら、手作業で文字を削り続けない。ローカル正本から本文再反映するか、人間監督で対象ブロックを削除する。

### 3a. Tag operation

- タグチップ本文をクリックして削除できる前提にしない。クリックで同じタグが重複追加される場合がある。
- 削除してよいのは、対象タグのボタン内または近傍に `aria-label="削除"` が確認できる場合だけ。
- `aria-label="削除"` がない既存タグは触らず、手動境界として報告する。
- タグ操作後は、公開設定画面の表示テキストと DOM button 一覧で重複タグがないことを確認する。

### 4. DOM verification

- この節の DOM 成功判定は local checker。公式ヘルプの記述として扱わない。
- 成功判定は表示テキストだけでなく、`figure[data-src="<target URL>"]` または同等の埋め込みDOMで確認する。
- 目次は `table-of-contents contenteditable="false"` と `toc` 属性内の
  H2/H3 heading list で確認する。
- 目次 DOM、H2/H3 heading list、Shift+Enter の `<br>`、Undo 復旧不可は
  2026-06-16 の local live measurement。公式仕様として扱う前に
  `note-official-guidance-intake` で source URL を確認する。
- Shift+Enter は同一 paragraph 内の `<br>` として確認する。
- `href` だけが残る状態は、通常リンク残りとして扱う。
- フッターでは、生URL残り、旧ラベル通常リンク残り、同一URL重複、意図しない段落混入を確認する。
- DOM 確認時は viewport size、scroll position、本文 root、対象 paragraph を closeout に残す。
- 操作対象の候補数、採用した識別子、使わなかった候補、DOM path が viewport 依存だったかを closeout に残す。

### 5. Undo recovery

- Playwright の DOM 座標と CUA の実操作面が同期しないことがある。
- 意図しない段落に入力したら、続けて修正しようとせず、まず Undo で直前の正常状態へ戻す。
- 復旧後に DOM と本文末尾を読み、壊れた文字列が残っていないことを確認する。
- retry可能な同じ失敗が2回続いたら、その操作ルートは使わない。能力非対応や対象不明は初回で停止する。

### 6. Local checker ratchet

- 実測で必要になったURL単独行、CTA、導線、禁止操作は、既存 checker または contract test に落とす。
- checker を追加したら、対象 draft への実行結果まで確認する。
- note側DOM成功とローカルdraft成功は別物として両方確認する。
- 公式機能として扱うものは、先に `references/note-editor-capability-inventory.md` へ source を記録する。
- DOM 判定は公式ヘルプの記述として扱わない。`figure[data-src]` や
  `iframe.note-embed` などの local policy / local checker として記録する。

### 7. Post-publish ledger

- 投稿確定後は `note-postpublish-ledger` を読む。
- 公開URL、JSON-LD の title / published_at / modified_at / image / tags、公開本文スナップショット、`published_notes.json`、`note_drafts.json` を確認する。
- X 投稿、SNS共有、外部告知は別承認がない限り行わない。

### 8. Image upload boundary

- 内部ブラウザ単体の画像アップロード完全自動化は保証しない。
- 実行前に `../../references/note-image-upload-automation-boundary.md` と
  `../../scripts/note_image_upload_boundary_check.py` を確認する。
- Codex in-app Browser が `File uploads are not supported` を返した場合、そこで停止する。画像候補のパスと推奨手動手順だけを返す。
- Chrome、note API、Cookie、セッション読み取り、隠れた画面操作、
  OSフォーカス奪取は使わない。
- 画面に見えている Windows ファイル選択ダイアログだけを扱う場合も、
  現在会話での明示確認があるまで実行しない。
- 公開、予約投稿、SNS共有、外部告知は行わない。

### 9. Prepublish verification

- 公開設定画面に進んだら、最終ボタン名を読む。`投稿する`、`更新する`、予約確定、共有系は未操作にする。
- TOP画像、目次、フッター埋め込み、タグ重複、マガジン追加済み、記事タイプを観測JSONへまとめられる場合は、`../../scripts/note_editor_prepublish_verify.py` で検査する。
- checker が fail の場合でも公開ボタンは押さない。fail項目を手動境界または次cycleとして報告する。

## Closeout Evidence

- attach した URL / note id。
- Browser surface / AI surface。
- viewport size / scroll position / cursor / selection。
- 操作対象の候補数 / 採用した識別子 / DOM path の viewport 依存性。
- 今回の PDCA: Goal / Plan / Do / Check / Act / 次の cycle。
- 触った機能: attach / embed / DOM verification / Undo / checker / ledger。
- 成功判定: `figure[data-src]`、checker結果、台帳件数など。
- 復旧した失敗と再発防止。
- target lock / 対象切替 / ユーザー確認 / failure class / retry count / fallback。
- 未実行の公開、保存、共有、SNS action。
