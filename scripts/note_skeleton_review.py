"""段落単位の骨組み JSON から、1話1ページの確認用 HTML と一覧ページを作る。
各段落に通し番号と出どころの印を付け、どの行にも「どこから入ったか」を添える。
見出しは開け閉めでき、見出しごとに口述待ちの数と色の点を出す。右端の色の帯で1話の形を、
上の印で出どころの絞り込みを見せる。JS は見出しの開閉、リンク先の展開、色の帯の「今ここ」と、
ローカル閲覧時の生成版更新を扱う。"""
import argparse
import hashlib
import html
import json
import re
import sys
from urllib.parse import urlsplit
from pathlib import Path
from note_skeleton_review_check import validate_writing_plans, writing_plan_html

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workspace-root", type=Path, required=True, help="記事と原資料を所有する利用側workspace")
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--draft", type=Path, action="append", default=[],
                    help="文字数を宣言した各話の実本文。hash一致と既存本文字数規則で検査する")
args = parser.parse_args()
src, outdir = args.source.resolve(), args.output.resolve()
workspace_root = args.workspace_root.resolve(strict=True)
outdir.mkdir(parents=True, exist_ok=True)
source_bytes = Path(src).read_bytes()
data = json.loads(source_bytes)
validate_writing_plans(data)
WRITING_PLAN_MODE = isinstance(data, dict) and data.get('skeleton_mode') == 'writing-plan'
GENERATION_VERSION = hashlib.sha256(
    source_bytes + Path(__file__).read_bytes()
    + Path(__file__).with_name("note_skeleton_review_check.py").read_bytes()
).hexdigest()
sync = data.get("sync", {}) if isinstance(data, dict) else {}
series = data.get("series", {}) if isinstance(data, dict) else {}
PROVENANCE_NOTICE = "由来ラベルは保存資料の申告です。本人由来の確認は原文引用・hash・本文対応の検査と併用してください。"
index_heading = series.get("title", "連載の骨組み")
index_title = series.get("index_title", "骨組み 一覧")
eps = data["episodes"] if isinstance(data, dict) else data
if (not isinstance(eps, list) or any(not isinstance(ep, dict) or type(ep.get("n")) is not int or ep["n"] < 1 for ep in eps)
        or len({ep["n"] for ep in eps}) != len(eps)):
    raise ValueError("各話nは重複のない正の整数で指定してください")
eps = sorted(eps, key=lambda ep: ep["n"])
for ep in eps:
    for section in ep.get("sections", []):
        for paragraph in section.get("paragraphs", []):
            urls = (paragraph.get("check") or {}).get("urls", [])
            if not isinstance(urls, list):
                raise ValueError("出典リンクはURLの配列で指定してください")
            for url in urls:
                if not isinstance(url, str):
                    raise ValueError("出典リンクは文字列で指定してください")
                parsed = urlsplit(url)
                if (parsed.scheme not in ("http", "https") or not parsed.hostname
                        or parsed.username or parsed.password):
                    raise ValueError("出典リンクは認証情報のないHTTP(S) URLに限定します")
                parsed.port  # 不正なportも出力前に拒否する。

# Legacy skeletons have estimates only. Declared actual counts require actual
# draft bytes, not a number copied from the input JSON.
draft_snapshots = {path: path.read_bytes() for path in args.draft}
drafts = {hashlib.sha256(raw).hexdigest(): raw.decode("utf-8-sig")
          for raw in draft_snapshots.values()}
for episode in eps:
    counts = episode.get("character_counts")
    if counts is None:
        continue
    if not isinstance(counts, dict) or counts.get("draft_sha256") not in drafts:
        raise ValueError("character_countsにはhash一致する実本文 --draft が必要です")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from note_skeleton_source_gate import nps_body_character_count
    actual_body = nps_body_character_count(drafts[counts["draft_sha256"]])
    raw_count = 0
    for section in episode.get("sections", []):
        for paragraph in section.get("paragraphs", []):
            text = paragraph.get("text")
            if not isinstance(text, str):
                raise ValueError("骨組み原文textは文字列が必要です")
            raw_count += sum(not character.isspace() for character in text)
    for key, actual in (("draft_body_no_whitespace", actual_body),
                        ("skeleton_paragraph_text_no_whitespace", raw_count)):
        if type(counts.get(key)) is not int or counts[key] != actual:
            raise ValueError(f"character_counts.{key}が実測と一致しません")
    episode["character_counts"] = {**counts, "draft_body_no_whitespace": actual_body,
                                    "skeleton_paragraph_text_no_whitespace": raw_count}
if any(path.read_bytes() != raw for path, raw in draft_snapshots.items()):
    raise ValueError("本文が文字数検査中に変更されました")

MARK = {"本人の発言": ("self", "本人"), "AIの案": ("ai", "AI"), "口述が必要": ("need", "口述待ち"), "公開本文": ("pub", "公開")}
KINDS = [k for k, _ in MARK.values()]
e = html.escape
OPENING = "（冒頭・見出しなし）"

