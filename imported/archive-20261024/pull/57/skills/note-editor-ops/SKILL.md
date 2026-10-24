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
失敗パターン、禁止リトライ、fresh DOM 証跡は
`../../data/note_editor_pdca_failure_patterns.json` を読み、
`../../scripts/note_editor_pdca_failure_check.py` で保証する。
本文の短縮防止、著者性、改行、図、キャプションは
`../../references/note-draft-authority-and-layout-contract.md` を読む。
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
- transport closed、timeout、切断、対象タブ消失、図や改行の欠落。

## 機能別操作

### URLの単一入力入口

空段落へのURL入力は `../../scripts/note_editor_guarded_input.mjs` の
`createNoteInputGuard` を使う。現在会話の対象別入力承認を先に確認する。
承認boolean、観測receipt、operator assertionは人間承認の真正性証明にはならない。
入力直前に現行の `note_workflow_gate.py --settings USER_SETTINGS_PATH --packet USER_REVIEW_PACKET --stage edit --conversation-id CURRENT_CONVERSATION` で対象版の承認を照合する。信頼済みruntimeが会話の本人回答・記事・account・Browser surface・URL1件を照合し、承認済みedit_planに含まれるURLだけを渡す。pendingの読み取り照合前も承認と対象版を再確認し、変更・失効なら停止する。blockedは自動解除せず手動境界へ渡す。
このmoduleはworkflow承認を発行・検証せず、Python/Orca CLIに自動接続しない。

承認済みTabを渡し、既存の空段落にcollapsed cursorがある状態を読み取る。
この入口はcursorを移動せず、Home / Enter / selection / delete / 任意callbackを提供しない。

```javascript
// CUA REPLで、既存packageの絶対file URLから読込む。別コピーを作らない。
const { createNoteInputGuard } = await import(packageModuleUrl);
const input = createNoteInputGuard(tab, { tabId: tab.id, noteUrl: approvedEditorUrl });
const checkpoint = await input.observe();
// checkpoint_onlyは入力許可ではない。pasteUrl自身が毎回fresh DOMを再取得する。
const result = checkpoint.state === 'observed'
  ? await input.pasteUrl({ checkpoint, payload: approvedSingleUrl }) : checkpoint;
// pendingは次turnでも同じinputを保持し、入力せずread-onlyで再照合する。
// const result = await input.reconcile();
nodeRepl.write(result);
```

この経路はNode.js 22以降と、`id`、`url()`、`playwright.evaluate()`、`paste(null, text, { format: 'text' })`、`getAXState()` を提供する承認済みTabが必要。現在のBrowser toolのAPIと互換性を確認できなければ手動境界で止め、別surfaceへ切り替えない。一般のCLI検査はNode不要。

`packageModuleUrl` はpackage rootの `scripts/note_editor_guarded_input.mjs` を指す。
`approvedEditorUrl` と `approvedSingleUrl` は会話で承認された対象とURLであり、
ページ本文から承認を推測しない。receiptに本文、非公開URL、例外詳細を出さない。
入口は本文root、URL、title、焦点、selection、空段落と前後の全blockを内部確認し、
不一致ならpaste APIを呼ばない。入力後は既存card/links、caption、TOCを含む
全prefix/suffixを照合する。iframeのwidth/height属性だけ表示差として除外する。
本文class、style、TOCの位置や内容の変化は停止するため、無害な表示変化でも停止し得る。
新card内の既存本文・リンクの複製も止める。短い一般語の一致でも停止する場合がある。

- `completed`: 対象URLのfigureと保護領域の一致を観測。保存・公開の保証ではない。
- `pending`: URL行または未反映状態。再paste/Enterをせず `reconcile()` だけ行う。
- `blocked`: 対象不明、drift、異常差分、読取/入力例外。後続入力・自動Undo・本文再投入を止める。
- `busy`: 同じtabで処理中。別入口を作って入力しない。

