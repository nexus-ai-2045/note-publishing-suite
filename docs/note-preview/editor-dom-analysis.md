---
title: note 下書きエディタの DOM / JS / CSS 解析（2026-09-11）
type: 派生台帳
date: 2026-09-11
method: Chrome 既存タブ（editor.note.com の自分の下書き）の DOM を読み取り専用で観測。本文テキストは読んでいない。CSS は editor.note.com の公開静的ファイルを curl で取得
external_action: none
tags: [nexa, source, note-preview]
origin_url: ""
topics: []
ported_from: nexa-articles content/nexa-articles/sources/_tools/note-preview/editor-dom-analysis.md
ported_at: 2026-09-11
ported_note: 2026-09-11 実測の元ファイルをそのままコピー（内容の改変なし）。CSS 抽出先パスはこの NPS worktree では assets/note-preview/note-textnote-body.extracted.css。
---

# note 下書きエディタの DOM / JS / CSS 解析

## 実測（2026-09-11、Chrome 既存タブ）

- フレームワーク: **Next.js**（`_next/static/chunks/…`、`pages/notes/[id]/edit`）。Nuxt/Vue ではない。
- 本文エディタ: **ProseMirror**。`div.ProseMirror.note-common-styles__textnote-body`（`contenteditable="true"`、`role`、`aria-multiline`）。tiptap のクラスは無い。
- 本文の子要素は `p`（`p.paragraph` を含む）。見出し・図・埋め込みは挿入メニューで生成される（NPS の実測記録と一致: 大見出し=H2、小見出し=H3、`figure[data-src]`、`iframe.note-embed`、`table-of-contents`）。
- ツールバー（aria-label / テキスト）: AI アシスタント、目次、noteのヒント、エディタのガイド、下書き保存、公開に進む、太字、取り消し線、リスト、文章の配置、リンク、引用、コード、メニューを開く。
- 読み込み CSS: `editor.note.com/_next/static/css/9db03725e06e87b2.css`（105 KB）。本文用クラス `note-common-styles__textnote-body` に対する規則が **258 件**。

## 本文で使える要素（CSS 規則から逆算）

`note-common-styles__textnote-body` 配下に規則があるタグ:
`a`, `b`, `strong`, `blockquote`, `code`, `pre`, `figure`, `figcaption`, `img`, `svg`, `h2`, `h3`, `hr`, `ol`, `ul`, `p`, `ruby`

含意:
- **H2 / H3 のみ**（H1・H4 以下の規則なし）。
- **表（table）の規則なし** → 表は使えない。
- **`hr` の規則あり** → 区切り線は存在する（Markdown の `---` が変換されるかは別。挿入メニュー経由が安全）。
- リンク `a`、太字 `strong/b`、引用 `blockquote`、コード `code/pre`、箇条書き `ul/ol`、図 `figure/figcaption/img` は本文の正式要素。
- `ruby`（ふりがな）の規則あり。

## preview への適用

- 抽出済み CSS: [note-textnote-body.extracted.css](../../assets/note-preview/note-textnote-body.extracted.css)（258 規則）。仮想 note preview の `template.html` はこの CSS をそのまま読み込み、本文を `<div class="note-common-styles__textnote-body">` で包めば、見た目は本物と同じになる。
- 公開記事側も同じクラス名を使う（公開記事ページの解析は別ファイル `note-article-dom-analysis.md`）。
- ProseMirror への貼り付けは、上記タグに正規化した HTML（または Markdown 風入力ではなく挿入メニュー）で行う。表・H1・H4・脚注記号・HTML コメントは落ちるか崩れる。

## 保証しないこと

- JS（`pages/notes/[id]/edit-*.js` 等）の中身は未解析。ProseMirror の schema 定義（許可ノード・マーク）はバンドル内にあり、今回はツールバーと CSS からの逆算にとどまる。
- 目次ブロックと埋め込みカードの見た目は、公開記事側の解析で補う。
- CSS のハッシュ付きファイル名は note 側の更新で変わる。再取得時は `editor.note.com` の `<link rel=stylesheet>` から現在の URL を取る。
