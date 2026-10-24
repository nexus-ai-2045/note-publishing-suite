# 記事版とworkspace台帳の契約

`note_article_version.py` は、利用者のworkspaceが明示選択した既存の `published_notes.json` の記事版を準備・確定・取り消す。祖先ディレクトリやNPS package内の台帳を探索しない。`--ledger` は必須で、package内を指定すると停止する。

既定はdry-runで、提案される記事recordを表示するだけ。`--write-ledger` を明示した時だけ、既存の公開台帳と共通のOS lock内で読取り・変更・原子的保存を行う。公開本文snapshotまたは公開後台帳の未完了transactionがあれば停止し、元の処理での復旧を求める。独立した版管理台帳は作らない。

```bash
python3 scripts/note_article_version.py --note-id <note-id> --ledger <workspace>/data/published_notes.json prepare --reason "誤記修正"
python3 scripts/note_article_version.py --note-id <note-id> --ledger <workspace>/data/published_notes.json --write-ledger prepare --reason "誤記修正"
```

`finalize --observed-title` は準備したtitleとの完全一致が必要。`cancel` / `abort --reason` は公開済み版を保持し、未公開の準備版だけを取り消す。いずれも既定dry-run。台帳への確定はNote本文の変更、公開、読戻しの代行ではなく、別途取得した観測に基づくローカル記録である。