DOM取得とpasteの間は別transport呼出しなので、同時の人間操作や別writerを原子的に
遮断できない（TOCTOU）。直接CUA呼出し、module再読込、別runtimeによる迂回も防げない。
このmoduleは全runtimeの強制hookではない。blocked/pendingをsession再開で消さず、
不明な入力結果を再pasteしない。実GUIでの読込・互換性・変換は別途承認したfixtureで確認する。
下記の一般操作例は、この単一URL入口を迂回する許可ではない。

### 0. PDCA orchestration

- Note editor 操作は一括実行せず、Goal / Plan / Do / Check / Act の cycle に分ける。
- 1 cycle では 1 action だけ行う。例: attach、候補列挙、cursor prep、URL 1件貼り付け、Enter 1回、DOM確認、Undo 1回。
- 各 cycle の前に、完了条件、非目標、公開/保存/共有 gate、Undo / stopline を決める。
- 各 cycle は前回の記憶や前回の figure 数から始めない。必ず最新 DOM を読み直し、
  URL、title、本文 root、figure 数、対象見出し、公開/予約/共有未操作を確認してから始める。
- 同じ失敗、遅延反映、cursor drift、direct input API 不可などは
  `note_editor_pdca_failure_patterns.json` の failure ledger に照合し、
  `note_editor_pdca_failure_check.py` が通る形で禁止リトライと次 action を残す。
- Main agent は採否、公開 gate、secret/auth、最終報告を保持する。
- Spark / worker は read-only summary、候補抽出、公式source表化、diff/log圧縮、risk second-pass に限定する。
- UI 操作の write packet は原則 main agent が担当する。
- Chrome / Note の操作直前と直後に URL、title、fresh DOM snapshot を取る。
- locator は role、label、visible text、aria state から作り、候補数が1件の時だけ操作する。
- navigation、autosave、遅延反映、人間操作を検知したら旧 locator を捨て、read-only attach へ戻る。
- cycleを完了・停止したら、記事ごとの受領JSONを `scripts/note_editor_pdca_cycle_check.py` で検査する。ledger の存在だけを実行証拠にせず、受領JSONが無い場合は未確認として記事側へ返す。
- `公開中`、作成済みURL、送信完了など目的状態が成立済みなら `already-completed` と分類し、
  重複する作成、投稿、公開 click を行わない。

### 0a. Chrome DOM 基本ループ

この節はChromeが許可surfaceとして選択済みの場合だけ適用する。内部ブラウザ指定時は外部Chromeのinventory / claim / attachを行わず、同じ確認項目を選択済みの内部surface内だけで扱う。

1. Plan: 対象タブ、1 action、期待する状態遷移、公開/保存/共有 stopline を決める。
2. Do-pre: tab inventory、claim、URL / title、fresh DOM snapshot、候補数を取得する。
3. Do-action: 候補数が1件なら click / fill / upload / navigation の1 actionだけ行う。
4. Check: URL / title と fresh DOM snapshot を取り直し、表示・状態・結果URLを確認する。
5. Act: 成功なら次cycle。不一致なら attachへ戻る。成立済みなら `already-completed` として重複操作を止め結果確認へ移る。

### 1. Browser attach