LIGHT = "--bg:#f6f5f1;--p:#fff;--ink:#1f2328;--mu:#646c77;--ln:#e2dfd8;--ac:#2f3a8f;--self:#1a7a4b;--selfb:#e2f3ea;--ai:#9a5a00;--aib:#fbefd9;--need:#c0262f;--needb:#fde8ea;--pub:#7a828c;--pubb:#ecebe6;--mix:#6b3fb8"
DARK = "--bg:#15171b;--p:#1e2127;--ink:#e7e7e4;--mu:#a2a8b2;--ln:#30343b;--ac:#aab1ff;--self:#6fd3a0;--selfb:#17302a;--ai:#f2bb63;--aib:#33281a;--need:#ff8f99;--needb:#3a1d21;--pub:#8d939c;--pubb:#2a2d33;--mix:#c3a6ff"
# 主張の種類: 事実と混在をまとめて「事実を含む」で絞り込む
CLAIM = {"意見": "op", "事実": "fact", "混在": "mix", "構成": "plan"}
CHECK_CLASS = {"資料で確認済み": "ok", "合っている": "ok", "おおむね合っている": "ok", "要旨のみ確認": "part", "一部のみ確認": "part",
               "確かめられない": "part", "確認待ち": "wait", "一部違う": "ng", "違う": "ng", "前提が違う": "ng", "言い直し済み": "ok"}
# 絞り込み: 本文は選んだ行だけ残し、当てはまる行のない見出しも隠す。色の帯と点は地図なので薄くするだけ
FILTERS = [(k, k) for k in KINDS] + [(f"c{k}", f"c-{k}") for k in ("fact", "op")]
HIDE = ",".join(f"body:has(#f-{fid}:checked) {sel}" for fid, cls in FILTERS for sel in (
    f".rows>li:not(.{cls})", f"details.s3:not(:has(.rows>li.{cls}))", f"details.s2:not(:has(.rows>li.{cls}))"))
DIM = ",".join(f"body:has(#f-{fid}:checked) {sel}:not(.{cls})" for fid, cls in FILTERS for sel in (".strip a", ".dots i")
               if not (cls.startswith("c-") and sel == ".dots i"))

