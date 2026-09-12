---
title: note 下書きエディタの JS（Next.js chunk）静的解析
type: 派生台帳
date: 2026-09-11
method: editor.note.com の公開静的 JS（_next/static/chunks/…）を curl で取得し、grep/python で文字列・構造を読む静的解析。JS は実行していない。下書き本文は読んでいない
external_action: none
tags: [nexa, source, note-preview]
origin_url: ""
topics: []
ported_from: nexa-articles content/nexa-articles/sources/_tools/note-preview/editor-js-analysis.md
ported_at: 2026-09-11
ported_note: 2026-09-11 実測の元ファイルをそのままコピー（内容の改変なし）。取得元 JS チャンク本体（js/ 配下）はサイズが大きいため移植していない。再取得手順は本文中に残す。
---

# note 下書きエディタの JS 静的解析

## 対象ファイル（取得元・実測 2026-09-11）

`https://editor.note.com/` の buildId（`tl6Xvv92QpTHW7f0XtZXU`、実測）の `_buildManifest.js` から
`/notes/[id]/edit` ページの依存チャンクを機械的に特定し、11 件を取得（元リポジトリの `js/` 配下、合計 **約 1.8 MiB / 1,830,325 bytes**）。

| ファイル | 役割（推測、ファイル内容から） |
|---|---|
| `pages/_app-0cabb7de5f24f05c.js` | Next.js `_app`。API パス定数、アカウント/公開系の状態管理を含む |
| `pages/notes/[id]/edit-04c8cc644a72ef1c.js` | edit ページ本体。ツールバー・保存スクロール制御など |
| `462-c361bf0be2328a81.js` | dnd-kit（drag & drop）ライブラリ |
| `0b654695-d9d82d2a83001aa8.js` | prosemirror-view（ProseMirror のブラウザ入力処理本体） |
| `884-4ad875a02b5e7e28.js` | ProseMirror 関連（コマンド・スキーマ補助、`toDOM`/`parseDOM` あり） |
| `57-d5679ec087299b82.js` | **note のエディタ本体**（schema、keymap、挿入メニュー、選択時メニュー、paste 処理。本解析の主対象） |
| `543-fc62a495d1ce808c.js` | 共有ライブラリ（詳細未特定） |
| `568-5518dc96c3432587.js` | 共有ライブラリ（詳細未特定、embed 関連文字列あり） |
| `framework-86821d64971c1a53.js` | React ランタイム |
| `main-f4d4d38a65f2ad05.js` | Next.js ランタイム |
| `webpack-49ae5e3f19fe453a.js` | webpack ランタイム |

以降の抽出結果はほぼ `57-d5679ec087299b82.js`（以下「schema チャンク」）由来。行番号は minify されており無意味なため、コード断片の**文字列リテラル引用は 15 語（トークン）以内**にとどめる。

## 1. ProseMirror schema

note のエディタは ProseMirror 標準の `prosemirror-schema-basic` 相当の**未使用の汎用 schema**（`K=new i.V_({nodes:{doc,paragraph,blockquote,horizontal_rule,heading,code_block,text,image,hard_break},marks:{link,em,strong,code}})`）をライブラリ内に含むが、**実際に editor で使われているのは別の note 独自 schema**（camelCase ノード名、下表）。判別根拠: 挿入メニューの `command` が `p.fK.nodes.tableOfContents` 等 camelCase を参照している。

### ノード（実測: schema 定義から）