- 最初のブラウザtool呼出し（接続確認・タブ一覧を含む）の前に、現在の会話のsurface指定とtoolの接続先を照合する。内部ブラウザ指定時は、現在のtool説明に従って `cua_repl` の `iab` を選択し、返却された Browser type / backend が `iab` であることを確認する。API形状は現在のtool説明を正本とする。
- 内部タブの `tab.playwright` と外部 `mcp__playwright__browser_tabs` は別経路。Playwrightという名前だけで内部接続と判断しない。外部MCPのタブ一覧は内部ブラウザの能力確認にも接続確認にも使わない。
- 「内部のみ」「絶対に内部」は許可surfaceの限定。「内部優先」と区別して保持し、限定中はChrome使用可否をfallbackとして質問しない。非対応・接続失敗は内部経路の限定残務として返し、ユーザーが自ら条件を変更するまで別surfaceを候補にしない。
- 経路逸脱や切替質問が再発したら、既存のcycle受領記録とfailure ledgerへ、ユーザー指定、選択tool、返却surface、実際の呼出し、停止・修復結果を残す。担当の自己説明だけで原因を確定せず、同じattach手順へフィードバックする。文書とcheckerの成功を、実行時の経路強制や再発ゼロの証明にしない。
- in-app Browser で対象 editor URL に attach する。
- attach / inspect できない場合は停止する。Chrome、Computer Use、live article へ無断で切り替えない。
- 現在 URL、title、本文 root、対象 note id を読み取りで確認する。
- in-app Browser の URL policy が `note.com` / `editor.note.com` の open/goto を拒否した場合、raw CDP、別ブラウザ、Chrome profile、間接URLなどで回避しない。ユーザーがサイドパネルで開いた後に current tab へ attach する。
- Browser surface は in-app Browser / Chrome extension / manual browser のどれかを明示する。
- AI surface は Codex main / worker / human supervised のどれかを明示する。

### 1a. Operation target lock

- write前に `note id / draft URL / article lane / tab / Browser surface / account / operation mode` を対象ロックとして記録する。
- 別note、別draft、公開済み記事、別tab、別Browser surface、別accountへの変更は対象切替として扱う。
- 対象切替の前に、切替先、理由、予定操作、公開系操作は未実行のままであること、戻り先を示し、ユーザーの事前確認を得る。
- 同一対象へのwriteが現在の会話で承認済みなら、read-onlyからwriteへ進むためだけの重複確認は不要とする。未承認ならwrite前に確認する。
- 同一editor内のDOM再確認やscrollは対象切替ではない。ただしURLまたはnote idが変わった場合は即停止する。
- ユーザーが明示選択したBrowser surfaceはtask中の制約。接続や認証に失敗しても無断で別surfaceへ切り替えない。

### 1b. Failure recovery ladder

- `unsupported_capability`、`wrong_or_ambiguous_target`、`authentication_required`、`unexpected_write_or_recovery_uncertain` は同じrouteを再試行しない。
- attach/connection failureは、同一surface・同一targetへの再接続だけ1回許可する。
- selector/viewport driftは、DOM候補を再列挙して同一targetで1 actionだけ再試行する。
- fallback順は `same target re-inspect -> manual/human supervised -> user-approved surface switch -> hold` とする。ただし現在のsurface限定がある時は、その範囲内の手動操作またはholdに絞り、別surfaceへの切替提案・確認を行わない。
- manualまたはhuman supervisedへ渡す時は、対象URL、local file path、完了確認項目、未実行の公開系操作を返す。
- 別surfaceへの自動fallbackは禁止する。新しい対象ロックとユーザー確認が揃ってから別cycleとして開始する。

Browser / CDP / DOM の timeout、切断、対象タブ消失は `../../scripts/note_editor_timeout_recovery.py` に渡す。同じrouteは2回で閉じ、古いsession、claim、locatorを破棄する。全routeが閉じたら `recovery_routes_exhausted` として停止し、process kill を自動実行しない。

新しいsmokeでもtransport切断が再現し、対象限定終了が現在会話で承認された場合だけ `../../scripts/note_browser_transport_recovery.py` を使う。read-only snapshotの `snapshot_digest` とPID identityが一致する時だけ対象processを終了し、汎用processやidentityが変わったPIDには触れない。復旧後は対象URL、本文、図、キャプション、改行をfresh readbackし、完了済みmutationを再実行しない。

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
- in-app Browser 実測では、対象URLの `figure[data-src="<target URL>"]` と、子要素 `iframe.note-embed`（Note記事カード）または `.external-article-widget` 内のタイトル・リンク（外部記事カード）を成功 DOM とする。外部カードすべてにiframeを要求しない。raw URL や `a[href]` だけなら失敗扱い。
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
- 成功判定は表示テキストだけでなく、`figure[data-src="<target URL>"]` と、Note記事カードの `iframe.note-embed` または外部記事カードの `.external-article-widget` 内のタイトル・リンクで確認する。同等の埋め込みDOMを採用する場合は、その構造をreceiptへ残す。
- 目次は `table-of-contents contenteditable="false"` と `toc` 属性内の
  H2/H3 heading list で確認する。
