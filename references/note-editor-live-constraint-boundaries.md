---
title: note editor live constraint boundaries
type: reference
status: active
created: 2026-06-16
source_scope: local live editor measurement
publication_action: none
---

# note editor live constraint boundaries

## 目的

`note-editor-constraint-debug` で実測した note editor の挙動を、
再現手順、成功判定、復旧可否、手動境界、contract test の根拠として残す。
この file は公式ソースではなく local observation。公式扱いする前に
`note-editor-capability-inventory.md` の公式ソース欄と照合し、
必要なら `note-official-guidance-intake` へ戻す。

## 実測条件

- date: 2026-06-16
- Browser surface: in-app Browser
- AI surface: Codex main
- URL: `https://editor.note.com/notes/.../edit/`
- viewport: default in-app Browser viewport
- note 操作: 新規下書き editor へのテスト入力のみ
- 未実行: 公開、投稿、予約確定、SNS 共有、外部告知、repository visibility 変更
- 押していないボタン: `下書き保存`、`公開に進む`

## 1. Shift+Enter

```text
constraint: Shift+Enter line break
surface: in-app Browser / ProseMirror body
cursor_or_selection: body textbox focused, no selection
goal: 段落内改行として入るか確認する
action: `ShiftEnter A` を入力し、Shift+Enter、`ShiftEnter B` を入力
expected: 同一段落内の改行
actual: 同一 `p.paragraph` 内に `<br>` が1件入り、paragraph count は1
dom_or_visible_evidence:
  <p class="paragraph">ShiftEnter A<br>ShiftEnter B</p>
recovery: 破壊的変更なし。Undo 復旧は不要
manual_boundary: なし
ratchet: Shift+Enter は paragraph split ではなく `<br>` として確認する
```

## 2. URL embed

```text
constraint: URL embed
surface: in-app Browser / ProseMirror body
cursor_or_selection: body textbox focused, URL paste before trailing blank position
goal: URL 単独行 + Enter がリンクカードへ変換されるか確認する
action:
  1. URL `https://note.com/info/n/n4abb4e998dfc` を入力
  2. Enter
  3. 約8秒待機して DOM 確認
expected: raw URL や `href` だけではなく embed DOM へ変換される
actual:
  - `figure[data-src="https://note.com/info/n/n4abb4e998dfc"]` が生成された
  - 子要素に `iframe.note-embed` が生成された
  - raw URL count は0、通常 `a[href]` は0
dom_or_visible_evidence:
  <figure data-src="https://note.com/info/n/n4abb4e998dfc"
          embedded-service="note" contenteditable="false">
    <iframe class="note-embed" src="https://note.com/embed/notes/n4abb4e998dfc">
  </figure>
recovery:
  - 変換後に本文 root を focus して `Control+Z` を1回実行しても figure は残った
  - この surface では embed 変換後の Undo 復旧を保証しない
manual_boundary:
  - 誤位置に embed された場合、追加編集で直す前に人間が画面上で削除/Undo を確認する
  - 自動化 closeout では `figure[data-src]`、raw URL、`a[href]`、重複を必ず報告する
ratchet:
  - URL embed 成功条件は `figure[data-src]` と `iframe.note-embed`
  - `href` だけ、raw URL 残り、重複 URL は失敗扱い
```

## 3. Table of contents

```text
constraint: table of contents
surface: in-app Browser / insertion menu
cursor_or_selection: body textbox focused, trailing blank paragraph
goal: 見出し階層と目次 DOM を確認する
action:
  1. `メニューを開く`
  2. `大見出し` を選び `Measured Big Heading` を入力
  3. `メニューを開く`
  4. `小見出し` を選び `Measured Small Heading` を入力
  5. `メニューを開く`
  6. `目次` を選択
expected: 見出しを参照する目次 block が本文 DOM に入る
actual:
  - `大見出し` は `H2`
  - `小見出し` は `H3`
  - `table-of-contents contenteditable="false"` が本文 DOM に入る
  - `toc` 属性に H2/H3 の text、level、id が入る
dom_or_visible_evidence:
  <h2 id="...">Measured Big Heading</h2>
  <h3 id="..." class="heading">Measured Small Heading</h3>
  <table-of-contents contenteditable="false" toc="[...]"></table-of-contents>
recovery:
  - 挿入後に本文 root を focus して `Control+Z` を1回実行しても
    `table-of-contents` は残った
  - この surface では目次挿入後の Undo 復旧を保証しない
manual_boundary:
  - 目次位置を誤った場合、人間が画面上で削除/移動を確認する
  - 自動化 closeout では `table-of-contents` 件数と H2/H3 件数を必ず報告する
