import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import { createNoteInputGuard, readNoteDom } from '../scripts/note_editor_guarded_input.mjs';

// 隔離Tab: 入口のwriteをspyする。実DOM取得関数の試験は下の別fixtureで行う。
const noteUrl = 'https://editor.note.com/notes/nfixture000001/edit/';
const payload = 'https://example.org/';
const text = value => ({ tag: '#text', text: value });
const p = value => ({ tag: 'P', attrs: [], children: value ? [text(value)] : [{ tag: 'BR', attrs: [], children: [] }] });
const card = () => ({ tag: 'FIGURE', attrs: [['data-src', payload]], children: [] });
function snapshot() {
  return {
    url: noteUrl, title: '無害fixture', rootCount: 1, rootAttrs: [['contenteditable', 'true']],
    blocks: [p('保護された本文'), p(''), p('保護された末尾')],
    rawHtml: '<p>保護された本文</p><p><br></p><p>保護された末尾</p>',
    bodyText: '保護された本文保護された末尾', focused: true, visible: true,
    selection: { collapsed: true, rangeCount: 1, blockIndex: 1, anchorOffset: 0, focusOffset: 0, sameNode: true, inside: true, emptyPosition: true },
  };
}
let sequence = 0;
function backend() {
  const tab = {
    id: `fixture-${++sequence}`, current: snapshot(), writes: [], reads: 0,
    async url() { return this.current.url; },
    playwright: { async evaluate() { tab.reads++; if (tab.readFailure) throw Error('秘密本文'); return structuredClone(tab.current); } },
    async paste(...args) { this.writes.push(args); if (this.writeFailure) throw Error('秘密URL'); this.effect?.(); },
    async getAXState() { if (this.axFailure) throw Error('秘密状態'); return ''; },
  };
  return tab;
}
function guard(tab) { return createNoteInputGuard(tab, { tabId: tab.id, noteUrl }); }
async function prepared() { const tab = backend(); const input = guard(tab); const checkpoint = await input.observe(); return { tab, input, checkpoint }; }

test('fresh内部取得から正常単一pasteと全文照合を行う', async () => {
  const { tab, input, checkpoint } = await prepared();
  tab.effect = () => { tab.current.blocks[1] = card(); tab.current.rawHtml += '<figure></figure>'; };
  const result = await input.pasteUrl({ checkpoint, payload });
  assert.equal(result.state, 'completed'); assert.equal(tab.reads, 3);
  assert.deepEqual(tab.writes, [[null, payload, { format: 'text' }]]);
  assert.match(result.before_sha256, /^[a-f0-9]{64}$/);
  assert.notEqual(result.before_sha256, result.after_sha256);
  assert.equal(result.approval_authenticity_verified, false);
  assert(!JSON.stringify(result).includes('保護された本文'));
});
for (const [name, change] of [
  ['画像作業wait後のwrong cursor', s => { s.selection.blockIndex = 0; }],
  ['新規入力後の非empty block', s => { s.blocks[1] = p('新規入力'); }],
  ['別note', s => { s.url = 'https://editor.note.com/notes/nother/edit/'; }],
  ['非collapsed selection', s => { s.selection.collapsed = false; }],
  ['offset drift', s => { s.selection.anchorOffset = 13; }],
  ['wrong neighbor', s => { s.blocks[2] = p('変更された末尾'); }],
  ['保護本文変更', s => { s.blocks[0] = p('変更された本文'); }],
  ['保護領域hash変更', s => { s.rootAttrs.push(['data-owner', 'changed']); }],
  ['曖昧root', s => { s.rootCount = 2; }],
  ['焦点喪失', s => { s.focused = false; }],
  ['不可視root', s => { s.visible = false; }],
  ['selection対象不明', s => { s.selection.inside = false; }],
]) test(`${name}: write未呼出し`, async () => {
  const { tab, input, checkpoint } = await prepared(); change(tab.current);
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
  assert.equal(tab.writes.length, 0);
});
test('別tabと人工receiptでは書けない', async () => {
  const { tab, input, checkpoint } = await prepared(); tab.id += '-other';
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked'); assert.equal(tab.writes.length, 0);
  const other = backend();
  assert.equal((await guard(other).pasteUrl({ checkpoint: { state: 'observed', approved: true }, payload })).state, 'blocked');
  assert.equal(other.writes.length, 0);
});
test('入力後全文増殖を検知して同じtabの別入口も止める', async () => {
  const { tab, input, checkpoint } = await prepared();
  tab.effect = () => { tab.current.blocks.push(...structuredClone(tab.current.blocks)); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
  assert.equal((await guard(tab).observe()).state, 'blocked'); assert.equal(tab.writes.length, 1);
});
test('非同期pendingでは再pasteせずread-only reconcileする', async () => {
  const { tab, input, checkpoint } = await prepared(); tab.effect = () => { tab.current.blocks[1] = p(payload); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'pending');
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'pending');
  assert.equal((await input.reconcile()).state, 'pending'); tab.current.blocks[1] = card();
  assert.equal((await input.reconcile()).state, 'completed'); assert.equal(tab.writes.length, 1);
});
for (const failure of ['readFailure', 'writeFailure', 'axFailure']) test(`${failure}: 例外詳細を漏らさず後続停止`, async () => {
  const { tab, input, checkpoint } = await prepared(); tab[failure] = true;
  const result = await input.pasteUrl({ checkpoint, payload });
  assert.equal(result.state, 'blocked'); assert(!JSON.stringify(result).includes('秘密'));
  await input.pasteUrl({ checkpoint, payload }); assert.equal(tab.writes.length, failure === 'readFailure' ? 0 : 1);
});
test('payloadは改行なしのhttps URLひとつだけ', async () => {
  for (const value of ['本文', 'https://example.org/\n', 'https://a/ https://b/', 'javascript:alert(1)', 'https://user:password@example.org/']) {
    const { tab, input, checkpoint } = await prepared();
    assert.equal((await input.pasteUrl({ checkpoint, payload: value })).state, 'blocked'); assert.equal(tab.writes.length, 0);
  }
});