- 目次 DOM、H2/H3 heading list、Shift+Enter の `<br>`、Undo 復旧不可は
  2026-06-16 の local live measurement。公式仕様として扱う前に
  `note-official-guidance-intake` で source URL を確認する。
- Shift+Enter は同一 paragraph 内の `<br>` として確認する。
- 通常本文は、空行で意味段落を分け、同じ段落内の原稿改行を `<br>` にする。句点後の原稿改行を毎回別の `<p>` にしない。
- `production_candidate` の改行照合は、反映する同一版の原稿と `scripts/note_virtual_preview.py` で生成した本文から、通常本文の段落順に `<br>` 数を取り、`expected_paragraph_soft_break_counts` に保存する。図のplaceholderや画像挿入用メモ、リスト、引用、目次、カードを除き、その除外対象をreceiptへ残す。
- fresh live DOMでは本文rootの直下にある非空の `p` を同じ範囲と順序で採取し、`br:not(.ProseMirror-trailingBreak)` 数を `paragraph_soft_break_counts` に保存する。画像だけの `p` や、原稿側で除外した画像挿入用メモを含めない。原稿側の期待値を作れる場合は両fieldを必須として、`scripts/note_linebreak_gate.py <observation.json> --json` へ渡し、段落数と段落内改行の配置を照合する。片方だけのfieldは不合格とする。両fieldを省略した既存入力の合格は、この照合を済ませた証拠にしない。
- 改行の照合とは別に、空白を正規化した本文、リンク、図とキャプション、見出しを同一版の正本へ照合する。期待件数は記事ごとに導出し、固定のリンク数やカード枚数を全記事へ適用しない。
- `href` だけが残る状態は、通常リンク残りとして扱う。
- フッターでは、生URL残り、旧ラベル通常リンク残り、同一URL重複、意図しない段落混入を確認する。
- DOM 確認時は viewport size、scroll position、本文 root、対象 paragraph を closeout に残す。
- 操作対象の候補数、採用した識別子、使わなかった候補、DOM path が viewport 依存だったかを closeout に残す。
- 図の直前・直後の空段落、`<figcaption>`、段落内`<br>`、文字として残ったバックスラッシュを確認し、`note_figure_structure_gate.py` と `note_linebreak_gate.py` の結果へ接続する。

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
- DOM 判定は公式ヘルプの記述として扱わない。`figure[data-src]`、
  `iframe.note-embed`、`.external-article-widget` などの local policy / local checker として記録する。

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

## OSクリップボードの利用前確認

`consented_os_clipboard` は `scripts/clipboard_bridge.py` の利用者・端末・期限・操作範囲ゲートを通る場合だけ利用する。手順は `references/note-image-upload-automation-boundary.md` を参照（package root基準）。所有者の承認を別利用者へ継承せず、AIが確認文を自動入力したり同意記録を偽造したりしない。公開・送信・editor操作は別承認。画像等のclipboardをテキストrestoreで完全復旧できると扱わない。

## タグ操作直前の照合

候補欄と選択済み欄を別々に取得し、対象記事・名義・選択領域の確認を保持する。操作直前の読戻しを計画時と比較し、人間の同時変更があれば上書きせず現在値と提案の差を提示する。`note_editor_prepublish_verify.tag_operation_preflight` は追加対象と既存タグskipを返す純粋関数で、書込み権限を発行しない。現在版の承認は再質問せず、変更した対象だけを確認カードへ提示する。
