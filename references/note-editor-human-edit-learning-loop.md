---
title: note editor human-edit learning loop
type: reference
status: active
created: 2026-08-08
publication_gate: human_review_required
---

# Note 人手編集 → ローカル吸収ループ

## 目的

Note editor で人間が直したタイトル・口調・構成・表現を、  
「AIが後からローカル案で上書きして消す」事故を防ぐ。  
人手編集は学習対象であり、次回の正本候補になる。

## いつ回すか

- Note 下書きに人間が手を入れたあと
- AI が本文を再 paste / 再構成する直前
- 公開前 gate の直前（差分未確認なら停止）

## 手順

1. **Attach read-only**  
   対象 `note_id` の editor 本文・タイトル・見出しを取得する。
2. **Diff 記録**  
   外部設定の `storage.feedback` 配下の当該記事フォルダに `note-vs-local-diff.md`（または更新）を書く。
   - Note にあって local に無いもの  
   - local にあって Note に無いもの  
   - タイトル採否  
   - 構成順の差
3. **優先規則**  
   - 本人の口調・言い回し・タイトル: **Note（人手）優先**  
   - 構成・型（例先・はてな・討論後など）: 合意した local 方針を提案し、人間確認  
   - 事実・数字: local 証拠コーナー / source と突合
4. **吸収**  
   採択した人手表現を `draft.md` / `note-body.md` / `note-title.txt` に戻す。  
   AI提案だけの文章で人手文を消さない。
5. **台帳**  
   利用者workspaceの既存台帳（package外）に `human_edit_absorbed_at` と差分要約を残す。
6. **再反映が必要なら**  
   差分適用後にだけ editor paste。その前に diff を見せる。

## 禁止

- Note に人手編集があるのに local だけで全面 paste し直す。
- diff を会話メモだけで終わらせ、指定された外部feedback保存先に残さない。
- 「学習した」と言って skill に本人体験談を作文で足す。

## Detector

- editor 本文と `note-body.md` の marker 突合で欠け / 余分がある
- `note-vs-local-diff.md` が無い、または最終 editor 保存より古い
- title が Note と local で食い違うまま AI が片方を独断採用

## Repair

1. editor 再読取  
2. diff 更新  
3. 人間に採否確認  
4. local 吸収 → 必要なら editor へ差分だけ戻す

## Evidence

- `note-vs-local-diff.md` path
- 吸収した項目一覧
- 上書きしなかった人手表現
- 公開未実行の確認

## 記憶の所有と参照

NPSは取得・差分・採否・読戻しの手順を提供する。口調の記憶、記事・シリーズのひな形、採用履歴は利用者の外部SSOTで管理する。毎回の設定・文体参照の読戻しは `note-workflow-review-contract.md` に従う。記事ごとの直しは、その記事の採用履歴として残し、共通口調へ自動昇格させない。

## 小・中・大のループ（運用上の5段階）

五段階はNPSの運用整理であり、心理学の欲求階層との対応を検証したモデルではない。段階を順に卒業する制度ではなく、同時に回る異なる時間幅・責任範囲である。毎回すべてを人間へ質問せず、版一致・再読・保存は機械で行い、採否・意味・一般化・公開は本人が判断する。

| 大きさ | 範囲 | 返す結果 | 再開・上の範囲へ渡す条件 |
|---|---|---|---|
| 小1 | 一回のeditor操作 | 対象一意性、変更前後、保存・読戻し、失敗時の復旧 | 想定差分だけなら次操作。競合や改行崩れは停止・復旧 |
| 小2 | 一つの修正案と採否 | 本人原文、AI案、採用/不採用/保留、理由と根拠 | 採用を外部記事履歴へ保存。未採用を本文へ混ぜない |
| 中3 | 一記事の制作・公開 | 校正、調査、末尾カード・目次、画像、設定、最終判断 | 現稿と履歴と承認が同じ版であること。公開後照合は実体取得後に別記録 |
| 大4 | 記事・シリーズの振り返り | 本人が繰り返し採った表現、読者の反応、次の仮説 | 本人が適用範囲を採用した場合だけシリーズ参照・共通口調へ昇格 |
| 大5 | NPS手順と機能の改善 | 再発原因、仕組みの不足、修正、回帰検証、配布receipt | 記事の好みを固定化せず、汎用停止条件をレビューして採用 |

