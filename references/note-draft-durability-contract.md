# Note下書き耐久性契約

## 目的

Git未追跡の下書きが別worktreeに残っている、または元の場所から見えなくなった時に、
削除と即断せず、所在と復元可能性を機械判定する。

## 同一性

- repository identity: `git rev-parse --git-common-dir` の解決先。linked worktree間で共有する。
- worktree identity: worktree rootの解決済み絶対path。作業場所を区別する。
- source identity: worktree rootからの相対pathと絶対pathをreceiptに併記する。

同じrepository identity・相対pathのreceiptが別worktreeを指し、そのsourceが現在も
通常fileとして実在してreceiptのhashと一致する場合、`status` は
`found_in_other_worktree` として停止する。古いreceiptだけでは別worktree現存と判定しない。
自動コピー、上書き、削除は行わない。

## 保存形式

既定保存先は `%LOCALAPPDATA%\nexus-ai\draft-history\<repo-id>`。repository外を必須とする。
macOS / Linuxなど `LOCALAPPDATA` のない環境では、workspaceが選択したrepository外の
保存先を `--backup-root <private-backup-root>` で必ず明示する。package内へフォールバックしない。

- `blobs/<sha256>.<suffix>`: 内容アドレス方式の本文。同内容は再利用する。
- `receipts/*.json`: 1回のsnapshotにつき1件の不変receipt。backup rootからreceiptまでの
  symlink/reparse pointを拒否し、原子的create-newで作成して既存receiptを置換しない。
- blobとreceiptは同一directory内の一時fileへ書き、`fsync` 後に`os.replace`する。
- 既存blob確認と保存直後確認は、同一handleのidentity・size・mtimeを照合してから
  SHA-256を再検証する。新規書込み前にもbackup rootからblob parentまでの
  symlink/reparse pointを拒否する。
- receiptのblob pathはlexicalにも同じrepo-id namespaceの
  `blobs/<sha256>.<suffix>`と一致する場合だけ許可する。backup rootからblobまでの
  symlinkおよびWindows reparse pointは拒否する。
- 初期版は世代を自動削除しない。

本文、Cookie、tokenを標準出力やreceiptへ複製しない。receiptはlocal-onlyであり、
公開物やGitへ追加しない。

## CLI

```powershell
python scripts/note_draft_durability.py snapshot --draft <draft> --repo-root <worktree> --reason before_edit --json
python scripts/note_draft_durability.py status --draft <draft> --repo-root <worktree> --json
python scripts/note_draft_durability.py verify --receipt <receipt.json> --json
python scripts/note_draft_durability.py restore --receipt <receipt.json> --to <new-path> --json
```

終了コードは、検証済み・現在版・復元済みが`0`、未保護・stale・別worktree発見が`2`、
入力または安全境界違反が`3`、I/O失敗が`4`。

## Fail closed

次の場合は書込みや後続工程へ進まない。

- source不在、repository外、通常fileでない、symlink、許可外suffix、明示なしの空file。
- backup rootがrepository内。
- 読取り中のidentity/size/mtime変化、blob/receipt/hash/schema/path不整合。
- 既存復元先への書込み。Windows上の非協調書込みとの安全なCASを保証できないため、
  初期版はexpected hashの有無にかかわらず拒否する。復元先の公開時にも原子的な
  create-newを使い、存在確認後に競合fileが作られた場合も置換しない。filesystem
  anchorから復元先までのsymlink/reparse pointも拒否する。
- 元pathが不在なのに`--restore-missing-original`がない。
- 別worktreeに同じ相対pathのsnapshotがある。

失敗時もsource、既存blob、既存receiptを削除しない。

## 保証境界

保証するのは、検証済みreceiptがある版について、blob整合確認と安全な別path復元が
できること。CLIを通さない編集、保存先disk自体の故障、Noteクラウド側、削除主体の
事後特定は保証しない。