// readNoteDomそのものを実行する最小DOM。ブラウザ/DOMParserには接続しない。
class Element {
  constructor(tag, attributes = {}, children = []) {
    this.nodeType = 1; this.tagName = tag;
    this.attributes = Object.entries(attributes).map(([name, value]) => ({ name, value }));
    this.childNodes = children.map(n => typeof n === 'string' ? { nodeType: 3, textContent: n } : n);
    for (const n of this.childNodes) n.parentElement = this;
  }
  get textContent() { return this.childNodes.map(n => n.textContent).join(''); }
  get innerHTML() { return this.childNodes.map(n => n.nodeType === 3 ? n.textContent : n.outerHTML).join(''); }
  get outerHTML() { return `<${this.tagName} ${this.attributes.map(a => `${a.name}="${a.value}"`).join(' ')}>${this.innerHTML}</${this.tagName}>`; }
  contains(n) { return n === this || this.childNodes.some(c => c === n || c.contains?.(n)); }
  getClientRects() { return [{}]; }
}
function domBackend() {
  const title = new Element('H2', {}, ['保護された見出し']);
  const blank = new Element('P', {}, [new Element('BR')]);
  const toc = new Element('TABLE-OF-CONTENTS', { toc: '[見出し]', contenteditable: 'false' });
  const iframe = new Element('IFRAME', { src: 'https://example.org/existing', width: '400', height: '200' });
  const existing = new Element('FIGURE', { 'data-src': 'https://example.org/existing' }, [iframe]);
  const root = new Element('DIV', { class: 'ProseMirror', contenteditable: 'true' }, [title, blank, toc, existing]);
  let roots = [root]; let focused = true;
  const selection = { anchorNode: blank, focusNode: blank, anchorOffset: 0, focusOffset: 0, isCollapsed: true, rangeCount: 1 };
  const document = { title: 'DOM fixture', activeElement: root, hasFocus: () => focused, querySelectorAll(selector) {
    assert.equal(selector, '.ProseMirror[contenteditable="true"]'); return roots;
  } };
  const window = { location: { href: noteUrl }, getSelection: () => selection };
  const tab = backend();
  tab.playwright.evaluate = async fn => {
    tab.reads++;
    // 実入口が渡した関数を、新しいscopeで実行。外部closure依存もここで失敗する。
    return runInNewContext(`(${fn.toString()})()`, { document, window });
  };
  tab.effect = () => {
    root.childNodes[1] = new Element('FIGURE', { 'data-src': payload }); root.childNodes[1].parentElement = root;
  };
  return { tab, root, blank, title, toc, iframe, selection, window, document, setRoots: value => { roots = value; }, blur: () => { focused = false; } };
}

