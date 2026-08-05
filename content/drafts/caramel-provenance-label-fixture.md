---
title: Caramel 完全解説 provenance label fixture
status: draft
article_lane: production_candidate
source_mode: source_pack_locked_with_user_speech_priority
based_on:
  source_pack: fixtures/caramel-public-source-pack.md
  user_speech: fixtures/caramel-user-speech-notes.md
  skeleton: fixtures/caramel-complete-guide-skeleton.md
allowed_use:
  - user-said は本人発言の優先ソースとして扱う
  - external-fact は source_pack の事実確認だけに使う
  - assistant-organized は構成、接続、読み順だけに使う
  - hold は未確認や追加確認の隔離に使う
not_allowed:
  - user-said を外部事実として扱う
  - assistant-organized を出典事実として扱う
  - hold を公開本文に混ぜる
editor_test_allowed: false
publication_gate: human_review_required
external_action: none
---

<!-- provenance-label: assistant-organized; source: assistant_structure -->
# Caramel 完全解説

導入では、まず読者が迷いやすい言葉をそろえ、本文全体の読み順を示す。
ここは構成のための橋渡しであり、新しい事実根拠としては扱わない。

<!-- provenance-label: user-said; source: user_speech_notes -->
ユーザーは、Caramel を単なる機能紹介ではなく、使う前に判断できる
「完全解説」として整理したいと話していた。
読者が知りたい順番を優先し、細部よりも意思決定の助けになる説明に寄せる。

<!-- provenance-label: external-fact; source: external_source_pack -->
Caramel の仕様、提供元、料金、公開日、利用条件などの断定は、
source pack に固定された公開情報だけを根拠にする。
本文では、source pack にない数字や比較表現を追加しない。

<!-- provenance-label: assistant-organized; source: assistant_transition -->
次の章では、概要、できること、向いている読者、注意点の順で並べる。
この並び替えは説明設計であり、外部事実や本人発言を増やすものではない。
