# 記事ごとの論点台帳と照合

複数の壁打ちを使う記事では、原稿を書く前に会話ごとの論点を JSON 台帳へ抽出する。`topic_status_check.py` は NPS 製品の課題台帳用であり、この記事単位の検査には使わない。

```json
{
  "schema_version": "note-topic-coverage/v1",
  "sources": [
    {
      "id": "current-conversation",
      "kind": "codex_conversation",
      "uri": "conversation://current",
      "capture_status": "complete"
    },
    {
      "id": "grok-conversation",
      "kind": "grok_conversation",
      "uri": "https://grok.com/c/example",
      "capture_status": "partial"
    }
  ],
  "topics": [
    {
      "id": "work-income-fear",
      "topic": "仕事を失うことへの収入面の不安",
      "source_id": "current-conversation",
      "origin": "user_speech",
      "evidence": "turn 42",
      "disposition": "include",
      "destination": "A3 / 導入"
    },
    {
      "id": "distribution-model",
      "topic": "分配の一案",
      "source_id": "grok-conversation",
      "origin": "ai_suggestion",
      "evidence": "reply 3",
      "disposition": "defer",
      "destination": "A4 検討メモ",
      "reason": "A3 の範囲外"
    }
  ]
}
```

- `sources` は対話ごとに一件。`capture_status` は `complete`、`partial`、`missing`。全文を保存・照合していない対話を `complete` にしない。
- `topics` は論点ごとに一件。`origin` は `user_speech`、`external_source`、`ai_suggestion`。Grok などの提案を本人の発言として記録しない。
- `disposition` は `include`、`defer`、`exclude`、`hold`。全件に `destination` を書き、`defer` と `exclude` には `reason` を書く。`hold` は行き先を決めるまでの保留として使う。
- 本文に採用した論点の直前へ `<!-- topic: work-income-fear -->` のような独立行を置く。HTML コメントなので通常の Markdown 表示には出ない。各 ID は本文に一回だけ置く。

```sh
python scripts/draft_topic_coverage_check.py <topics.json> <draft.md> --json
```

検査は全台帳行の分類、採用論点の本文マーカー、保留・除外先、ソースの取得状態を確認する。`partial` / `missing` は `ok=false` となり、未取得の対話があることを隠さない。検査は**台帳に列挙された論点**を照合する。元会話からの抽出漏れを自動発見する機能ではないため、会話全文と台帳の人間レビューは別に必要。壁打ちは論点と仮説の素材であり、外部事実の根拠にはならない。公開可否もこの検査の結果だけでは決めない。