| ノード名 | group | 主な attrs | 備考 |
|---|---|---|---|
| `paragraph`（変数 `D`） | block | `align`, `id` | marks: `strong strike link`。`p` の `img` 子要素は除外条件あり |
| `heading` | block | `level`（既定2）, `align`, `id` | marks: `link` のみ。`parseDOM` は `h1`→level 2 に丸め、`h2`→2、`h3`→3（h4-h6 用のparseDOMは無し。H1/H2/H3 のみ許容） |
| `blockquote`（figure 型） | block | `id`, `figcaption` | content: `blockquoteContent blockquoteSource`。DOM は `figure > blockquote + figcaption` |
| `blockquoteContent` | blockquote | — | `figure:not([embedded-service]) > blockquote` |
| `blockquoteSource` | blockquote | — | marks: `strong strike link`。figcaption 相当 |
| `bulletList` | block | `id` | `<ul>` |
| `orderedList` | block | `order`（既定1）, `id` | `<ol>` |
| `listItem` | — | — | content: `paragraph (orderedList\|bulletList)?` |
| `codeBlock` | block | `id` | marks なし（`marks:""`） |
| `horizontalRule` | block | `id` | `<hr>` |
| `image` | block | `src`, `alt`（既定""）, `width`, `height`, `id`, `canvaId`, `style`, `link`, `align` | marks: `strong strike link`。figcaption 用ノードは無い（alt テキストのみ） |
| `embed`（`attachment` と同系） | block | `htmlForEmbed`, `src`/`identifier`, `style`, `embeddedService`, `embeddedContentKey`, `id` | atom / isolating。`figure[embedded-service]` にマッチ。`embeddedService` 実測値: `"note-slide"`（コミック機能）、空文字含む複数種 |
| `paywallLine` | block | `id` | 有料エリア境界線 |
| `tableOfContents` | block | `id` | DOM は `<table-of-contents>`。中身は JS 側で動的生成（本チャンクからは中身描画ロジック未特定） |
| `hardBreak` | inline | — | `<br>` |
| `text` | inline | — | — |

**table ノードは schema に存在しない**（`tableRow`/`tableCell` を含む全チャンクで grep 該当なし）。CSS 側の実測（`editor-dom-analysis.md`）と一致。

### マーク（実測）

| マーク名 | parseDOM | 備考 |
|---|---|---|
| `link` | `a[href]` | attrs: `href`, `title`（別バージョンでは `target`, `rel` も） |
| `strong` | `strong`, `b`（font-weight判定） | 太字 |
| `strike` | `s`, `del`, `strike`, `text-decoration=line-through` | 取り消し線 |
| `em`, `code` | ライブラリ内の未使用 schema にのみ存在 | 実際の note schema（`57`）側には `em`/`code`（インライン）マークが見当たらない。**ruby マークは grep 該当なし（未特定）** |

`ruby` はファイル横断で 6 件ヒットしたが、いずれも schema の `marks:` ブロック外（別の文脈、内容未特定）。README にある「ruby の CSS 規則あり」（editor-dom-analysis.md）と、JS 側で ruby mark 定義が見つからない点は **未確認の食い違い**として記録する。

## 2. メニューの種類と出現条件

### 2a. 挿入メニュー（「＋」/ `/`）

`rn` 配列（`57` チャンク）が挿入メニュー全項目。

| ラベル | icon | 生成ノード/挙動 |
|---|---|---|
| AIアシスタント | ai | `openAssistantsModal()` |
| 画像 | image | `<input type=file>` を動的生成しクリック |
| 音声 | headphones | `openSoundUploadModal()` |
| 埋め込み | link | URL 入力→embed 変換 |
| ファイル | file | ファイル添付 |
| コミック | comic | `openComicUploadModal()`（`embeddedService:"note-slide"`） |
| 目次 | toc | `tableOfContents` ノード挿入 |
| 大見出し | h2 | `heading level:2` |
| 小見出し | h3 | `heading level:3` |
| 箇条書きリスト | bulletedList | `bulletList` |
| 番号付きリスト | orderedList | `orderedList` |
| 引用 | quote | `blockquote`（figure型） |
| コード | code | `codeBlock` |
| 区切り線 | separate | `horizontalRule` + 空段落を挿入 |
| 有料エリア指定 | enLine | `paywallLine`（有料境界） |

**出現条件（実測）**: `handleKeyDown` で `"/"===key && window.innerWidth>=768 && n8(selection)` のとき挿入メニューをトグルする処理がある。**スラッシュコマンドは存在するが、viewport 幅 768px 以上でのみ有効**（`n8` の具体条件＝カーソル位置の判定は未特定、恐らく空段落先頭）。768px 未満では「＋」ボタン経由のみと推測される（未確認）。