CSS = f"""
:root{{{LIGHT}}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{DARK}}}}}
:root[data-theme="dark"]{{{DARK}}}
*{{box-sizing:border-box}}html{{scroll-padding-top:64px}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 "Hiragino Sans","Noto Sans JP",system-ui,sans-serif}}
main{{max-width:880px;margin:0 auto;padding:10px 26px 80px 16px}}a{{color:var(--ac)}}
.nav{{display:flex;gap:6px;flex-wrap:wrap;font-size:12px;margin:0 0 8px}}
.nav a,.nav .cur{{border:1px solid var(--ln);background:var(--p);border-radius:999px;padding:1px 10px;text-decoration:none}}
.nav .cur{{background:var(--ac);border-color:var(--ac);color:#fff}}
h1{{font-size:19px;margin:2px 0}}.sub{{color:var(--mu);font-size:12px;margin:0 0 6px}}
.bar{{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--ln);padding:6px 0;margin:0 0 10px;display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;font-size:12px}}
.grp{{display:flex;flex-wrap:wrap;gap:4px;align-items:center}}.lb{{color:var(--mu);margin-right:2px}}
.flt input{{position:absolute;opacity:0;pointer-events:none}}
.chip{{display:inline-block;font-size:11.5px;font-weight:700;border-radius:999px;padding:0 9px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;background:var(--pubb);color:var(--ink);line-height:1.8}}
.flt input:checked+.chip{{border-color:currentColor}}.flt input:focus-visible+.chip{{outline:2px solid var(--ac)}}
.vw button{{font:inherit;font-size:11.5px;border:1px solid var(--ln);background:var(--p);color:var(--ink);border-radius:6px;padding:0 8px;line-height:1.8;cursor:pointer}}
.vw button.on{{background:var(--ac);color:#fff;border-color:var(--ac)}}
.m{{display:inline-block;font-size:11px;font-weight:700;border-radius:4px;padding:0 6px;line-height:1.7;white-space:nowrap}}
.self.m,.self.chip{{color:var(--self);background:var(--selfb)}}.ai.m,.ai.chip{{color:var(--ai);background:var(--aib)}}
.need.m,.need.chip{{color:var(--need);background:var(--needb)}}.pub.m,.pub.chip{{color:var(--pub);background:var(--pubb)}}
.dots{{display:inline-flex;flex-wrap:wrap;gap:2px;vertical-align:middle;max-width:100%}}
.dots i{{width:7px;height:7px;border-radius:50%;background:var(--pub)}}
.dots i.self{{background:var(--self)}}.dots i.ai{{background:var(--ai)}}.dots i.need{{background:var(--need)}}
.meta{{font-size:11px;color:var(--mu);font-weight:400;display:inline-flex;flex-wrap:wrap;gap:2px 8px;align-items:center}}
.needc{{color:var(--need);font-weight:700}}
.toc{{background:var(--p);border:1px solid var(--ln);border-radius:10px;padding:8px 12px;margin:0 0 12px}}
.toc>b{{font-size:12px;color:var(--mu)}}.toc ol{{list-style:none;margin:0;padding:0}}.toc>ol>li{{margin:4px 0}}
.toc .l1{{display:flex;flex-wrap:wrap;align-items:center;gap:0 8px}}.toc .l1 a{{font-weight:700;color:var(--ink);text-decoration:none}}
.tn{{color:var(--ac);font-weight:800;display:inline-block;min-width:2.4em}}
.toc ul{{margin:0 0 0 2.4em;padding:0;list-style:none;font-size:12.5px}}.toc ul li::before{{content:"– ";color:var(--mu)}}
.toc ul a{{color:var(--ink);text-decoration:none}}.toc a:hover{{color:var(--ac)}}
summary{{list-style:none;cursor:pointer}}summary::-webkit-details-marker{{display:none}}
summary::before{{content:"▸";color:var(--mu);font-size:11px;display:inline-block;transition:rotate .15s}}details[open]>summary::before{{rotate:90deg}}
details.s2{{margin:14px 0 4px}}
details.s2>summary{{display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:15.5px;font-weight:800;padding:5px 10px;background:var(--p);border:1px solid var(--ln);border-left:6px solid var(--ac);border-radius:6px}}
details.s3{{margin:8px 0 2px 12px}}
details.s3>summary{{display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:14px;font-weight:700;padding:1px 8px;border-left:3px solid var(--ln)}}
summary .n{{color:var(--ac)}}summary .meta{{margin-left:auto}}
.rows{{list-style:none;margin:2px 0 0;padding:0}}details.s3 .rows{{margin-left:14px}}
.rows>li{{display:grid;grid-template-columns:1.9em 4.4em minmax(0,1fr);gap:0 6px;padding:5px 6px 5px 2px;border-bottom:1px solid var(--ln);border-left:3px solid var(--pub)}}
.rows>li.self{{border-left-color:var(--self)}}.rows>li.ai{{border-left-color:var(--ai)}}.rows>li.need{{border-left-color:var(--need);background:var(--needb)}}
.rows .no{{color:var(--mu);font-size:11px;text-align:right;padding-top:3px;font-variant-numeric:tabular-nums}}
.rows .edited-text{{display:block;white-space:pre-line;border-left:2px solid var(--ln);padding-left:10px;margin-top:6px;line-height:1.65}}
.rows .m{{justify-self:start;align-self:start;margin-top:2px}}.rows .t{{min-width:0}}.rows>li.pub .t{{color:var(--mu)}}
.src{{grid-column:3;font-size:11.5px;color:var(--mu);overflow-wrap:anywhere}}.src::before{{content:"どこから: "}}
.rows>li.ai .src{{color:var(--ai)}}.rows>li.need .src{{color:var(--need)}}
.rows>li:target{{outline:2px solid var(--ac);outline-offset:-2px}}
.tags{{display:flex;flex-direction:column;gap:3px;align-items:flex-start}}
.ct{{display:inline-block;font-size:10.5px;font-weight:700;border-radius:4px;padding:0 5px;line-height:1.55;border:1px solid var(--ln);color:var(--mu);white-space:nowrap}}
.ct.fact{{border-color:var(--ac);color:var(--ac)}}.ct.mix{{border-color:var(--mix);color:var(--mix)}}.ct.plan{{border-style:dashed}}
.chk{{grid-column:3;font-size:11.5px;font-weight:600;overflow-wrap:anywhere}}.chk::before{{content:"確認: "}}
.chk.ok{{color:var(--self)}}.chk.part{{color:var(--ai)}}.chk.wait{{color:var(--ac)}}.chk.ng{{color:var(--need)}}
.chk a{{color:inherit}}
.how{{font-size:11.5px;color:var(--mu);margin:0 0 6px}}
.fig{{grid-column:3;margin:6px 0 4px;display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1fr);gap:3px;font-size:12px}}
.fig .ax{{font-weight:700;color:var(--mu);font-size:11px;align-self:center;text-align:center;padding:2px 4px}}
.fig .rh{{font-weight:700;font-size:11.5px;align-self:stretch;display:flex;align-items:center;padding:4px 6px;border-radius:6px;background:var(--pubb)}}
.fig .rh.pref{{background:var(--selfb);color:var(--self)}}
.fig .cell{{border-radius:6px;padding:6px 8px;line-height:1.45;border:1px solid var(--ln)}}
.fig .bad{{background:var(--needb)}}.fig .good{{background:var(--selfb)}}
.fig .pn{{grid-column:1/-1;font-size:11.5px;color:var(--self)}}
.fig .cap{{grid-column:1/-1;font-size:11px;color:var(--mu)}}
.strip{{position:fixed;right:3px;top:64px;bottom:10px;width:11px;display:flex;flex-direction:column;gap:1px;z-index:4}}
.strip a{{flex:1 1 0;min-height:2px;border-radius:2px;background:var(--pub)}}
.strip a.self{{background:var(--self)}}.strip a.ai{{background:var(--ai)}}.strip a.need{{background:var(--need)}}
.strip a:hover{{outline:1px solid var(--ink)}}.strip a.cur{{outline:2px solid var(--ink);outline-offset:1px}}
.strip .gap{{flex:0 0 5px}}
{HIDE}{{display:none}}
{DIM}{{opacity:.18}}
details.notes{{background:var(--p);border:1px solid var(--ln);border-radius:10px;padding:6px 12px;margin-top:18px}}
details.notes>summary{{font-weight:700;font-size:13.5px}}details.notes li{{margin:3px 0;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}}
.card{{background:var(--p);border:1px solid var(--ln);border-radius:10px;padding:10px 12px;text-decoration:none;color:var(--ink);display:block}}
.card:hover{{border-color:var(--ac)}}.card b{{color:var(--ac)}}.card .t{{font-weight:700;margin:2px 0 4px}}.card .c{{font-size:12px;color:var(--mu)}}
.card .dots{{margin:4px 0}}.card ol{{margin:4px 0 0;padding-left:1.4em;font-size:12.5px}}.card ol .needc{{font-size:11px;margin-left:4px}}
.card h2{{font-size:16px}}.card a{{text-decoration:none}}.card a:hover{{text-decoration:underline}}
.card .outline>li{{margin:8px 0}}.card .outline>li>a{{font-weight:700}}
.card .outline ul{{margin:3px 0 0;padding-left:1.25em;color:var(--mu)}}
.heading-origin.self{{color:var(--self)}}.heading-origin.ai{{color:var(--ai)}}
.heading-origin.need{{color:var(--need)}}.heading-origin.pub{{color:var(--pub)}}
.card .outline ul li{{margin:3px 0}}
.writing-plan{{background:var(--p);border:1px solid var(--ln);border-radius:8px;padding:12px;margin:8px 0}}
.writing-plan>ol{{padding-left:1.5em}}.plan-item{{margin:12px 0}}.plan-item p{{white-space:pre-line;margin:4px 0}}
.plan-basis,.adoption,.external-sources{{font-size:12px;color:var(--mu);overflow-wrap:anywhere}}
.plan-evidence{{margin:8px 0}}.plan-evidence>summary{{font-size:12px;color:var(--mu)}}
.plan-references>summary{{font-size:12px;color:var(--mu)}}
"""

