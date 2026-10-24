# 本人・AI・出典を確認するHTMLレビュー

機能コードはNPS、本文・本人原文・口調・採否は利用側workspaceに置く。既存の由来ラベル付き本文レビューは `note_preview.py --review-provenance`、骨組みと本文の対応レビューは次の入口を使う。旧記事リポジトリのHTMLコマンドはこの機能を呼ぶadapterとし、実装を独立更新しない。

```sh
python scripts/note_skeleton_review.py SKELETON_JSON OUTPUT_DIR --workspace-root ARTICLE_WORKSPACE
python scripts/note_skeleton_review_check.py SKELETON_JSON OUTPUT_DIR --workspace-root ARTICLE_WORKSPACE
python scripts/note_skeleton_source_gate.py DRAFT_MD --workspace-root ARTICLE_WORKSPACE
```

JSONは既存のepisodes[].n/sections[].heading/paragraphs[]を使う。本人原文はtext、編集案はedited_text、出どころはsource/ref、保存本文と引用のhashはsource_sha256/text_sha256、現稿との対応はdraft_correspondence。本人採用とAI案、未収録と本人の不採用を分ける。各話の番号は重複のない正の整数とし、出典リンクは認証情報のないHTTP(S) URLに限定する。由来表示は申告ラベルの可視化であり、著者性の認証ではない。原文hash・引用block・段落ID・現稿対応の検査を併用する。字数を宣言した骨組みはhash一致する `--draft` を渡す。

## 壁打ちから各節の執筆内容を整理する

原文の引用一覧と「各節で何を書くか」は別の成果物である。会話を記事にする骨組みは、rootに `skeleton_mode: writing-plan` を宣言し、全sectionへ `writing_plan.items` を付ける。既存のparagraphsは根拠原文として保持し、画面では執筆内容を先に、原文を折り畳みで表示する。旧形式は引き続き読めるが、引用一覧の生成成功を執筆計画の完成とは扱わない。

各itemは `text`、`kind`、`basis` を持つ。kindは `author-position`（本人の考え）、`accepted-response`（本人が同意した返答）、`research`（調べて説明する内容）、`open-question`（答えが出ていない疑問）。basisは同じ節のparagraph IDの配列である。本人の考え・疑問・調査依頼には本人発言の根拠を必須とする。本人の考えにAI返答を根拠として使う場合は、`accepted-response`と同意記録へ分類し直す。調査の必要な箇所は依頼した本人発言へ結び、外部事実を本人の見解へ読み替えない。具体例や疑問が無い節に枠埋めで追加しない。

本人が同意した返答は、adoptionの `user_message_id`、`user_quote`、`assistant_message_id`、`scope` で範囲を明記する。同じ節のparagraphsへ本人の同意発言と対象のAI返答を収録し、その両方をbasisに含める。checkerは参照と保存内容の一致、未知の由来、欠落、重複、改変、URL形式を検査する。同意の意味・真正性や、疑問が結論へ変わっていないかは独立レビューで確認し、構造検査の成功やAIの自己申告で本人採用にしない。

本文へ進む際は、この骨組みの採用・最新修正と本文各段落を照合する。本人の判断や経験として根拠を示せないまとめ・感想・説明のつなぎは、本人の語りに追加しない。出典により確認できる事実、本人が同意した範囲、未採用の提案を分け、未解決の疑問を勝手に解決しない。本人へ骨組みを提示している段階では本文の改稿を進めない。

`source_mode: skeleton_first` の原稿は `author_skeleton` と正の整数の `episode` を必須にする。本人由来blockの既存 `provenance-label: user-said` と `paragraph-id` を、選択した話の原文・edited_textへ照合する。旧B5の契約を維持し、他の話数にも同じ検査を使う。依存は任意機能専用のrequirements-review.txtに置く。未導入環境で検査を実行した扱いにしない。全source paragraphの意味が保たれたことはhash照合だけでは証明できず、人間の採否と意味の点検を残す。

## 修正ごとのフィードバック

本人が細かな確認を求めた場合は、元の文→AIが理解した意図→修正案→本人への短い確認の順で一件ずつ提示する。返答後に修正前後を読戻す。回答前の提案はAI/pendingとして既存feedbackへ保存し、無回答を採用にしない。既存の本人採用は同じ質問を繰り返さず、今回の文脈で適用・非該当を検査する。共通の口調、記事限定、後続版で変更済みを分け、本人が今後にも使うと採用した知見だけを利用側の文体・history policyへ結線する。新しい採否台帳を作らない。

各話の番号は重複のない正の整数にし、出典リンクは認証情報のないHTTP(S)に限る。原文参照と現稿対応の相対pathは利用側workspaceを基準に解決する。本文の直接編集や新しいUIの採用は、この移植の検査成功とは分ける。