各範囲で「予想した結果 → 実測 → 違いの理由 → 採用/修正/撤回 → 次回に使う参照」を残す。単にtest成功や保存済みとするだけで学習を完了扱いにしない。大4の読者評価取得・大5の上流配送は、記録を作っただけでは完了しない。

## 実装された保存・読戻しの入口

`note_feedback.py` は独立供給された設定のstorage.feedbackから `<article_id>/feedback.json` と `note-vs-local-diff.md` を解決する。本人原資料・以前の原稿・現稿のimmutable snapshotと採否根拠をpackage外へ保存する。更新前の履歴と差分はhistoryへ保全し、共通口調は変更しない。

```sh
python scripts/note_feedback.py --settings USER_SETTINGS_PATH --article-id ARTICLE_ID \
  --source SOURCE_SNAPSHOT --draft CURRENT_DRAFT --prior-draft PREVIOUS_LOCAL_SNAPSHOT \
  --entries ADOPTION_ENTRIES_JSON --conversation-id CURRENT_CONVERSATION
```

採否entryはorigin（author/ai）、before、after、decision（adopted/rejected/pending/source_preserved）、reason、evidence_refを持つ。本人の発言の真正性をJSONだけで証明したとは扱わない。trusted runtimeが現在会話の発言または本人原稿と照合して記録する。

workflow入口は毎回履歴・差分・snapshotを読み、原資料/現稿と一致すること、packet.feedback_readbackと一致することを必要とする。履歴の変更も承認を失効させる。読戻し成功は、AIが本文の意味や著者らしさを適切に理解した証明ではない。本人による文章レビューは残す。

## 研究・指針との照合（2026-10-05）

- [Deming InstituteのPDSA](https://deming.org/explore/pdsa/)は、目標・予測を置き、実際の結果を学び、次の試行へ反映する説明。NPSでは機械検査をCheckとして残しつつ、意味や方法の見直しをStudyとして区別する。
- [Microsoft ResearchのHuman-AI Interaction研究](https://www.microsoft.com/en-us/research/wp-content/uploads/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf)は、修正しやすさ、粒度の細かいfeedback、慎重な適応、利用者の制御を扱う。NPSでは採否を小単位で保存し、勝手な共通ルール化を避ける。
- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)は継続的な評価、利用者feedbackと改善、測定手段の見直しを扱い、機能を必ず順番に行うチェックリストとはしていない。大4/大5を独立した継続範囲とする設計に整合する。

これらは設計上の根拠であり、NPSの5段階自体の効果を実験で確認した証拠ではない。測る項目は意図しない変更件数、再発した指摘、保留案の本文混入、採否提示の分かりやすさ、次回での本人修正保持。記事の質はこれらの件数だけで評価しない。

- [Argyrisの組織学習の論考（出版社要約）](https://store.hbr.org/product/double-loop-learning-in-organizations/77502)は、既存目標の下で誤りを直すことと、目標・方針自体を問い直すことを区別する。NPSでは小ループの誤字修正と、大ループの「そもそもこの目次必須は適切か」の再設計を分ける。要約を確認した範囲での適用で、全文を読んだとは扱わない。
- [Maslow 1943原論文](https://worrydream.com/refs/Maslow_1943_-_A_Theory_of_Human_Motivation.pdf)は人間の動機についての理論。編集ループの5区分を裏付けるものではなく、NPSでは階層を固定した順序や優劣にしない。

適切性の判断: 粒度ごとの入れ子のループと、目的・規則そのものを見直す大ループは上記研究・指針と整合する。『5が唯一の適切な数』『上段へ進むほど記事が良い』という主張にはしない。小ループの完了を、大ループの有効性・公開結果・全AIへの反映に代用しない。