JS = """(function(){
var KEY='a-skel-view';
function initialize(){
function openUp(t){var d=t&&t.closest('details');while(d){d.open=true;d=d.parentElement&&d.parentElement.closest('details');}}
function setView(v){
 document.querySelectorAll('details.s2').forEach(function(d){d.open=v!=='h2';});
 document.querySelectorAll('details.s3').forEach(function(d){d.open=v==='all';});
 document.querySelectorAll('[data-view]').forEach(function(b){b.classList.toggle('on',b.dataset.view===v);});
 try{localStorage.setItem(KEY,v);}catch(e){}
}
document.querySelectorAll('[data-view]').forEach(function(b){b.addEventListener('click',function(){setView(b.dataset.view);});});
try{var v=localStorage.getItem(KEY);if(v&&v!=='all')setView(v);}catch(e){}
function reveal(){var id=decodeURIComponent(location.hash.slice(1));if(id)openUp(document.getElementById(id));}
if(!window.aSkeletonListenersInstalled){
window.aSkeletonListenersInstalled=true;
document.addEventListener('click',function(ev){var a=ev.target.closest('a[href^="#"]');if(a)openUp(document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))));},true);
addEventListener('hashchange',reveal);}
reveal();
// 色の帯の「今ここ」。CSS の scroll-target-group は、見出しを全部閉じた状態で読み込むと Chromium 145 が落ちたので使わない
if(window.aSkeletonObserver)window.aSkeletonObserver.disconnect();
var strip=document.querySelector('.strip');
if(strip&&'IntersectionObserver' in window){
 var map={},cur=null;strip.querySelectorAll('a').forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
 var io=new IntersectionObserver(function(es){es.forEach(function(en){var a=map[en.target.id];if(en.isIntersecting&&a){if(cur)cur.classList.remove('cur');cur=a;a.classList.add('cur');}});},{rootMargin:'-70px 0px -75% 0px'});
 window.aSkeletonObserver=io;
 document.querySelectorAll('.rows>li[id]').forEach(function(li){io.observe(li);});
}
}
initialize();
// ローカルの読書ページだけ、生成版の変化を確かめる。状態はこのページ内だけに保持する。
if((location.protocol==='http:'||location.protocol==='https:')&&
   (location.hostname==='127.0.0.1'||location.hostname==='localhost')){
 var checking=false;
 function detailKey(d){
  var names=[];
  while(d){var summary=d.querySelector(':scope > summary');
   var name=summary&&summary.querySelector(':scope > span:nth-child(2)');
   names.unshift(name?name.textContent:(summary?summary.textContent:d.id));
   d=d.parentElement&&d.parentElement.closest('details');}
  return names.join(' / ');
 }
 setInterval(async function(){
  if(checking)return;checking=true;
  try{
   var response=await fetch(location.href,{cache:'no-store',credentials:'omit'});
   if(!response.ok)return;
   var next=new DOMParser().parseFromString(await response.text(),'text/html');
   var currentVersion=document.querySelector('meta[name="generation-version"]');
   var nextVersion=next.querySelector('meta[name="generation-version"]');
   var nextMain=next.querySelector('main');
   if(!currentVersion||!nextVersion||!nextMain||currentVersion.content===nextVersion.content)return;
   var scroll=window.scrollY,states=new Map();
   document.querySelectorAll('details').forEach(function(d){states.set(detailKey(d),d.open);});
   var filter=document.querySelector('.flt input:checked');
   var filterId=filter&&filter.id;
   var view=document.querySelector('[data-view].on');
   var viewName=view&&view.dataset.view;
   var anchor=Array.from(document.querySelectorAll('.rows > li[id],details.s2[id]'))
    .find(function(el){return el.getBoundingClientRect().top>=0;});
   var anchorId=anchor&&anchor.id,anchorOffset=anchor&&anchor.getBoundingClientRect().top;
   document.querySelector('main').replaceWith(nextMain);
   var nextStyle=next.querySelector('style');
   if(nextStyle)document.querySelector('style').textContent=nextStyle.textContent;
   document.title=next.title;currentVersion.content=nextVersion.content;
   initialize();
   if(viewName)document.querySelectorAll('[data-view]').forEach(function(b){b.classList.toggle('on',b.dataset.view===viewName);});
   document.querySelectorAll('details').forEach(function(d){var key=detailKey(d);if(states.has(key))d.open=states.get(key);});
   var restoredFilter=filterId&&document.getElementById(filterId);
   if(restoredFilter)restoredFilter.checked=true;
   requestAnimationFrame(function(){var restoredAnchor=anchorId&&document.getElementById(anchorId);
    window.scrollTo(0,restoredAnchor?window.scrollY+restoredAnchor.getBoundingClientRect().top-anchorOffset:scroll);});
  }catch(error){/* 接続できないときは読んでいる版を保つ。 */}
  finally{checking=false;}
 },5000);
}
})();"""