### 2b. 選択時のバブルメニュー（テキスト選択）

同じ `rf` 配列をノード種別で `.filter()` して出し分ける。判定変数（`57` チャンク内の1関数）:

- `f`（image ノード選択） → `["link","resizeImageUp","resizeImageDown","imageAlignLeft","alt","trash"]` のみ表示。`selectedNode:"image"`
- `g||v`（`embeddedService==="note-sound"` または `"note-slide"` の embed 選択） → `["create","trash"]`（"編集"/"削除"、ラベルは音声/コミックで文言分岐）
- `y||b`（通常テキスト選択、または blockquoteSource 選択） → `["bold","strike","link"]` のみ
- `u||a`（image/embed が `!false===EG(selection)` で判定される「ノード混在 or 単独ノード」状態） → 選択範囲が空文字のみなら `["trash"]`、そうでなければ `["ai","trash"]`
- それ以外 → フル項目（見出しレベル選択、太字、取り消し線、リスト種別、文章の配置、リンク、引用、コード、`.command(state)` が真の項目のみ）

`selectedNode` は `"image"|"mixed"|"node"|"text"` の4値。

### 2c. 画像/figure 選択時のメニュー

image ノード単独選択時: リンク付与・拡大/縮小（`resizeImageUp`/`resizeImageDown`、`attrs.width<620` で align 制御の可否分岐）・左右中央寄せ・**代替テキスト**（`icon:"alt"`, `label:"代替テキスト"`）・削除。**figcaption / キャプション編集項目は image ノードには無い**（figcaption 相当は blockquote 型ノードのみに存在）。

### 2d. リンク編集ポップオーバー

バブルメニューの `link` マーク項目 `command:eW(rs)` が呼ばれる（`rs` はリンク編集用の何らかの state/モーダル、実体は本チャンク内に定義を特定できず**未特定**）。

### 2e. 右クリック（context menu）

`57`/`0b654695`/`462`/`framework` チャンクで `contextmenu` 文字列は計7件ヒットするが、いずれも ProseMirror の内部イベント処理（IME 確定検知）または dnd-kit のドラッグセンサー定義であり、**note 独自の右クリックメニュー実装は見つからなかった**（＝ブラウザ既定の右クリックメニューがそのまま出ると推測されるが、確証なし。未確認）。

### 2f. スラッシュコマンド

2a に記載のとおり**存在する**（`"/"` キー押下で挿入メニュートグル）。ただし発火条件に `window.innerWidth>=768` が明示されており、**デスクトップ幅限定**という制約付き。

## 3. キーボードショートカット（keymap、実測）

`57` チャンクの `r9` 関数がショートカット一式を合成する。

| キー | 動作 |
|---|---|
| `Mod-z` | Undo |
| `Mod-y` / `Mod-Shift-z` | Redo |
| `Mod-b` | 太字トグル |
| `Mod-Shift-x` | 取り消し線トグル |
| `Mod-Alt-0` | 段落に変換 |
| `Mod-Alt-2` | 見出し2（H2） |
| `Mod-Alt-3` | 見出し3（H3） |
| `Mod-Alt-\` | コードブロックに変換 |
| `Mod-Shift-e`/`l`/`r` | 文章配置（中央/左/右） |
| `Mod-Enter` / `Shift-Enter` | `hardBreak`（`<br>`）挿入 |
| `Mod-[` / `Mod-]` | リストのインデント上げ/下げ |
| `Tab` / `Shift-Tab` | リストインデント |
| `Mod-Shift-7` / `Mod-Shift-8` | 箇条書き⇔番号付きリスト切替 |
| `Mod-Shift-\` | 不明動作（`tg` 未特定） |
| `Alt-ArrowUp` / `Alt-ArrowDown` | ノード移動（ProseMirror標準 join/lift系） |
| `Mod-BracketLeft` | 標準リフト |
| `Escape` | メニュー等を閉じる（`rQ`） |

### 入力ルール（Markdown 風・タイピング時オートコンバート、実測）

`nU` 関数が input rules を定義（ProseMirror の `InputRule`。**タイピング中**に発火）:

- `> ` → `blockquote` へ変換
- `1. ` 等の数字+`. ` → `orderedList`
- `- ` / `+ ` / `* ` → `bulletList`
- `` ``` `` → `codeBlock`
- `##`/`###` 相当（`nH(heading,2,2)` と `nH(heading,2,3)`、具体的なトリガー文字列は関数実装側で定義され本抽出では未特定だが、見出しレベル2/3への変換ルールが2件存在） → 見出し
- `---` → `horizontalRule`（行頭かつ段落選択時のみ）
- URL 文字列（`nP(link)`） → リンクマーク自動付与
- `**text**` / `__text__` → 太字（削除→再マーク方式）
- `~~text~~` → 取り消し線

