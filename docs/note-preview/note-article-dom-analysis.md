---
title: 公開記事の構造とローカルプレビューの合成例
type: reference
status: active
source_scope: synthetic examples; historical observations summarized
external_action: none
---

# 公開記事の構造とローカルプレビュー

過去のDOM観測からプレビューに必要な構造を整理した資料。以下のHTML・URL・文章は
説明用の合成例であり、特定著者の記事や保存済みの実ページを複製したものではない。
実在記事のURL、著者情報、記事識別子、取得CSSは公開パッケージに含めない。

## 本文とブロック

```html
<article>
  <div data-name="body" class="note-common-styles__textnote-body">
    <h2>合成見出し</h2>
    <p>構造を説明するための合成本文。</p>
    <p><a href="https://example.com/reference" target="_blank"
          rel="noopener nofollow">参考リンク</a></p>
    <ul><li>合成項目</li></ul>
    <blockquote><p>合成の引用例。</p></blockquote>
    <figure data-src="https://example.com/article">
      <div data-name="embedContainer">カードの代替表示</div>
    </figure>
    <hr>
    <table-of-contents><br></table-of-contents>
  </div>
</article>
```

H2/H3、段落、箇条書き、引用、画像、リンク、`figure[data-src]`と目次を
ローカル変換の対象とする。ページ側のクラスや属性は変更され得るため、
実記事の更新では既存の画面照合を省略しない。
CSSに規則がないことだけで、エディタの入力可否やschemaを断定しない。

## 描画の責務

`assets/note-preview/note-preview.css`はNPSが独自に作成した読書用の近似スタイル。
NoteのCSSから抽出した規則は同梱しない。テンプレートはカードを代替表示し、
NoteのJS、実カード取得、目次の実サイト表示や著者設定の完全再現は行わない。
`--css`は利用者が権利を確認した別スタイルを指定する既存の入口として維持する。

## 検証の限界

ローカルの変換テストは本文構造・リンク数・画像保持などを確認する。
実サイトとの描画一致、モバイル実機、保存成功や公開成功の証拠にはならない。
