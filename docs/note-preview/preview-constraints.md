---
title: 仮想 note preview が守るべき制約（editor JS/CSS 静的解析から）
type: 派生台帳
date: 2026-09-11
method: editor-js-analysis.md / editor-dom-analysis.md / note-article-dom-analysis.md の実測を突き合わせて導出。実装はしていない
external_action: none
tags: [nexa, source, note-preview]
origin_url: ""
topics: []
ported_from: nexa-articles content/nexa-articles/sources/_tools/note-preview/preview-constraints.md
ported_at: 2026-09-11
ported_note: 2026-09-11 実測の元ファイルをそのままコピー（内容の改変なし）。移植先の実装は scripts/note_virtual_preview.py（旧 render_note_preview.py の移植）。
---

# 仮想 note preview が守るべき制約

このファイルは判断材料の一覧。`template.html` / `render_note_preview.py`（このリポジトリでは `assets/note-preview/template.html` / `scripts/note_virtual_preview.py`）への実装はしない（別タスク）。

## 見出しの許容

- H2 / H3 のみが正式ノード。H1・H4〜H6 は **schema 上も丸められる**（貼り付け時の markdown-it パースで `level<2→2, level>3→3`）。
- → preview 側で H1/H4以上の見出しが draft に出てきたら、警告するか H2/H3 に丸めて表示するのが note 実物に忠実。現状の `render_note_preview.py` の挙動は未確認（別途要確認）。

## リンクの表示

- 本文リンクは **地の文と同色＋下線**（青字ではない）。属性は `target="_blank" rel="noopener nofollow"`。
- → preview の CSS で `a { color: inherit または --color-text-primary; text-decoration: underline; }` を徹底する（note-article-dom-analysis.md 既知の指摘と一致、再掲）。

## figure（画像）の枠

- 画像ノードに **caption/figcaption は存在しない**（`alt` 属性のみ）。figcaption が使えるのは blockquote 型ノード（`figure > blockquote + figcaption`）だけ。
- → preview で「画像にキャプションをつける」表現をするなら、それは note 実物の image ノードとは別物（誤解を招く）である旨を preview 側に注記するか、キャプション表示自体を避ける。

## 埋め込みカード

- embed は `figure[embedded-service]` 系ノードで、`embeddedService` 値ごとに種類が分かれる（外部記事カード／note記事埋め込み／`note-sound`（音声）／`note-slide`（コミック）等）。
- 選択時のバブルメニューも `note-sound`/`note-slide` は "編集"/"削除" のみに絞られる特別扱い。
- → preview の埋め込みカード近似（`.embed-card`）は「note記事URL→iframe型」「その他→外部記事カード型」の分岐が既存 README の「今後の改善点」に既出。加えて、音声・コミック埋め込みは全く別 UI であることも preview の注記に加える価値がある（ただし draft.md 側でこれらを使うかどうかは編集フローの実態次第）。

## 目次

- `tableOfContents` ノードは DOM 上は空タグで、中身は JS が動的生成する（本解析では生成ロジック未特定）。
- → preview で「H2/H3が2つ以上あれば目次を出す」簡易ロジック（README記載の現状）は近似としては妥当。ただし note 実物の目次表示条件（見出し設定・予約投稿設定との関係）は依然未解明のまま。

## 区切り線

- `horizontalRule` は挿入メニュー経由で `<hr>` + 直後に空段落が自動挿入される。
- → preview で `---` を hr に変換する場合、note 実物同様「hr の直後に空行相当の余白」を再現すると近い。

## ツールバーの位置

- JS 実測: `window.innerWidth>=768` が明確な分岐点（スラッシュコマンドの有効/無効の判定に使用）。CSS のメディアクエリも `768px`/`769px` を対で持つ。
- バブルメニューは固定配置ではなく `coordsAtPos()` による選択追従（`left`/`top`/`mobileTop` の3値を保持）。どちらを表示に使うかの実際の分岐点は CSS 側にあり未特定。
- → preview で「幅によってパネルが下に出たり左に出たりする」を再現するなら、**768px を暫定の分岐点**として採用し、769px以上は選択位置追従、768px以下は下部固定、という近似が現時点の最有力仮説（未確証。実機での目視確認が要る）。

## 貼り付け・入力時の変換（preview は編集不可なので直接は関係しないが、draft.md → note editor への投入指示に影響）

- プレーンテキスト貼り付けは markdown-it 相当で `#`〜`######`→H2/H3、`>`→引用、`-`/`1.`→リスト、` ``` `→コード、`---`→hr、`**`→太字、`~~`→取り消し線、`[]()`→リンク に変換されるが、**`*斜体*` と `` `インラインコード` `` は破棄される**（表示されずに消える）。
- → draft.md 内で斜体やインラインコードを使っている箇所は、そのまま note editor に貼り付けると消える可能性がある。preview 側で「この記法は note では再現されない」と警告する価値がある（priority は低いが、既存の「note 実物との差」節に追記候補）。
- HTML貼り付け時の note 独自変換は nbsp正規化のみで、构造変換は schema のパーサ段階に委ねられている（table・h1・h4は note の schema に無いノードなので、貼り付け後にどう扱われるかは note-editor-live-constraint-boundaries.md の実測（h2/h3/p/ol/liのみ対応）を正とする）。

## 反映は別タスク

上記は「preview に反映すべき項目」の候補整理であり、`template.html` / `render_note_preview.py` の実装・CSS 追記は行っていない。実装時は本ファイルと `editor-js-analysis.md` の「未確認」節を合わせて参照し、確証のない挙動（目次生成ロジック、右クリックメニュー、ツールバー分岐の実セレクタ等）は「近似・未保証」と明記したまま進めること。
