---
title: note draft authority and layout contract
type: reference
status: active
source_scope: public-safe workflow contract
publication_action: none
---

# note draft authority and layout contract

## 目的

壁打ちから記事を作る時に、AIが本人らしい文章を推測で補ったり、編集反映の都合で本文を短縮したり、図と改行を崩したりすることを防ぐ。

## 問答 intake と著者性

材料が不足している時は、完成文を先に作文せず、短い問答 intake で次を確認する。

- 読者に最初に伝えたい結論や違和感。
- 本人が実際に行ったこと、理解したこと、まだ分からないこと。
- 使ってよい発言、資料、過去記事、図。
- 丁寧さ、話し言葉、断言の強さ、残したい言い回し。

`voice_profile` は、許可された過去記事や本人指定の例から、語尾、断言の強さ、一文の長さ、丁寧語と話し言葉の配分を抽出した参照情報である。本人の事実や感情を生成する根拠ではない。本人の発言にない感想や体験を作文しない。不足部分は質問、保留、確認候補として残す。

## 短縮防止

編集前に `shortening_budget` を決める。既定は「意味段落、具体例、本人発言、出典、図、キャプションを削らない」。短くする必要がある時も、省略候補を勝手に削除しない。削除候補と理由を提示し、人間が採否を決める。

反映後は、見出し、段落、引用、URL、図、キャプションの件数と主要句をローカル正本と照合する。長さが違うだけで失敗とはしないが、主要句や意味段落が欠けた場合は完了扱いにしない。

## 改行、図、キャプション

- 通常の段落境界と段落内改行を区別する。文字としての `\\`、不要な空段落、句読点ごとの過剰な分割を作らない。
- ローカル原稿は `scripts/note_linebreak_gate.py`、editor観測はfresh DOMで確認する。
- 図は新しい概念を最初に説明する箇所へ置き、本文との対応を確認する。
- 図の直前と直後に意図しない空段落を増やさない。
- キャプションは図の説明として保持し、本文や「図: ...」というplaceholderへ戻さない。
- 図、近傍見出し、キャプションの構造は `scripts/note_figure_structure_gate.py` で検査する。

## ブラウザ復旧との境界

transport切断やtimeoutから復旧しても、古いカーソル、DOM、本文長を引き継がない。対象URLを再取得し、本文、図、キャプション、改行のreadbackを終えてから次の一操作へ進む。mutationの再実行より状態照合を優先する。

## Closeout Evidence

- 問答で確認した事項と保留事項。
- `voice_profile` の根拠にした許可済み資料。
- `shortening_budget` と、削除した項目または削除なし。
- 改行、図、キャプションの検査結果。
- 未実行の公開、予約、共有、外部送信。

## 記事ごとの末尾リンク選定契約

固定枚数のカードを全記事に要求しない。既存の制作パックの Plan 内に、
次の `footer-selection` JSON ブロックを一つだけ保持する。別の選定台帳を作らない。

- `article_id`、`reader`、`series`、`reader_action`: 記事、読者、シリーズ、読後行動。
- `decision`、`reason`: `include`（採用）または `omit`（非採用）と空でない理由。
  非採用は `links: []` を明示し、採否と理由を含む計画を人間が承認する。
  採否が未指定の既存計画は従来の採用として照合し、空配列から非採用を推測しない。
- `links`: DOM順に並べた採用リンク。各項目は `url`、`registry_ref`、`reason`、
  `presentation`（`card` または `text_link`）、`required`（真偽値）を持つ。
- `registry_ref`: 公開記事なら既存 `data/published_notes.json` の該当登録、
  その他はその記事で承認された既存のリンク登録・資料の参照先。新しい汎用台帳を増やさない。
  素材登録だけでCTA適合性を承認済みと解釈しない。存在確認と意味の適合性は人間レビューで行う。
- `review`: `status: approved`、`reviewer`、時差付き `reviewed_at`、`plan_sha256`。
  ハッシュは review を除く全計画を `json.dumps(ensure_ascii=False, sort_keys=True,
  separators=(",", ":"))` のUTF-8でSHA256化する。変更後は再レビューを要する。

```footer-selection
{
  "article_id": "example-article",
  "reader": "関連する入門記事を読みたい読者",
  "series": "example-series",
  "reader_action": "次の解説を読む",
  "decision": "include",
  "reason": "読後の疑問を関連資料で解消する",
  "links": [{
    "url": "https://example.com/archive",
    "registry_ref": "既存登録の参照先を人間が確認して記入",
    "reason": "読後の疑問を次の解説で解消する",
    "presentation": "card",
    "required": true
  }],
  "review": {"status": "pending", "reviewer": "", "reviewed_at": "", "plan_sha256": ""}
}
```

この例は未レビューなので検査に通らない。fixtureの承認記録は人工の試験入力で、
人間レビューが実施された証明にはしない。意味の適合性や承認の真正性を機械が創作しない。
空計画、採用時の空のlinks、未レビューは停止する。承認済み非採用では
`links: []` と観測の `footer.nodes: []` を必要とし、リンクや観測の欠落は空配列扱いしない。
非採用なのにリンクや観測ノードがある場合も停止する。採否や理由の変更は承認を失効させる。
workflowの `layout.footer_cards` と同じ採否・理由の考え方を使うが、各入口の承認証拠は別に必要。
任意リンクは省略できるが、追加時の順序と形式を守る。

公開前の実入口:

```powershell
python scripts/note_editor_prepublish_verify.py <observation.json> --production-plan <production-pack.md> --json
```

公開後は同じ照合を `--footer-only` で行う。公開後本文検査のinnerTextやAPI応答だけでは
カードDOMを確認できない。承認されたブラウザ経路で対象記事の末尾を取得してから照合する。
検査器はブラウザを操作せず、公開記事も更新しない。

観測は記事ID、シリーズと `footer.nodes` のDOM順配列を保持する。
FIGUREは `data_src` / `data-src` / `url` または子リンクの `hrefs` から単一URLを解決する。
公開DOMのFIGUREにdata-srcが無い場合もhrefsで照合できる。複数の異なるURLなら未確定として落とす。
文字リンクは `tag: A`、`href`、表示文 `text`。URLそのものの表示は未カード化の生URLとして落とす。
未知node、欠落、余分、順序違い、重複、カードと文字リンクの取り違えは停止する。

`ok` は供給されたsnapshotと計画の整合性だけを示す。
`verification_scope: supplied_snapshot_only`、`live_dom_verified: false`、
`ready_for_publish: false` を常に保持する。manual_boundaryは合格にしない。
実DOM取得の真正性、note名義、記事版、人間レビュー、公開操作の承認は別証拠で確認する。