**既存の `note-editor-live-constraint-boundaries.md`（2026-06-16 実測）との食い違い**: 同ドキュメント4節は「automation surface（Playwright/dom_cua）で `# Heading`/`## Heading` を入力しても H2/H3 に変換されなかった」と記録している。今回の静的解析では見出し用の input rule 自体は**コード上に存在する**ことを確認した。両者は矛盾するのではなく、対象が異なる可能性が高い（automation のキー入力イベントが input rule の発火条件を満たさない、または `nH` の実際のトリガー文字列が `# `/`## ` と一致していない、のいずれか＝**未確認**）。実運用の判断は live-constraint-boundaries.md を優先する。

### 貼り付け時の変換（typing 用 input rule とは別経路、実測）

- `transformPastedHTML: e=>e.replace(/\xA0/g," ")` — note 独自の HTML paste 変換は**改行のみ／nbsp を半角スペースに正規化するだけ**で、他の変形は無い（table・h1・h4・iframe・style を能動的に除去する専用ロジックは見当たらない）。ただし貼り付け HTML は最終的に note の schema でパースされるため、schema にないタグ（`table` 等）は ProseMirror の DOM parser 段階で自動的に無視/フォールバックされると推測される（**未確認**、具体挙動は `note-editor-live-constraint-boundaries.md` 5節の実測 [text/html paste で h2/h3/p/ol/li が対応ノードに変換された] を優先する）。
- プレーンテキスト貼り付け（`clipboardTextParser`）は **markdown-it（"commonmark" プリセット、`html:false`）でパースされる**。トークン→ノード対応表（実測）:
  - `blockquote`→blockquote、`paragraph`→paragraph、`list_item`→listItem、`bullet_list`→bulletList、`ordered_list`→orderedList（`start`属性継承）
  - `heading`→heading（**h1は2に、h4以上は3に丸め**: `level<2?2:level>3?3:level`）
  - `code_block`/`fence`→codeBlock、`hr`→horizontalRule、`image`（`![]()`構文）→image
  - `hardbreak`/`softbreak`→hardBreak
  - `s`（`~~~~`）→strike mark、`strong`（`**`）→strong mark、`link`→link mark
  - **`em`（`*italic*`）と `code_inline`（`` `code` ``）は `ignore:!0` で破棄される**（イタリック体・インラインコードはプレーンテキスト貼り付けでは再現されない）
- 画像・embed の URL 貼り付けは重複排除ロジックあり（`lT`/`lH` が既存 doc 内の `src`/`embeddedContentKey` と比較し、重複分はアップロード処理をスキップ）。
- クリップボードの画像アイテム（`clipboardData.items` の image type）を検出してアップロードする `handlePaste` プラグインが別途存在（drag&drop や OS クリップボード画像を想定）。

## 4. 応答レイアウト（ブレークポイント）

### CSS（`editor-9db03725.css`、実測: メディアクエリ一覧）

```
@media (min-width:1280px)
@media (min-width:2048px)
@media (min-width:361px)
@media (min-width:481px)
@media (min-width:769px)
@media (min-width:941px)
@media only screen and (max-width:360px)
@media only screen and (max-width:480px)
@media only screen and (min-width:481px) and (max-width:768px)
@media only screen and (min-width:769px)
```