ratchet:
  - 目次成功条件は `table-of-contents` と `toc` 属性内の heading list
  - 見出し作成は Markdown 風入力ではなく挿入メニューを優先する
```

## 4. Enter and heading shortcut caveat

```text
constraint: automation Enter / heading shortcut caveat
surface: Playwright locator and dom_cua keypress
goal: automation surface で Enter がどう DOM に反映されるか確認する
actual:
  - Playwright `press("Enter")` と `dom_cua.keypress(["ENTER"])` は、
    通常テキストでは同一 paragraph 内の `<br>` として観測された
  - `# Heading` / `## Heading` の Markdown 風入力では H2/H3 に変換されなかった
manual_boundary:
  - live editor の見出し作成は挿入メニューの `大見出し` / `小見出し` を使う
  - 段落分割や改行の保証は、実操作面ごとに DOM 確認する
  - この結果は 2026-06-16 の local observation であり、公式仕様として扱わない
ratchet:
  - automation surface で Enter の一般段落分割を保証しない
  - URL embed、見出し、目次はそれぞれ専用 DOM 成功条件で判定する
```

## 5. HTML paste による block 生成

```text
constraint: text/html paste
surface: cmux browser / ProseMirror body
date: 2026-07-13
goal: 記事全体を見出し・段落・箇条書きの block 構造を保って投入する
action:
  - DataTransfer に text/html と text/plain を設定する
  - ClipboardEvent('paste') を ProseMirror body へ dispatch する
actual:
  - text/html では h2 / h3 / p / ol / li が対応する block node として生成された
  - text/plain だけでは全段落が1 block に潰れた
manual_boundary:
  - paste 後に H2 / H3 / paragraph / list の件数を DOM で照合する
  - 下書き保存、公開、予約投稿は別 gate とする
ratchet:
  - 構造化本文の一括投入では text/html を必須にする
  - text/plain 単独 paste を構造保持 route として扱わない
```

## 6. hidden WebView の入力境界

```text
constraint: hidden WebView input
surface: cmux browser
date: 2026-07-13
actual:
  - WebView hidden 時は browser press / click が届かず、focus-webview は invalid_state になった
  - DOM eval は到達し、ProseMirror への synthetic keydown は処理された
  - Mod-a + Backspace では本文選択と削除が成立した
  - document.execCommand('delete') は contenteditable=false の figure を消し残した
manual_boundary:
  - synthetic keydown は対象 editor と DOM 状態を確認した限定操作にする
  - execCommand('delete') は使わない
ratchet:
  - hidden WebView では実キー入力の成功を保証しない
  - figure を含む全選択削除は ProseMirror keymap 経由で行い、残存 figure を検査する
```

## 7. DOM selection と paste の tick 境界

```text
constraint: DOM Range selection synchronization
surface: cmux browser / ProseMirror body
date: 2026-07-13
actual:
  - Range.selectNodeContents() と paste を同一 tick で実行すると挿入位置が末尾へ飛んだ
  - selection と paste の間に1 tick以上置くと ProseMirror state が選択を取り込んだ
ratchet:
  - DOM selection 直後の同一 tick paste を禁止する
  - 1 tick以上待ち、paste 後に先頭・末尾 marker と block 件数を確認する
```

## 8. 連続画像と CDN 取り込み

```text
constraint: consecutive images and remote CDN import
surface: cmux browser / ProseMirror body
date: 2026-07-13
actual:
  - <p><img></p><p><img></p> の連続画像は1枚目が消え、2枚目だけ残った
  - 画像間に <p><br></p> を置くと両方残った
  - assets.st-note.com の既存 CDN URL は5枚中1枚を取りこぼした
manual_boundary:
  - 画像間に空 paragraph を置き、投入後の画像件数と順序を照合する
  - remote CDN URL の再取得を完全経路として保証しない
ratchet:
  - 連続画像には空 paragraph separator を必須にする
  - 確実性が必要な画像は local File paste route を使う
```

## Contract test boundary

自動テストで live editor を直接再実行することはしない。代わりに、この
reference と skill が次の測定済み境界を持ち続けることを contract test で確認する。

- `figure[data-src]`
- `iframe.note-embed`
- `table-of-contents`
- `toc` 属性
- `H2` / `H3`
- Shift+Enter の `<br>`
- Undo 復旧を guarantee しない手動境界
- `text/html` paste と `text/plain` paste の構造差
- hidden WebView の synthetic keydown 境界
- DOM selection と paste の間の 1 tick
- 連続画像の空 paragraph separator
