---
name: note-draft-production
description: "Use inside note-publishing-suite when creating skeletons, Note drafts, top-image ideas, and tag candidates from approved local materials."
---

# note-draft-production

## 役割

選ばれた候補を `content/drafts/` のローカル下書きへ進める。

## 入力

- 記事候補、読者、読後に得るもの、公開目的。
- 読んでよいローカル素材 path。
- 既存 draft path。未作成なら Unknown。
- article lane。`production_candidate`、`exploratory_draft`、
  `editor_fixture`、`continuation_article` のいずれか。
- source mode。例: `source_pack_locked`、`skeleton_first`、
  `conversation_reflection`、`fixture_only`。
- TOP 画像の有無。未作成なら Unknown。
- 権利、引用、秘密情報、内部メモに関する未確認事項。

## 手順

1. `../../references/note-article-provenance-design.md` を読み、
   `article_lane`、`source_mode`、source database、source pack、plot、
   skeleton、wall-bang、stance brief を固定する。
2. Plan 表を作る。読者、読後に得るもの、嬉しい解決、入口、公開後 PDCA 指標を 1 行ずつ決める。
3. plot / skeleton を作る。連載や記事の展開、導入、読者の痛み、主張、根拠、具体例、反論処理、締め、Call To Action（CTA）を含める。
4. 本文では事実、推定、意見を分ける。根拠が必要な主張は確認対象として残す。
5. 長い転載、歌詞全文、未承認引用、個人情報、秘密情報、内部メモを本文に入れない。
6. TOP 画像案を 7 件出す。各案に `concept`、`prompt`、`style`、`avoid`、`fit_reason` を付ける。
7. タグ案は広い発見タグ、主題タグ、文脈タグ、所有シリーズタグを混ぜる。
8. 保存先は `content/drafts/<date>-<slug>.md` を既定にする。
9. frontmatter に `article_lane`、`source_mode`、`based_on`、
   `allowed_use`、`not_allowed`、`editor_test_allowed`、
   `publication_gate: human_review_required`、`external_action: none` を置く。

## 境界

公開文面として扱える水準まで整えるが、公開承認ではない。公開、予約投稿、SNS 共有、外部告知は行わない。

`editor_fixture` lane は公開候補にしない。Note editor 操作テストは fixture 文で行い、
`production_candidate` の本文をテスト目的で改変しない。

## 出力

- `content/drafts/<date>-<slug>.md`: 本文。
- 必要なら `content/drafts/<date>-<slug>-production-pack.md`: skeleton、壁打ち、画像案、タグ案。
- `content/assets/<slug>/`: TOP 画像候補や preview を置く場合のみ。

## 停止条件

- 根拠が必要な主張を確認できない。
- 権利リスクのある引用や画像が公開前提になっている。
- ユーザーが求めている記事種別が未確定。

## Closeout Evidence

- 作成/更新した draft path。
- article lane / source mode。
- 使った source database / source pack / plot / skeleton / wall-bang / stance brief。
- 残した未確認事項。
- 次の QA コマンド。

## ハッシュタグ選定

- 候補は 5-10 個。記事の主題タグ + 文脈タグ + 固有タグを混ぜる。
- 過去記事のタグ実績を台帳 (data/published_notes.json の tags) で確認し、続き物は揃える。
- 公式ソースで確認済み: ハッシュタグは公開設定で追加する方法と、本文中に半角 `#` + 単語を書く方法がある。本文中に書く方法でも公開設定へ反映される。
- local policy: 主題タグ、文脈タグ、固有タグを混ぜる。これは公式推奨としては扱わない。
- local observation: ハッシュタグは本文中で使うと候補に出やすくなる場合がある。断定せず、必要なら実測確認へ回す。
- 断定的な流入予測をしない。タグ案は人間レビューに回す。

## AI 利用の境界 (本 skill 内)

- AI が作ってよいもの: skeleton、構成案、要約、タグ候補、画像案。
- AI が作ってはいけないもの: 本人の一言・体験・判断の代作、原文と一致しない引用 (作文禁止)。
- 引用はすべて source と突き合わせ、言い換えは間接話法にする。
