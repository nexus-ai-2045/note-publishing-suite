---
title: note article provenance design
type: reference
status: active
created: 2026-06-16
source_scope: local workflow design
publication_action: none
---

# note article provenance design

## 目的

Note 記事が「何を元に作られたか」を、draft 作成前に固定する。
実記事候補と editor 操作テストを混ぜないため、source database、source、
plot、skeleton、wall-bang、stance、fixture を別の役割として扱う。

## lane

| lane | 用途 | 使ってよいもの | 禁止 |
|---|---|---|---|
| `production_candidate` | 公開候補の本文 | 承認済み source pack、skeleton、stance brief | fixture 文、未承認素材、editor 実験のための本文改変 |
| `exploratory_draft` | 壁打ち・仮説整理 | ユーザーの発言、許可されたメモ、仮説 | 事実断定、公開 ready 扱い |
| `editor_fixture` | Note editor 操作検証 | 無害なテスト文、検査用 URL、検査用見出し | 公開候補本文、個人情報、秘密情報 |
| `continuation_article` | シリーズ継続記事 | 前記事、シリーズ skeleton、context brief、source pack | 前記事にない事実の無根拠な継ぎ足し |

## source roles

- `source_database`: 最初に参照する事実DB。台帳、公式URL一覧、既存記事、
  許可済み観測メモ、ローカル資料 index など。ファクト抽出はここを優先する。
- `source_pack`: 事実根拠として使ってよい資料。公式 URL、公開済み記事、
  許可済み観測メモなど。source database から記事単位に切り出した根拠束。
- `series_plot`: 連載全体の展開設計。どの順で何を読ませるか。
- `article_plot`: その記事の展開設計。主張の運び、読者体験、転換点。
- `skeleton`: 構成の設計図。見出し、論点順、読者への約束。
  plot / skeleton は evidence ではない。
- `wall_bang`: 壁打ち、会話ログ、仮説、違和感、切り口候補。
  ファクト根拠ではなく、問い・論点・表現候補として扱う。
- `stance_brief`: この記事の立場、避ける断定、語り口、境界。
- `previous_articles`: 文脈継承のための過去記事。事実根拠に使う場合は
  source pack にも入れる。
- `editor_fixture`: editor 操作テスト専用の本文。公開候補に混ぜない。

## 壁打ちからコンテンツ化する制作ライン

壁打ちは、単なる雑談メモではなく、人間の暗黙知、違和感、比喩、
読者感覚、論点、熱量を回収する創発素材レイヤーとして扱う。

ただし、wall-bang は事実出典ではない。
会話から出た断定、数字、固有名詞、時系列、評判、引用候補は、
`source_database` または `source_pack` で裏取りされるまで
本文の事実根拠にしない。

推奨フロー:

1. 数人の人間で壁打ちする。
2. 発話ログ、メモ、資料名、未確認の主張を残す。
3. 次の単位に分解する。
   - 問い
   - 違和感
   - 仮説
   - 体験談
   - 比喩
   - タイトル候補
   - 読者角度
   - 連載化できる軸
   - 追加調査が必要な主張
4. 事実は `source_database` から確認し、記事単位では `source_pack` に固定する。
5. 出力領域を選ぶ。
   - Note 記事
   - 動画概要
   - X投稿
   - 台本
   - 連載構成
   - 書籍章
   - 商品 / 企画提案
6. 人間が採否、語り口、公開可否をレビューする。

wall-bang 由来の出力は、完了報告で次を分けて報告する。

- 出典事実: source database / source pack で裏取り済みの事実。
- 壁打ち由来の案: 問い、切り口、比喩、仮説、言い回し候補。
- 追加調査ギャップ: 本文採用前に追加確認が必要な主張。
- 不採用の切り口: 強いが採用しなかった切り口。

## draft frontmatter contract

```yaml
title: 社会シミュレーションは、どこまで実験してよいのか
status: draft
article_lane: production_candidate
source_mode: source_pack_locked
based_on:
  source_database: data/note_source_database.json
  series_plot: content/drafts/2026-06-05-automata-series-skeleton-v1.md
  article_plot: content/drafts/2026-06-05-automata-second-third-article-context-brief.md
  skeleton: content/drafts/2026-06-07-automata-third-article-skeleton.md
  context_brief: content/drafts/2026-06-05-automata-second-third-article-context-brief.md
  wall_bang:
    - content/drafts/2026-06-04-automata-chat-context.md
  previous_articles:
    - published/2026-06-05-automata-observation-magazine-first-article.md
    - content/drafts/2026-06-05-automata-second-article-note-prepublish.md
  official_sources:
    - https://automata-lab.jp/
    - https://singulab.jp/news/202605_automata_release
allowed_use:
  - 前記事の文脈継承
  - 公式情報の事実確認
  - 壁打ちは問い、切り口、仮説、言い回し候補として扱う
  - Discord は個別引用せず場の傾向として扱う
not_allowed:
  - 未確認の活発度断定
  - 個人投稿の引用
  - 公開承認なしの投稿
editor_test_allowed: false
publication_gate: human_review_required
external_action: none
```

## design rules

- draft 作成前に `article_lane` と `source_mode` を決める。
- ファクト抽出は `source_database` を最優先し、記事単位では `source_pack` に切り出す。
- `source_pack_locked` の記事では、本文根拠は `based_on` に列挙した source に限定する。
- plot / skeleton は構成にだけ使い、事実根拠として扱わない。
- wall-bang は問い、論点、仮説、言い回し候補として使い、事実断定の根拠にしない。
- wall-bang 由来の断定は追加調査ギャップに入れ、source pack で確認されるまで本文の事実にしない。
- wall-bang から複数出力領域へ展開する場合も、公開、投稿、告知は各領域の人間レビューゲートで止める。
- stance brief は断定回避、未確認境界、読者への約束を固定する。
- editor 操作検証は `editor_fixture` lane を使う。実記事候補を検証 fixture にしない。
- 実記事候補を Note editor へ反映する場合は `editor_test_allowed: false` を保ち、
  editor 操作のために本文を改変しない。
- `exploratory_draft` は公開候補ではない。公開候補に進める前に source pack を固定する。

## closeout

記事作成・editor handoff の closeout では次を報告する。

- article lane
- source mode
- source database / source pack / plot / skeleton / wall-bang / stance brief
- editor fixture を使ったか
- 未確認 source
- 公開、投稿、予約、SNS 共有を未実行にしたこと
