---
title: note 公開記事の DOM 構造解析（仮想 note プレビュー用）
type: reference
status: active
created: 2026-09-11
source_scope: local live measurement（本人公開記事1本の HTML/CSS を curl で取得して解析）
external_action: none
origin_url: ""
date: ""
topics: []
tags: [nexa, source]
ported_from: nexa-articles content/nexa-articles/sources/_tools/note-preview/note-article-dom-analysis.md
ported_at: 2026-09-11
ported_note: 2026-09-11 実測の元ファイルをそのままコピー（内容の改変なし）。
---

# note 公開記事の DOM 構造解析

## 目的

`render_note_preview.py`（仮想 note プレビュー）の見た目・構造を、note の実物に寄せるための実測メモ。
本文テキストは転記しない。構造説明に必要な最小限のタグ・属性・CSS 値だけを引用する。

## 実測条件

- 取得方法: `curl -sL -A "Mozilla/5.0 ..." https://note.com/nexus_ai/n/n1d09f439df7f`（read-only、投稿なし）
- 取得日: 2026-09-11
- 対象: 本人の公開記事1本（SSR された HTML。Nuxt 製、JS 未実行の静的 DOM）
- 既存の一次資料との関係: `note-publishing-suite/references/note-editor-live-constraint-boundaries.md`（editor 側の実測）と `note-editor-capability-inventory.md`（公式ソース一覧）を突き合わせ、editor 入力結果と公開後レンダリングの DOM が一致することを確認した（`figure[data-src]`、`table-of-contents`、H2/H3 は両方に出現）。

## 1. 本文コンテナ

本文（記事タイトルより下、著者情報より下）は次の入れ子で出力される。

```html
<article class="p-article__body">
  <div class="p-article__content pb-4">
    <div data-note-id="..." data-note-key="...">
      <div class="o-noteContentText o-noteContentText--font_sansserif">
        <figure class="o-noteEyecatch">...</figure>  <!-- TOP画像 -->
        <div class="o-noteContentHeader o-noteContentText__header">...</div>  <!-- タイトル/著者/日付 -->
        <div data-name="body" class="note-common-styles__textnote-body">
          <!-- 本文の実体はここ -->
        </div>
      </div>
    </div>
  </div>
</article>
```

- 本文コンテナの実クラスは **`note-common-styles__textnote-body`**（`data-name="body"` 付き）。
- 直下の各ブロック要素（`p` / `h2` / `h3` / `ul` / `ol` / `blockquote` / `figure` / `hr` / `table-of-contents`）はすべて `name="<uuid>" id="<uuid>"` を持つ。プレビュー生成時にこの属性まで再現する必要はない。

## 2. 見出し（H2 / H3）

- H2・H3 のみが使われている（H1 は記事タイトル専用、H4 以下は本文中に出現しない）。editor 側実測（`note-editor-live-constraint-boundaries.md` 3節）と一致。
- 見出しテキストには番号（`1. `、`2. `…）が本文側で手動で振られている例が多い。note が自動採番するわけではない。
- CSS（`.note-common-styles__textnote-body` 内、抜粋）:
  - `h2, h3 { margin-bottom: -18px; font-weight: 700; letter-spacing: .04em; line-height: 2.25rem; }`
  - `h2 { margin-top: 54px; font-size: var(--font-size-2xl); }` → `--font-size-2xl: 1.75rem`
  - `h3 { margin-top: 36px; font-size: var(--font-size-xl); }` → `--font-size-xl: 1.25rem`
  - モバイル（`max-width:480px`）では `h2` が `--font-size-xl`、`h3` が `--font-size-lg`（`1.125rem`）に縮小。

## 3. 段落・箇条書き

