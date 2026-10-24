# 検査ツールの保全

`ai_ratchet_gate` は、取り込み元の保全済み wheel 内の Python ソース3件とライセンス1件をテキストとして保存したものです。外部取得や同名パッケージへの置換は行いません。

元 wheel の SHA-256 は `b3f22ab772699d57906326e42189e0ab7a0ee9e33dcad55a90909ece35106cd7` です。ソースの改行を LF に統一し、各ファイルの SHA-256 を `ratchet-source-hashes.json` に保存しています。CI は実行前に照合します。

実行例: `PYTHONPATH=vendor python3 -m ai_ratchet_gate --repo .`

原配布元は移行前の `nexus-ai-2045/ai-ratchet-gate` の v0.1.1 release、元 wheel は10,108 bytesです。現在の同名リポジトリから生成したものとは区別します。Python本体やテスト依存全体をオフライン提供するものではありません。

更新は新しい上流成果物・ライセンス・出典・ハッシュをレビューした変更として行います。実装の編集元は上流リポジトリとし、ハッシュ不一致は停止させます。基準値や検査設定で免除しません。