def split_heading(h):
    parts = re.split(r"\s*[＞>]\s*", h, maxsplit=1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (h.strip(), None)


def chars_of(s):
    m = re.search(r"\d[\d,]*", str(s.get("chars") or ""))
    return int(m.group().replace(",", "")) if m else 0


def group(sections):
    out = []
    for s in sections:
        h2, h3 = split_heading(s["heading"])
        if not out or out[-1]["h2"] != h2:
            out.append({"h2": h2, "direct": [], "direct_sections": [], "subs": [], "chars": 0, "plan_count": 0})
        g = out[-1]
        g["chars"] += chars_of(s)
        g["plan_count"] += len(s.get('writing_plan', {}).get('items', []))
        if h3 is None:
            g["direct"].extend(s["paragraphs"])
            g["direct_sections"].append(s)
        else:
            g["subs"].append({"h3": h3, "paras": s["paragraphs"], "chars": chars_of(s), "section": s})
    return out


def short_title(t):
    t = re.sub(r"^第\d+[話回]｜?", "", t)
    return re.sub(r"（.*?）$", "", t).strip()


def status(ep):
    current = ep.get("status", "")
    normalized = str(current).strip().lower().replace("_", "-")
    if "published-readback" in normalized:
        return "公開済み（読戻し済み）"
    if "author-review-pending" in normalized:
        return "著者レビュー待ち"
    if "公開済み" in current:
        return "公開済み"
    if "壁打ち中" in current:
        return "壁打ち中"
    if "制作中" in current:
        return "制作中"
    return "未着手"


def kind(p):
    return MARK.get(p["source"], ("ai", "AI"))[0]


def heading_origin(paragraphs):
    """Use the existing legend palette for the section's main source."""
    counts = {key: sum(kind(p) == key for p in paragraphs) for key in KINDS}
    return max(KINDS, key=counts.get) if any(counts.values()) else "none"


def heading_link(href, title, paragraphs):
    origin = heading_origin(paragraphs)
    label = dict(MARK.values()).get(origin, "段落なし・未分類")
    return (f'<a class="heading-origin {origin}" href="{e(href)}" '
            f'title="{"根拠" if WRITING_PLAN_MODE else "本文"}の主な出どころ: {e(label)}">{e(title)}</a>')


def dots(paras):
    return f'<span class="dots">{"".join(f"<i class={kind(p)}></i>" for p in paras)}</span>'


def count_label(paras, plan_count=0):
    if WRITING_PLAN_MODE:
        return f'書く内容{plan_count}項目・根拠{len(paras)}件'
    return f'{len(paras)}段落'


def meta(paras, chars, plan_count=0):
    need = sum(1 for p in paras if p["source"] == "口述が必要")
    parts = [dots(paras), count_label(paras, plan_count) + (f"・約{chars:,}字" if chars else "")]
    if need:
        parts.append(f'<span class="needc">口述待ち {need}</span>')
    return f'<span class="meta">{"".join(f"<span>{x}</span>" for x in parts)}</span>'


def figure_html(f):
    rows, cols, cells = f["rows"], f["cols"], f["cells"]
    tone = ["bad", "good"] if cols[0].startswith("最悪") else ["", ""]
    out = ['<div class="fig"><span></span>' + "".join(f'<span class="ax">{e(c)}</span>' for c in cols)]
    for i, r in enumerate(rows):
        pref = " pref" if f.get("pref_row") == i else ""
        out.append(f'<span class="rh{pref}">{e(r)}</span>' + "".join(
            f'<span class="cell {tone[j]}">{e(cells[i][j])}</span>' for j in range(len(cols))))
    if f.get("pref_note"):
        out.append(f'<span class="pn">● {e(f["pref_note"])}</span>')
    out.append('<span class="cap">下書きの絵（記事用の図はこれから作る）</span></div>')
    return "".join(out)


def claim_cls(p):
    c = CLAIM.get(p.get("claim", ""))
    if not c:
        return ""
    return " c-fact" if c in ("fact", "mix") else f" c-{c}"


def check_html(p):
    ck = p.get("check")
    if not ck:
        return ""
    cls = CHECK_CLASS.get(ck["status"], "part")
    note = f'　{e(ck["note"])}' if ck.get("note") else ""
    links = "".join(f'　<a href="{e(u)}" target="_blank" rel="noopener">出典{i}</a>' for i, u in enumerate(ck.get("urls", [])[:3], 1))
    return f'<span class="chk {cls}">{e(ck["status"])}{note}{links}</span>'


def row(p, no):
    k = kind(p)
    label = MARK.get(p["source"], ("ai", "AI"))[1]
    ref = (p.get("ref") or "").strip()
    fig = figure_html(p["figure"]) if p.get("kind") == "figure" and p.get("figure") else ""
    c = CLAIM.get(p.get("claim", ""))
    tag = f'<span class="ct {c}">{e(p["claim"])}</span>' if c else ""
    paragraph_id = f' data-paragraph-id="{e(p["id"])}"' if p.get("id") else ""
    text_html = e(p["text"])
    if p.get("edited_text") is not None:
        text_html = (f'<span class="raw-text">原文: {e(p["text"])}</span><br>'
                     f'<span class="edited-text">{"現稿対応" if p.get("draft_correspondence") else "編集案"}: {e(p["edited_text"])}</span>')
    return (f'<li class="{k}{claim_cls(p)}" id="p{no}"{paragraph_id}><span class="no">{no}</span><span class="tags"><span class="m {k}">{label}</span>{tag}</span>'
            f'<span class="t">{text_html}</span>{fig}<span class="src">{e(ref) if ref else "（記録なし）"}</span>{check_html(p)}</li>')


def nav(cur):
    links = ['<span class="cur">一覧</span>' if cur == 0 else '<a href="index.html">一覧</a>']
    for ep in eps:
        n = ep["n"]
        links.append(f'<span class="cur">第{n}話</span>' if n == cur else f'<a href="ep{n}.html">第{n}話</a>')
    return f'<div class="nav">{"".join(links)}</div>'


def bar(c, total, ordered):
    if WRITING_PLAN_MODE:
        views = ''.join(f'<button type="button" data-view="{v}"{" class=on" if v == "all" else ""}>{label}</button>'
                        for v, label in (("all", "書く内容まで"), ("h3", "小見出しまで"), ("h2", "大見出しだけ")))
        return f'<div class="bar"><div class="grp vw"><span class="lb">構成の表示</span>{views}</div></div>'
    chips = ['<input type="radio" name="f" id="f-all" checked><label for="f-all" class="chip">全部 ' + str(total) + "</label>"]
    for name, (k, label) in MARK.items():
        chips.append(f'<input type="radio" name="f" id="f-{k}"><label for="f-{k}" class="chip {k}">{label} {c.get(name, 0)}</label>')
    n_fact = sum(1 for p in ordered if p.get("claim") in ("事実", "混在"))
    n_op = sum(1 for p in ordered if p.get("claim") == "意見")
    if n_fact or n_op:
        chips.append(f'<input type="radio" name="f" id="f-cfact"><label for="f-cfact" class="chip">事実を含む {n_fact}</label>')
        chips.append(f'<input type="radio" name="f" id="f-cop"><label for="f-cop" class="chip">意見 {n_op}</label>')
    views = "".join(f'<button type="button" data-view="{v}"{" class=on" if v == "all" else ""}>{t}</button>'
                    for v, t in (("all", "段落まで"), ("h3", "小見出しまで"), ("h2", "大見出しだけ")))
    return (f'<div class="bar"><div class="grp flt"><span class="lb">絞り込み</span>{"".join(chips)}</div>'
            f'<div class="grp vw"><span class="lb">表示</span>{views}</div></div>')


def page(title, body):
    sync_parts = []
    if sync.get("updated_at"):
        sync_parts.append(f'壁打ち同期: {e(str(sync["updated_at"]))}')
    if sync.get("source_version"):
        sync_parts.append(f'原稿版: {e(str(sync["source_version"]))}')
    sync_info = f'<p class="sub">{"　".join(sync_parts)}</p>' if sync_parts else ""
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="generation-version" content="{GENERATION_VERSION}">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>'
            f"<style>{CSS}</style></head><body><main id=\"top\"><p>{e(PROVENANCE_NOTICE)}</p>{sync_info}{body}</main><script>{JS}</script></body></html>")