test('実DOM読取関数→fresh再取得→paste→全文比較を同じ入口で通す', async () => {
  const { tab, iframe } = domBackend(); const input = guard(tab); const checkpoint = await input.observe();
  assert.equal(checkpoint.state, 'observed');
  iframe.attributes.find(a => a.name === 'height').value = '900';
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
  assert.equal(tab.writes.length, 1); assert.equal(tab.reads, 3);
});
for (const [name, change] of [
  ['隣接TOC内容消失', d => { d.toc.attributes.find(a => a.name === 'toc').value = '[]'; }],
  ['見出しclass変化', d => { d.title.attributes.push({ name: 'class', value: 'hidden' }); }],
  ['既存iframeリンク変更', d => { d.iframe.attributes.find(a => a.name === 'src').value = 'https://example.org/changed'; }],
  ['空段落から本文へcursor drift', d => { d.selection.anchorNode = d.title.childNodes[0]; d.selection.focusNode = d.title.childNodes[0]; }],
  ['本文選択', d => { d.selection.isCollapsed = false; }],
  ['別note DOM URL', d => { d.window.location.href = 'https://editor.note.com/notes/nother/edit/'; }],
  ['root複数', d => { d.setRoots([d.root, d.root]); }],
  ['焦点喪失', d => { d.blur(); }],
]) test(`実DOM読取: ${name}でpaste未呼出し`, async () => {
  const d = domBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  change(d); assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked'); assert.equal(d.tab.writes.length, 0);
});
test('DOM取得はroot不明とselectionなしを安全に返す', () => {
  const document = { querySelectorAll: () => [] };
  assert.equal(runInNewContext(`(${readNoteDom.toString()})()`, { document }).rootCount, 0);
});
test('入力後の保護リンク消失とカード内本文複製も止める', async () => {
  for (const mode of ['protected_loss', 'duplicate_in_card']) {
    const { tab, input, checkpoint } = await prepared();
    // 64文字以上の保護本文で、新checkpointを内部取得する。
    tab.current.blocks[0] = p('保護された本文'.repeat(20));
    const fresh = await input.observe();
    tab.effect = () => {
      tab.current.blocks[1] = card();
      if (mode === 'protected_loss') tab.current.blocks[2] = p('');
      else tab.current.blocks[1].children = [text('保護された本文'.repeat(20))];
    };
    assert.equal((await input.pasteUrl({ checkpoint: fresh, payload })).state, 'blocked');
    assert.equal(tab.writes.length, 1);
  }
});
test('同時呼出しでもmutationはひとつ', async () => {
  const { tab, input, checkpoint } = await prepared();
  tab.effect = () => { tab.current.blocks[1] = card(); };
  const results = await Promise.all([input.pasteUrl({ checkpoint, payload }), input.pasteUrl({ checkpoint, payload })]);
  assert.equal(tab.writes.length, 1); assert(results.some(r => r.state === 'completed')); assert(results.some(r => r.state === 'busy'));
});
test('短い本文の結合複製と既存リンクのカード内複製はblocked', async () => {
  for (const mode of ['short_text', 'old_link', 'nested_figure']) {
    const { tab, input } = await prepared();
    if (mode === 'old_link') tab.current.blocks[0] = { tag: 'P', attrs: [], children: [{ tag: 'A', attrs: [['href', 'https://example.org/protected']], children: [text('既存リンク')] }] };
    const checkpoint = await input.observe();
    tab.effect = () => {
      tab.current.blocks[1] = card();
      if (mode === 'short_text') tab.current.blocks[1].children = [text('保護された本文保護された末尾')];
      if (mode === 'old_link') tab.current.blocks[1].children = [{ tag: 'A', attrs: [['href', 'https://example.org/protected']], children: [text('複製')] }];
      if (mode === 'nested_figure') tab.current.blocks[1].children = [card()];
    };
    assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked'); assert.equal(tab.writes.length, 1);
  }
});
test('Aのpendingを別note Bのfactoryで解消できない', async () => {
  const { tab, input, checkpoint } = await prepared();
  tab.effect = () => { tab.current.blocks[1] = p(payload); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'pending');
  tab.current.url = 'https://editor.note.com/notes/nother/edit/'; tab.current.blocks[1] = card();
  const other = createNoteInputGuard(tab, { tabId: tab.id, noteUrl: tab.current.url });
  assert.equal((await other.reconcile()).state, 'blocked');
  assert.equal((await other.observe()).state, 'blocked');
  assert.equal((await input.reconcile()).state, 'blocked'); assert.equal(tab.writes.length, 1);
});