このファイルは Tailwind のユーティリティクラス集合体（クラス名がハッシュ化されておらず、`fixed`/`bottom-0` 等の一般語で構成）で、`toolbar` という文字列自体は含まれない。**ツールバーの位置切り替えを担う専用セレクタは本 CSS からは特定できなかった**（未特定。DOM 上のクラス名突合が必要）。

### JS 側の viewport 判定（実測）

- `window.innerWidth>=768` — `/` キーで挿入メニューを開けるかどうかの判定にのみ使用（2a節）。**768px がデスクトップ/モバイルの実質的な境界値**と推測される（CSS 側の `min-width:769px` / `max-width:768px` の対と符合）。
- `window.innerWidth>480` — 下書き保存バー（"保存先を変更しました" 等の UI）のスクロール判定用オフセット計算（50px vs 0px）。レイアウト切替そのものではない。
- バブルメニューの位置は `matchMedia` ではなく **`ProseMirrorView.coordsAtPos()` で選択範囲の画面座標を都度計算**し、`left`（中央寄せ）/`top`/`mobileTop` の3値を CSS 変数的にセットする方式（`rK` 関数）。`#desktop-toolbar` という id 要素が存在し、その `top` スタイルを選択位置に応じて直接書き換えている（固定配置ではなく選択追従型）。**「幅によってパネルが下に出たり左に出たりする」という現象は、この `mobileTop` フィールド（別の CSS が幅条件で `top`/`mobileTop` のどちらを使うか切り替えている可能性）が対応すると推測されるが、実際にどちらを表示に使うかの分岐は CSS 側にあり、本 JS からは断定できない（未確認）。**

### 推測される結論（要検証）

- 769px 以上: PC 前提のツールバー・スラッシュコマンド有効
- 768px 以下: モバイル/タブレット前提。スラッシュコマンド無効、`mobileTop` 座標を使ったパネル表示（下部固定の可能性が高いが未確認）
- 480px 以下・360px 以下: さらに小さい画面向けの微調整（padding 等、CSS 側で断片的に確認、詳細は本解析の範囲外）

## 5. 保存・公開 API（URL パターンのみ、token/cookie は記録しない）

実測（`_app-0cabb7de5f24f05c.js` の文字列リテラル）:

- `/v1/notes/`
- `/v1/text_notes`
- `/v1/text_notes/draft_delete`
- `/v1/text_notes/draft_save`
- `/v2/notes/`
- `/v3/notes`
- `/v3/notes/`
- `/v3/notes/reserved`
- `/v3/notes/sellable_potential`
- `/v3/members/owner_notes/circle_permissions`
- `/v3/members/owner_notes/magazines`
- （`edit-04c8cc644a72ef1c.js` にも `/notes/` 参照あり、詳細未特定）

`draft_save`/`draft_delete` が下書き保存・削除に対応すると推測される（命名から。実際のリクエスト payload は未確認・未取得）。

## 未確認・保証しないこと

- `n8`（`/` キーの発火条件関数）、`rs`（リンク編集の実体）、`tg`（`Mod-Shift-\`）、`nH` の具体的トリガー文字列、`table-of-contents` の中身描画ロジックは、いずれも変数名が難読化されており本解析では実体を特定できなかった。
- `ruby` マークの schema 定義は本チャンク群からは見つからず、CSS 側の「ruby 規則あり」（editor-dom-analysis.md）との整合は未確認。
- CSS のツールバー位置切替セレクタは特定できていない（Tailwind ユーティリティクラスと DOM クラスの突合が別途必要）。
- 543 / 568 チャンクの役割は文字列断片からの推測に留まり、確定していない。
- 取得した JS はビルドハッシュが note 側の更新で変わるため、再取得時は本ファイル冒頭の buildId 取得手順（`_buildManifest.js`）をやり直す必要がある。
- 取得元 JS チャンク本体（元リポジトリの `js/` 配下、約 1.8 MiB）はこの移植先には含めていない。再取得方法は元ファイルの README（`sources/_tools/note-preview/README.md`）を参照。