cards = []


def section_content(section, rows):
    evidence = f'<ul class="rows">{"".join(rows)}</ul>'
    plan = writing_plan_html(section)
    if not plan:
        return evidence
    return (plan + '<details class="plan-evidence"><summary>根拠の発言を確認</summary>'
            + evidence + '</details>')


for idx, ep in enumerate(eps):
    n = ep["n"]
    groups = group(ep["sections"])
    ordered = []  # 表示順の (番号, 段落)。本文・目次・色の帯で同じ番号を使う
    toc, body, strip, k = [], [], [], 0
    for i, g in enumerate(groups, 1):
        gid = f"g{i}"
        gp = g["direct"] + [p for s in g["subs"] for p in s["paras"]]
        if g["h2"] == OPENING:
            num, title = "冒頭", "見出しなし"
        else:
            k += 1
            num, title = str(k), g["h2"]
        direct_rows = []
        for section in g["direct_sections"]:
            rows_html = []
            for p in section['paragraphs']:
                ordered.append(p)
                rows_html.append(row(p, len(ordered)))
            direct_rows.append(section_content(section, rows_html))
        subs, subs_toc = [], []
        for j, s in enumerate(g["subs"], 1):
            sid = f"{gid}s{j}"
            rows_html = []
            for p in s["paras"]:
                ordered.append(p)
                rows_html.append(row(p, len(ordered)))
            sn = "" if g["h2"] == OPENING else f"{k}-{j}"
            subs.append(f'<details class="s3" id="{sid}" open><summary><span class="n">{sn}</span><span>{e(s["h3"])}</span>'
                        f'{meta(s["paras"], s["chars"], len(s["section"].get("writing_plan", {}).get("items", [])))}</summary>{section_content(s["section"], rows_html)}</details>')
            subs_toc.append(f'<li><a href="#{sid}">{e(s["h3"])}</a></li>')
        first = len(ordered) - len(gp) + 1
        if strip:
            strip.append('<i class="gap"></i>')
        strip.extend(f'<a href="#p{first + m}" class="{kind(p)}{claim_cls(p)}" title="{first + m} {MARK.get(p["source"], ("", "AI"))[1]}: {e(p["text"][:40])}"></a>'
                     for m, p in enumerate(gp))
        toc.append(f'<li><div class="l1"><a href="#{gid}"><span class="tn">{num}</span>{e(title)}</a>{meta(gp, g["chars"], g["plan_count"])}</div>'
                   + (f'<ul>{"".join(subs_toc)}</ul>' if subs_toc else "") + "</li>")
        body.append(f'<details class="s2" id="{gid}" open><summary><span class="n">{num}</span><span>{e(title)}</span>'
                    f'{meta(gp, g["chars"], g["plan_count"])}</summary>'
                    + "".join(direct_rows) + "".join(subs) + "</details>")
    c = {}
    for p in ordered:
        c[p["source"]] = c.get(p["source"], 0) + 1
    notes = "".join(f"<li>{e(x)}</li>" for x in ep.get("notes", []))
    pn = []
    episode_count_label = count_label(ordered, sum(g['plan_count'] for g in groups))
    if idx > 0:
        pn.append(f'<a href="ep{eps[idx-1]["n"]}.html">← 第{eps[idx-1]["n"]}話</a>')
    if idx < len(eps) - 1:
        pn.append(f'<a href="ep{eps[idx+1]["n"]}.html">第{eps[idx+1]["n"]}話 →</a>')
    html_body = (
        nav(n)
        + f'<h1>第{n}話　{e(short_title(ep["title"]))}</h1>'
        + (f'<p class="sub">{status(ep)}　実本文 {ep["character_counts"]["draft_body_no_whitespace"]:,}字　'
           f'原文骨組み {ep["character_counts"]["skeleton_paragraph_text_no_whitespace"]:,}字　'
           f'目標 {e(ep.get("target_chars", ""))}　{episode_count_label}</p>'
           if ep.get("character_counts") else
           f'<p class="sub">{status(ep)}　{e(ep.get("target_chars", ""))}　{episode_count_label}</p>')
        + (f'<p class="how">現稿との対応：保存素材 {e(str(ep["draft_correspondence"]["source_paragraphs"]))}件 → 本文 {e(str(ep["draft_correspondence"]["draft_body_paragraphs"]))}段落。'
           '各素材の「現稿対応」に、対応する本文をそのまま表示しています。未収録・一部未反映は、本人の不採用判断ではありません。</p>'
           if ep.get("draft_correspondence") else "")
        + bar(c, len(ordered), ordered)
        + ('<p class="how">印の見方: 上は出どころ（本人・AI・口述待ち・公開）、下は主張の種類（意見＝予測や考え、事実＝調べて確かめられる、混在＝両方を含む、構成＝話の組み立て）。事実の行には「確認」の結果。</p>'
           if any(p.get("claim") for p in ordered) else "")
        + f'<nav class="toc"><b>目次</b><ol>{"".join(toc)}</ol></nav>'
        + "".join(body)
        + (f'<details class="notes" open><summary>メモ（口述が要る所・本人確認・見立て）</summary><ul>{notes}</ul></details>' if notes else "")
        + f'<div class="nav" style="margin-top:16px">{"".join(pn)}<a href="#top">ページの先頭へ</a></div>'
        + f'<nav class="strip" aria-label="段落の色の帯（押すとその段落へ）">{"".join(strip)}</nav>'
    )
    (outdir / f"ep{n}.html").write_text(page(f"第{n}話 骨組み", html_body), encoding="utf-8")
    total_chars = sum(g["chars"] for g in groups)
    outline = []
    for i, g in enumerate(groups, 1):
        heading = "冒頭（見出しなし）" if g["h2"] == OPENING else g["h2"]
        subheadings = "".join(
            f'<li>{heading_link(f"ep{n}.html#g{i}s{j}", s["h3"], s["paras"])}</li>'
            for j, s in enumerate(g["subs"], 1)
        )
        outline.append(
            f'<li>{heading_link(f"ep{n}.html#g{i}", heading, g["direct"] + [p for sub in g["subs"] for p in sub["paras"]])}'
            + (f"<ul>{subheadings}</ul>" if subheadings else "") + "</li>"
        )
    character_counts = ep.get("character_counts", {})
    character_summary = (
        f'<div class="c">本文 {character_counts["draft_body_no_whitespace"]:,}字 / '
        f'原文骨組み {character_counts["skeleton_paragraph_text_no_whitespace"]:,}字 / '
        f'目標 {e(ep.get("target_chars", ""))}</div>'
        f'<div class="c">{episode_count_label}</div>'
        if character_counts else
        f'<div class="c">{episode_count_label}・見出しの字数の合計 約{total_chars:,}字</div>'
    )
    cards.append(
        f'<article class="card"><b class="heading-origin {heading_origin(ordered)}">第{n}話</b>　<span class="c">{status(ep)}</span>'
        f'<h2 class="t">{heading_link(f"ep{n}.html", short_title(ep["title"]), ordered)}</h2>'
        f'{character_summary}{dots(ordered)}'
        f'<div class="c">{"根拠の由来: " if WRITING_PLAN_MODE else ""}本人 {c.get("本人の発言", 0)}・AI {c.get("AIの案", 0)}・口述待ち {c.get("口述が必要", 0)}・公開 {c.get("公開本文", 0)}</div>'
        f'<ol class="outline">{"".join(outline)}</ol></article>'
    )