- 段落は `<p>`。`p, ul li { font-size: var(--font-size-lg); line-height: 2.25rem; }` → 本文フォントサイズ `1.125rem`（18px 相当）、行間 `2.25rem`（36px、行高 2.0 相当）。
- 箇条書きは `<ul><li>`（`disc`）と `<ol><li>`（CSS カウンタで `1.` 等を自動採番、`list-style:none` + `counter()`)。
- `ul, ol, blockquote, figure, h2, h3, hr, p` はすべて `margin-top:36px; margin-bottom:36px`（モバイルは `30px`）で統一されている。段落間の縦の余白がかなり広い。

## 4. リンク（`<a>`）

実測した本文中リンクの属性:

```html
<a href="https://github.com/nexus-ai-2045/note-publishing-suite" target="_blank" rel="noopener nofollow">https://github.com/nexus-ai-2045/note-publishing-suite</a>
```

- 属性は `target="_blank" rel="noopener nofollow"`。`note-editor-capability-inventory.md` にある一般論（外部 URL 貼り付け→埋め込み/カード化）とは別に、**本文中に残る通常リンクはこの3属性の組**であることを確認した。
- CSS: `a { text-decoration: underline; cursor: pointer; }`。色は個別指定がなく、`--color-text-primary: #08131a`（ほぼ黒）を継承する。hover 時のみ `color: var(--color-text-primary)`（実質変化なし）+ `text-decoration:none`。
  - つまり **note の本文リンクは「青いリンク色」ではなく、地の文と同色＋下線** で区別される。既存 `scripts/note_preview.py` の `a { color:#2b82d9 }`（青）は note 実物と異なる。

## 5. URL 埋め込み（figure[data-src]）

単独行 URL は note editor 側で自動的に埋め込み/カード化される（`note-editor-live-constraint-boundaries.md` 2節と同じ挙動）。公開後の DOM でも同じ構造が残る。実測した2パターン:

### 5a. 外部記事カード

```html
<figure data-src="https://singulab.jp/" data-identifier="null"
        embedded-service="external-article" embedded-content-key="...">
  <div data-name="embedContainer">
    <div data-embed-service="external-article">
      <span>
        <div class="external-article-widget">
          <a href="https://singulab.jp/" rel="noopener nofollow" target="_blank">
            <strong class="external-article-widget-title">シンギュラボ（Singulab）...</strong>
            <em class="external-article-widget-description">...</em>
            <em class="external-article-widget-url">singulab.jp</em>
          </a>
          <a class="external-article-widget-image" href="https://singulab.jp/" ...>...</a>
        </div>
      </span>
    </div>
  </div>
</figure>
```

### 5b. note 記事の埋め込み（editor 実測と同型）

`note-editor-live-constraint-boundaries.md` 2節の実測どおり `figure[data-src="https://note.com/..."]` + 子要素 `iframe.note-embed` が生成される（今回の対象記事では note 記事の埋め込みは未使用だったため、公開後 DOM は editor 実測結果を正とする）。

## 6. 引用（blockquote）— カード型の使われ方

この記事では `blockquote` が単独ではなく `figure > blockquote + figcaption` の形で使われていた。

```html
<figure>
  <blockquote>
    <p>（引用テキスト）</p>
  </blockquote>
  <figcaption></figcaption>
</figure>
```

CSS: `blockquote { padding:25px 36px; font-size: var(--font-size-base); line-height:2.25rem; background-color: var(--color-background-secondary); }`。背景色付きのカードとして表示される。

## 7. 区切り線・目次

- `<hr>` は単独タグ。`border:none; border-bottom:1px solid var(--color-border-strong)`（値は取得 HTML から一部欠落、file 中に完全一致なし。おおよその色のみ確認）。
- 目次: `<table-of-contents name="..." id="..."><br></table-of-contents>`。中身は空で、フロント側 JS が見出しを拾ってレンダリングするカスタム要素。editor 実測（`table-of-contents contenteditable="false" toc="[...]"`）と同じカスタムタグ名で、公開後は `toc` 属性が省略されている（JS 実行後に生成される可能性があり、SSR 段階では空）。