legend = "".join(f'<span class="m {k}">{label}</span> ' for k, label in MARK.values())
published_numbers = [str(ep["n"]) for ep in eps if status(ep).startswith("公開済み")]
working_numbers = [str(ep["n"]) for ep in eps if not status(ep).startswith("公開済み")]
publication_summary = ("公開済み: 第" + "・".join(published_numbers) + "話。" if published_numbers else "公開済みの回はありません。")
publication_summary += ("制作・壁打ち: 第" + "・".join(working_numbers) + "話。" if working_numbers else "全話公開済みです。")
index_description = series.get(
    "description",
    f"全{len(eps)}話の大見出しと小見出し。見出しを押すと、その話の該当箇所へ進みます。{e(publication_summary)}見出しは本文で最も多い出どころの色。色の点は1つが1段落で、混在する出どころもそのまま示します。",
)
if WRITING_PLAN_MODE and 'description' not in series:
    index_description = (f'全{len(eps)}話の書く内容と根拠。見出しを押すと、その話の該当箇所へ進みます。'
                         f'{publication_summary}色の点は1つが根拠1件で、計画の項目数とは別です。')

index_body = (
    nav(0)
    + f"<h1>{e(index_heading)}</h1>"
    + f'<p class="sub">{e(index_description)}</p>'
    + f'<p>{legend}</p><div class="grid">{"".join(cards)}</div>'
)
(outdir / "index.html").write_text(page(index_title, index_body), encoding="utf-8")
print("pages:", len(eps) + 1, outdir)