## 8. 画像

- TOP画像は `figure.o-noteEyecatch > img.o-noteEyecatch__image`（本文とは別枠）。
- 本文内画像は `img { display:block; max-width:100%; height:auto!important; margin:0 auto; border:1px solid var(--color-border-weak); }` → 中央寄せ・枠線付き。`--color-border-weak: #f5f8fa`（ごく薄いグレー）。

## 9. 太字・強調

- 太字は `<strong>`（`font-weight:700`）。今回の記事では `<em>` は「外部記事カードの説明文」（`external-article-widget-description`）にのみ使われており、本文の斜体強調としては未確認。

## 10. フォント・配色（本文コンテナ）

```css
.note-common-styles__textnote-body {
  font-family: "Hiragino Mincho ProN","Hiragino Mincho Pro",HGSMinchoE,"Yu Mincho",YuMincho,"MS PMincho",serif;
  color: var(--color-text-primary); /* #08131a */
}
/* font_sansserif 修飾クラスが付くと差し替え */
[class$=font_sansserif] .note-common-styles__textnote-body {
  font-family: "Helvetica Neue","Hiragino Sans","Hiragino Kaku Gothic ProN",Arial,"Noto Sans JP",Meiryo,sans-serif;
}
```

実測対象記事は `o-noteContentText--font_sansserif` 修飾があり、実際の表示フォントはゴシック体（サンセリフ）側だった。**note の本文既定フォントは明朝体で、著者設定でゴシックに切り替えられる。**既存 `note_preview.py` は最初からゴシック固定（`-apple-system, "Hiragino Sans"...`）だが、これは note の「サンセリフ設定時」の見た目に近く、明朝体の既定は再現していない。

- 本文コンテナの左右 padding: `481px〜768px` で `40px`、`480px以下` で `16px`（レスポンシブ）。PC 幅（769px以上）は padding 指定なし＝親コンテナの幅に依存。

## 11. JS（実行はしない・名前と役割のメモのみ）

SSR HTML 内の `<script src>` は Nuxt のチャンクファイル群（`frontend.st-note.com/nuxt/production/note.*.js` が十数本、`cdn.st-note.com/js/tw-widget.js` が1本）。ファイル名からハッシュ化されたビルド成果物であることが分かるのみで、個別ファイルの役割は名前からは特定できない（未確認）。`tw-widget.js` は X（Twitter）埋め込みウィジェット用と推測されるが未検証。目次 (`table-of-contents`) の中身描画、いいねボタンの状態管理、埋め込みカードの遅延読み込みなどはいずれもこれらの JS が担っていると推測されるが、個別対応は特定できていない（未確認）。

## 12. 仮想プレビューへの反映方針（このメモを踏まえた設計判断）

- リンク色は青ではなく地の文と同色＋下線にする（4節）。
- 段落・見出しの縦マージンは note 実測値（36px 基準、モバイル30px）に寄せる。
- 見出しは H2/H3 のみを許容し、H2 は `1.75rem` 相当、H3 は `1.25rem` 相当を基準にする。
- URL 埋め込みカードは `figure[data-src]` 型の外部記事カード（5a）を模した点線／実線枠で表現する（本ツールでは note の JS を実行できないため実カードは再現できない。枠と URL 表示までの近似）。
- 本文フォントは note の既定（明朝）ではなく、実測対象記事と同じサンセリフ表示を採用する（読みやすさ優先、AI案）。

## 未確認・保証できない点

- `table-of-contents` の実際の見た目（JS 実行後の中身）は今回未確認。空タグのみ実測。
- `blockquote` 単体（`figure` に包まれない形）の実例は今回の記事になし。
- モバイル実機での表示は未確認（CSS のメディアクエリ値からの推定のみ）。
- ハッシュタグ表示・目次以外のインタラクティブ要素（いいねアニメーション等）は未確認。
