import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';
import { createNoteInputGuard, readNoteDom, selectionWithinBlock } from '../scripts/note_editor_guarded_input.mjs';

// 隔離Tab: 入口のwriteをspyする。実DOM取得関数の試験は下の別fixtureで行う。
const noteUrl = 'https://editor.note.com/notes/nfixture000001/edit/';
const payload = 'https://example.org/';
const text = value => ({ tag: '#text', text: value });
const p = value => ({ tag: 'P', attrs: [], children: value ? [text(value)] : [{ tag: 'BR', attrs: [], children: [] }] });
const card = () => ({ tag: 'FIGURE', attrs: [['data-src', payload]], children: [] });
const nativeCard = () => ({ tag: 'FIGURE', attrs: [['data-src', payload], ['id', 'new-native-card']], children: [] });

function dialogBackend() {
  const tab = backend();
  const caption = '作品を紹介します';
  const link = { tag: 'A', attrs: [['href', payload]], children: [text('本文中の同じリンク')] };
  tab.current.blocks = [p('導入'), { tag: 'P', attrs: [], children: [link] }, p(caption), p(payload),
    { tag: 'TABLE-OF-CONTENTS', attrs: [['contenteditable', 'false']], children: [] },
    { tag: 'FIGURE', attrs: [['data-src', 'https://example.org/old']], children: [{ tag: 'IMG', attrs: [['src', 'old.png']], children: [] }] }, p('末尾')];
  const value = n => n.tag === '#text' ? n.text : n.children.map(value).join('');
  function sync() { tab.current.bodyText = tab.current.blocks.map(value).join(''); tab.current.rawHtml = JSON.stringify(tab.current.blocks); }
  sync();
  function select(index, selected = false) {
    let last = tab.current.blocks[index]; const path = [];
    while (last.children?.length) { path.push(last.children.length - 1); last = last.children.at(-1); }
    const length = last.tag === '#text' ? last.text.length : 0;
    const start = { blockIndex: index, nodePath: [0], offset: selected ? 0 : length };
    const end = { blockIndex: index, nodePath: path, offset: length };
    if (!selected) start.nodePath = [...path];
    tab.current.selection = { intersectionsKnown: true, ranges: [{ start, end, protectedIntersections: [] }],
      collapsed: !selected, rangeCount: 1, blockIndex: index, inside: true, text: selected ? payload : '' };
  }
  tab.ax = {
    async get() { return `Browser tab: ${tab.axTarget ?? tab.id}, Title: ${JSON.stringify(tab.current.title)}, URL: ${JSON.stringify(tab.current.url)}.\n  430 text entry area (settable) ${tab.current.bodyText}\n` +
      (tab.current.embedInput ? (tab.applyButtons ?? '  850 button 適用, ID: :r17:\n') : '') +
      (tab.rawAxLeaves ?? '') +
      `The focused UI element is 430 text entry area (settable) ${tab.current.bodyText}`; },
    async selectText(id, target, options) {
      assert.equal(id, options.selectionType === 'text' ? tab.expectedRawTarget ?? 430 : 430);
      (tab.selectedAxTargets ??= []).push(id); tab.writes.push(['select', target]); tab.current.focused = true;
      select(tab.wrongCursor ? 0 : options.selectionType === 'cursor_after' ? 2 : tab.wrongRaw ? 1 : 4, options.selectionType === 'text');
    },
    async pressKey(point, key) {
      assert.equal(key, 'Backspace'); tab.writes.push(['Backspace']); tab.current.blocks[4] = p(''); sync();
    },
    async click(id) {
      assert.equal(id, tab.expectedApplyId ?? 850); tab.clickedApplyId = id;
      tab.writes.push(['適用']); tab.current.blocks[3] = nativeCard(); sync();
    },
  };
  tab.playwright.getByRole = (role, { name }) => ({ async click() {
    tab.writes.push([name]);
    if (name === '埋め込み') {
      tab.current.blocks.splice(3, 0, p('')); sync();
      tab.current.embedInput = { count: 1, active: true, visible: true, value: '' };
      tab.current.focused = false;
      tab.current.selection = { inside: false, collapsed: true, rangeCount: 1, blockIndex: -1,
        intersectionsKnown: true, ranges: [{ start: null, end: null, protectedIntersections: [] }] };
    }
    if (name === '適用') throw Error('Playwright Apply must never be used');
  } });
  tab.playwright.getByPlaceholder = () => ({ async waitFor(options) { assert.equal(options.state, 'visible'); tab.dialogWaited = true; }, async fill(url) {
    assert.equal(url, payload); assert.equal(tab.dialogWaited, true); tab.writes.push(['fill']); tab.current.embedInput.value = url;
  } });
  tab.playwright.locator = () => ({ async waitFor() { if (tab.timeout) throw Error('timeout'); } });
  return { tab, caption, sync };
}
test('native dialog: caption/raw URLの間へカードを作り同一inline linkと既存画像・TOCを保持', async () => {
  const { tab, caption } = dialogBackend();
  const original = structuredClone(tab.current.blocks);
  const result = await guard(tab).embedViaNativeDialog({ payload, caption });
  assert.equal(result.state, 'completed'); assert.equal(result.reason, 'native_embed_verified');
  assert.deepEqual(tab.current.blocks.slice(0, 3), original.slice(0, 3));
  assert.deepEqual(tab.current.blocks.slice(5), original.slice(4));
  assert.deepEqual(tab.current.blocks[3], nativeCard()); assert.deepEqual(tab.current.blocks[4], p(''));
  assert.equal(tab.writes.filter(w => w[0] === '適用').length, 1);
});
test('native dialog: captionの複数人物・作品inlineリンクをすべて保持する', async () => {
  const { tab, caption, sync } = dialogBackend();
  tab.current.blocks[2].children = [
    { tag: 'A', attrs: [['href', 'https://example.org/person']], children: [text(caption.slice(0, 3))] },
    { tag: 'A', attrs: [['href', 'https://example.org/work']], children: [text(caption.slice(3))] },
  ]; sync();
  const original = structuredClone(tab.current.blocks[2]);
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.deepEqual(tab.current.blocks[2], original);
});
for (const buttons of ['', '  850 button 不適用\n', '  850 button 適用 (disabled)\n', '  850 button 適用\n  851 button 適用\n']) test(`native dialog: exact一意Apply以外はAXclickしない ${JSON.stringify(buttons)}`, async () => {
  const { tab, caption } = dialogBackend(); tab.applyButtons = buttons;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_apply_unverified');
  assert.equal(tab.clickedApplyId, undefined); assert(!tab.writes.some(w => w[0] === '適用'));
});
test('native dialog: AXclick非対応は操作前に拒否', async () => {
  const { tab, caption } = dialogBackend(); delete tab.ax.click;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert.equal(tab.writes.length, 0);
});
test('native dialog: Apply AXの別tab headerを拒否', async () => {
  const { tab, caption } = dialogBackend(); const original = tab.playwright.getByPlaceholder;
  tab.playwright.getByPlaceholder = (...args) => ({ async waitFor(opts) { return original(...args).waitFor(opts); }, async fill(url) {
    await original(...args).fill(url); tab.axTarget = 'different-tab';
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_apply_unverified');
  assert.equal(tab.clickedApplyId, undefined);
});
test('native dialog: Applyは固定idでなくfresh AX stateのidを使う', async () => {
  const { tab, caption } = dialogBackend(); tab.applyButtons = '  951 button 適用\n'; tab.expectedApplyId = 951;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.equal(tab.clickedApplyId, 951);
});
test('native dialog: caption cursor違いはmenu操作前に停止', async () => {
  const { tab, caption } = dialogBackend(); tab.wrongCursor = true;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_wrong_caption_cursor');
  assert.deepEqual(tab.writes, [['select', caption]]);
});
test('native dialog: raw URLでなくinline linkを選んだらBackspaceしない', async () => {
  const { tab, caption } = dialogBackend(); tab.wrongRaw = true;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_wrong_raw_selection');
  assert(!tab.writes.some(w => w[0] === 'Backspace'));
});
test('native dialog: 既存カード重複とcaption曖昧はwrite前に停止', async () => {
  for (const duplicate of ['card', 'caption', 'raw']) {
    const { tab, caption, sync } = dialogBackend(); tab.current.blocks.push(duplicate === 'card' ? card() : p(duplicate === 'caption' ? caption : payload)); sync();
    assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
    assert.equal(tab.writes.length, 0);
  }
});
test('native dialog: timeoutは共有channelを止め再操作せずread-onlyで完成形だけ受理', async () => {
  const { tab, caption, sync } = dialogBackend(); tab.timeout = true;
  const input = guard(tab);
  assert.equal((await input.embedViaNativeDialog({ payload, caption })).state, 'pending');
  const writes = tab.writes.length;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'pending');
  assert.equal((await input.reconcile()).state, 'pending'); assert.equal(tab.writes.length, writes);
  tab.current.blocks[4] = p(''); sync();
  assert.equal((await input.reconcile()).state, 'completed'); assert.equal(tab.writes.length, writes);
});
async function pendingNativeCard() {
  const fixture = dialogBackend(), input = guard(fixture.tab);
  fixture.tab.timeout = true;
  assert.equal((await input.embedViaNativeDialog({ payload, caption: fixture.caption })).state, 'pending');
  return { ...fixture, input };
}
test('verified cleanup: pendingの正しいcard+rawだけを削除し再Applyしない', async () => {
  const { tab, input } = await pendingNativeCard(), original = structuredClone(tab.current.blocks);
  const applies = tab.writes.filter(w => w[0] === '適用').length;
  assert.equal((await input.completeNativeEmbed()).state, 'completed');
  assert.equal(tab.writes.filter(w => w[0] === '適用').length, applies);
  assert.deepEqual(tab.current.blocks.slice(0, 4), original.slice(0, 4));
  assert.deepEqual(tab.current.blocks.slice(5), original.slice(5));
  const writes = tab.writes.length;
  assert.equal((await input.completeNativeEmbed()).reason, 'no_pending_native_embed');
  assert.equal(tab.writes.length, writes);
});
test('verified cleanup: stagingだけなら一切操作せずpending', async () => {
  const { tab, input, sync } = await pendingNativeCard(); tab.current.blocks[3] = p(''); sync();
  const writes = tab.writes.length;
  assert.equal((await input.completeNativeEmbed()).state, 'pending');
  assert.equal(tab.writes.length, writes);
});
test('verified cleanup: protected本文変更をwrite前に拒否', async () => {
  const { tab, input, sync } = await pendingNativeCard(); tab.current.blocks[0] = p('改変'); sync();
  const writes = tab.writes.length;
  assert.equal((await input.completeNativeEmbed()).state, 'blocked'); assert.equal(tab.writes.length, writes);
});
test('verified cleanup: inline誤選択をBackspace前に拒否', async () => {
  const { tab, input } = await pendingNativeCard(); tab.wrongRaw = true;
  assert.equal((await input.completeNativeEmbed()).reason, 'native_embed_wrong_raw_selection');
  assert(!tab.writes.some(w => w[0] === 'Backspace'));
});
test('verified cleanup: failedreadはpendingのまま無操作、安定後に明示cleanup可能', async () => {
  const { tab, input } = await pendingNativeCard(), writes = tab.writes.length;
  tab.readFailure = true;
  assert.equal((await input.completeNativeEmbed()).state, 'pending'); assert.equal(tab.writes.length, writes);
  tab.readFailure = false;
  assert.equal((await input.completeNativeEmbed()).state, 'completed');
});
test('verified cleanup: 結果不明のBackspaceを二度送らない', async () => {
  const { tab, input } = await pendingNativeCard();
  tab.ax.pressKey = async () => { tab.writes.push(['Backspace']); throw Error('timeout'); };
  assert.equal((await input.completeNativeEmbed()).state, 'pending');
  const writes = tab.writes.length;
  assert.equal((await input.completeNativeEmbed()).state, 'pending'); assert.equal(tab.writes.length, writes);
  assert.equal(tab.writes.filter(w => w[0] === 'Backspace').length, 1);
});
test('verified cleanup: 通常routeの無反応Backspaceも明示cleanupで再送しない', async () => {
  const { tab, caption } = dialogBackend(), input = guard(tab);
  tab.ax.pressKey = async () => { tab.writes.push(['Backspace']); };
  assert.equal((await input.embedViaNativeDialog({ payload, caption })).state, 'pending');
  const writes = tab.writes.length;
  assert.equal((await input.completeNativeEmbed()).state, 'pending'); assert.equal(tab.writes.length, writes);
});
for (const route of ['normal', 'complete']) test(`newcard settle: ${route}で新規カードだけのmetadata/preview変化を許す`, async () => {
  const fixture = route === 'complete' ? await pendingNativeCard() : dialogBackend();
  const { tab, caption, sync } = fixture, input = fixture.input ?? guard(tab), select = tab.ax.selectText;
  const protectedOld = structuredClone(tab.current.blocks.slice(route === 'complete' ? 5 : 4));
  tab.ax.selectText = async (...args) => {
    await select(...args);
    if (args[2].selectionType === 'text') {
      tab.current.blocks[3].attrs.push(['data-identifier', 'settled']);
      tab.current.blocks[3].children = [{ tag: 'DIV', attrs: [], children: [text('provider preview')] }]; sync();
    }
  };
  const result = route === 'complete' ? await input.completeNativeEmbed() : await input.embedViaNativeDialog({ payload, caption });
  assert.equal(result.state, 'completed'); assert.deepEqual(tab.current.blocks.slice(5), protectedOld);
  assert.equal(tab.current.blocks[3].attrs.find(a => a[0] === 'id')[1], 'new-native-card');
});
for (const route of ['normal', 'complete']) test(`raw AX leaf: ${route}は一意のexact static textを選びcaptionはrootのまま`, async () => {
  const fixture = route === 'complete' ? await pendingNativeCard() : dialogBackend();
  const { tab, caption } = fixture, input = fixture.input ?? guard(tab);
  tab.rawAxLeaves = `  299 text ${payload}\n  300 text prefix ${payload}\n`;
  tab.expectedRawTarget = 299;
  assert.equal((route === 'complete' ? await input.completeNativeEmbed() : await input.embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.deepEqual(tab.selectedAxTargets, [430, 299]);
});
test('raw AX leaf: 複数exact leafは推測せずroot fallback後のRangeで拒否', async () => {
  const { tab, caption } = dialogBackend(); tab.rawAxLeaves = `  299 text ${payload}\n  301 text ${payload}\n`; tab.wrongRaw = true;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_wrong_raw_selection');
  assert.deepEqual(tab.selectedAxTargets, [430, 430]); assert(!tab.writes.some(w => w[0] === 'Backspace'));
});
test('raw AX leaf: exact文字でも違うPを選べばBackspaceしない', async () => {
  const { tab, caption } = dialogBackend(); tab.rawAxLeaves = `  299 text ${payload}\n`; tab.expectedRawTarget = 299; tab.wrongRaw = true;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).reason, 'native_embed_wrong_raw_selection');
  assert.deepEqual(tab.selectedAxTargets, [430, 299]); assert(!tab.writes.some(w => w[0] === 'Backspace'));
});
test('raw AX leaf: leafに近似URLしかなければ既存root pathを使う', async () => {
  const { tab, caption } = dialogBackend(); tab.rawAxLeaves = `  299 text prefix ${payload}\n`;
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.deepEqual(tab.selectedAxTargets, [430, 430]);
});
for (const route of ['normal', 'complete']) for (const [name, mutate] of [
  ['URL', tab => { tab.current.blocks[3].attrs.find(a => a[0] === 'data-src')[1] = 'https://other.example/'; }],
  ['id', tab => { tab.current.blocks[3].attrs.find(a => a[0] === 'id')[1] = 'other-card'; }],
  ['position', tab => { [tab.current.blocks[2], tab.current.blocks[3]] = [tab.current.blocks[3], tab.current.blocks[2]]; }],
  ['oldcard metadata', tab => { tab.current.blocks[6].attrs.push(['data-identifier', 'changed']); }],
  ['author text', tab => { tab.current.blocks[0] = p('改変'); }],
]) test(`newcard settle: ${route}の${name}変更をcleanup前に拒否`, async () => {
  const fixture = route === 'complete' ? await pendingNativeCard() : dialogBackend();
  const { tab, caption, sync } = fixture, input = fixture.input ?? guard(tab), select = tab.ax.selectText;
  tab.ax.selectText = async (...args) => {
    await select(...args); if (args[2].selectionType === 'text') { mutate(tab); sync(); }
  };
  const result = route === 'complete' ? await input.completeNativeEmbed() : await input.embedViaNativeDialog({ payload, caption });
  assert.equal(result.state, 'blocked'); assert(!tab.writes.some(w => w[0] === 'Backspace'));
});
test('newcard settle: cleanup後のカードid変更も完了にしない', async () => {
  const { tab, caption, sync } = dialogBackend(), press = tab.ax.pressKey;
  tab.ax.pressKey = async (...args) => { await press(...args); tab.current.blocks[3].attrs.find(a => a[0] === 'id')[1] = 'replaced'; sync(); };
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
});
test('native staging診断は不一致pathと照合flagだけを返し本文値を含めない', async () => {
  const { tab, caption, sync } = dialogBackend(), role = tab.playwright.getByRole;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await role(...args).click();
    if (args[1].name === '埋め込み') { tab.current.blocks[0] = p('秘密の本文値'); sync(); }
  } });
  const result = await guard(tab).embedViaNativeDialog({ payload, caption });
  assert.equal(result.diagnostic.checks.prefix, false);
  assert.equal(result.diagnostic.checks.suffix, true);
  assert.match(result.diagnostic.mismatch_path, /^\$\.blocks\.0\./);
  assert(!JSON.stringify(result).includes('秘密の本文値'));
});
test('native dialog: menu後targetが変われば次のwriteを拒否', async () => {
  const { tab, caption } = dialogBackend();
  const original = tab.playwright.getByRole;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await original(...args).click();
    if (args[1].name === 'メニューを開く') tab.current.url = 'https://editor.note.com/notes/nother/edit/';
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert.deepEqual(tab.writes, [['select', caption], ['メニューを開く']]);
});
for (const driftAfter of ['メニューを開く', '埋め込み', 'fill']) test(`native dialog: ${driftAfter}後の本文不変Range driftをApply前に拒否`, async () => {
  const { tab, caption } = dialogBackend();
  const drift = () => {
    const q = tab.current.selection;
    q.ranges[0].start = { blockIndex: 0, nodePath: [0], offset: 1 };
    q.ranges[0].end = { blockIndex: 0, nodePath: [0], offset: 1 }; q.blockIndex = 0; q.inside = true;
  };
  const role = tab.playwright.getByRole, placeholder = tab.playwright.getByPlaceholder;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await role(...args).click(); if (args[1].name === driftAfter) drift();
  } });
  tab.playwright.getByPlaceholder = (...args) => ({ async waitFor(opts) { return placeholder(...args).waitFor(opts); }, async fill(url) {
    await placeholder(...args).fill(url); if (driftAfter === 'fill') drift();
  } });
  const result = await guard(tab).embedViaNativeDialog({ payload, caption });
  assert.equal(result.state, 'blocked');
  assert.equal(result.diagnostic.code, 'native_embed_caption_range_changed');
  assert(!tab.writes.some(w => w[0] === '適用'));
});
test('native dialog: dialogへのfocus移動は保存されたcaption Rangeと区別する', async () => {
  const { tab, caption } = dialogBackend();
  const role = tab.playwright.getByRole, select = tab.ax.selectText;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await role(...args).click(); if (args[1].name !== '適用') tab.current.focused = false;
  } });
  tab.ax.selectText = async (...args) => { await select(...args); tab.current.focused = true; };
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
});
test('native dialog: dialog中にRange取得不能ならApply前に停止', async () => {
  const { tab, caption } = dialogBackend(); const original = tab.playwright.getByRole;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await original(...args).click();
    if (args[1].name === '埋め込み') tab.current.selection.ranges = [];
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert(!tab.writes.some(w => w[0] === '適用'));
});
for (const [name, change] of [
  ['staging以外の本文変更', tab => { tab.current.blocks[0] = p('書き換え'); }],
  ['余分な空P', tab => { tab.current.blocks.splice(3, 0, p('')); }],
  ['stagingに内容混入', tab => { tab.current.blocks[3] = p('余分な内容'); }],
  ['URL欄複数', tab => { tab.current.embedInput.count = 2; }],
  ['URL欄非active', tab => { tab.current.embedInput.active = false; }],
  ['URL欄不可視', tab => { tab.current.embedInput.visible = false; }],
  ['空でないURL欄', tab => { tab.current.embedInput.value = 'https://other.example/'; }],
]) test(`native dialog: ${name}をfill/Apply前に拒否`, async () => {
  const { tab, caption, sync } = dialogBackend(); const original = tab.playwright.getByRole;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await original(...args).click(); if (args[1].name === '埋め込み') { change(tab); sync(); }
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert(!tab.writes.some(w => ['fill', '適用'].includes(w[0])));
});
test('native dialog: fillしたURLの値が違えばApplyしない', async () => {
  const { tab, caption } = dialogBackend(); const original = tab.playwright.getByPlaceholder;
  tab.playwright.getByPlaceholder = (...args) => ({ async waitFor(opts) { return original(...args).waitFor(opts); }, async fill(url) {
    await original(...args).fill(url); tab.current.embedInput.value = 'https://other.example/';
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert(!tab.writes.some(w => w[0] === '適用'));
});
for (const index of [2, 3]) test(`native dialog: retained root bookmark index ${index}だけ許容`, async () => {
  const { tab, caption } = dialogBackend(); const original = tab.playwright.getByRole;
  tab.playwright.getByRole = (...args) => ({ async click() {
    await original(...args).click();
    if (args[1].name === '埋め込み') {
      const point = { blockIndex: index, nodePath: index === 2 ? [0] : [], offset: index === 2 ? caption.length : 0 };
      tab.current.selection = { rangeCount: 1, intersectionsKnown: true, collapsed: true, inside: true,
        blockIndex: index, ranges: [{ start: point, end: { ...point }, protectedIntersections: [] }] };
    }
  } });
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
});
test('native dialog: arbitrary callbackと不正URLは操作前に拒否', async () => {
  for (const extra of [{ callback() {} }, { payload: 'https://u:p@example.org/' }, { payload: 'https://example.org:8443/' }, { payload: 'https://example.org/\n' }]) {
    const { tab, caption } = dialogBackend();
    assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption, ...extra })).state, 'blocked');
    assert.equal(tab.writes.length, 0);
  }
});
function snapshot() {
  return {
    url: noteUrl, title: '無害fixture', rootCount: 1, rootAttrs: [['contenteditable', 'true']],
    blocks: [p('保護された本文'), p(''), p('保護された末尾')],
    rawHtml: '<p>保護された本文</p><p><br></p><p>保護された末尾</p>',
    bodyText: '保護された本文保護された末尾', focused: true, visible: true,
    selection: { intersectionsKnown: true, ranges: [{start:{blockIndex:1,nodePath:[],offset:0},end:{blockIndex:1,nodePath:[],offset:0},protectedIntersections:[]}], collapsed: true, rangeCount: 1, blockIndex: 1, anchorOffset: 0, focusOffset: 0, sameNode: true, inside: true, emptyPosition: true },
  };
}
function loadingBlock() {
  return {tag:'P', attrs:[], children:[
    {tag:'DIV', attrs:[['class','placeholder ProseMirror-widget'],['contenteditable','false']], children:Array.from({length:3},()=>({tag:'DIV',attrs:[],children:[]}))},
    {tag:'IMG', attrs:[['alt',''],['class','ProseMirror-separator']], children:[]},
    {tag:'BR', attrs:[['class','ProseMirror-trailingBreak']], children:[]},
  ]};
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
test('実測の読込みwidgetは再入力せずpendingからURL一致カードへ照合する', async () => {
  const {tab,input,checkpoint}=await prepared();
  tab.effect=()=>{tab.current.blocks[1]=loadingBlock();tab.current.blocks.splice(2,0,p(''));};
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  tab.current.blocks[1]=card();
  assert.equal((await input.reconcile()).state,'completed');
  assert.equal(tab.writes.length,1);
});
test('読込みwidgetに本文が混入したら停止する', async () => {
  const {tab,input,checkpoint}=await prepared();
  tab.effect=()=>{const b=loadingBlock();b.children[0].children[0].children.push(text('意図しない本文'));tab.current.blocks[1]=b;};
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'blocked');
});
for (const failure of ['readFailure', 'writeFailure', 'axFailure']) test(`${failure}: 例外詳細を漏らさず後続停止`, async () => {
  const { tab, input, checkpoint } = await prepared(); tab[failure] = true;
  const result = await input.pasteUrl({ checkpoint, payload });
  assert.equal(result.state, failure === 'readFailure' ? 'blocked' : 'pending'); assert(!JSON.stringify(result).includes('秘密'));
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
  selection.getRangeAt = () => ({startContainer:selection.anchorNode,startOffset:selection.anchorOffset,
    endContainer:selection.focusNode,endOffset:selection.focusOffset,intersectsNode:node=>node.contains(selection.anchorNode)});
  const document = { title: 'DOM fixture' , activeElement: root, hasFocus: () => focused, querySelectorAll(selector) {
    assert.equal(selector, '.ProseMirror[contenteditable="true"]'); return roots;
  } };
  const window = { location: { href: noteUrl }, getSelection: () => selection };
  const tab = backend();
  tab.playwright.evaluate = async fn => {
    tab.reads++;
    // 実入口が渡した関数を、新しいscopeで実行。外部closure依存もここで失敗する。
    return runInNewContext(`(${fn.toString()})()`, { document, window, URL });
  };
  tab.effect = () => {
    root.childNodes[1] = new Element('FIGURE', { 'data-src': payload }); root.childNodes[1].parentElement = root;
  };
  return { tab, root, blank, title, toc, iframe, selection, window, document, setRoots: value => { roots = value; }, blur: () => { focused = false; } };
}

const tweetSource = 'https://x.com/creator/status/12345';
function twitterFixture(fallback = false, widget = 'twitter-widget-14') {
  const frame = new Element('IFRAME', { id: widget, ...(fallback
    ? { style: 'position: absolute; visibility: hidden; width: 0px; height: 0px;' }
    : { src: `https://platform.twitter.com/embed/Tweet.html?id=12345&embedId=${widget}&features=runtime`, 'data-tweet-id': '12345' }) });
  const renderer = new Element('DIV', { class: 'twitter-tweet twitter-tweet-rendered' }, [frame]);
  const quote = new Element('BLOCKQUOTE', { align: 'center', class: 'twitter-tweet', 'data-dnt': 'true', 'data-twitter-extracted-i123456': 'true' }, [
    new Element('P', { dir: 'ltr', lang: 'en' }, ['provider tweet']), '— Creator ',
    new Element('A', { href: `${tweetSource}?ref_src=twsrc%5Etfw`, tabindex: '-1' }, ['date']),
  ]);
  const script = new Element('SCRIPT', { async: '', charset: 'utf-8', src: 'https://platform.x.com/widgets.js' });
  const span = new Element('SPAN', {}, [renderer, ...(fallback ? [quote] : []), '\n', script, '\n\n']);
  const figure = new Element('FIGURE', { contenteditable: 'false', 'embedded-service': 'twitter',
    'data-src': tweetSource, id: 'protected-figure', name: 'protected-figure' }, [span]);
  return { figure, frame, renderer, quote, span, script };
}
function mountTwitter(d, fixture) { d.root.childNodes[3] = fixture.figure; fixture.figure.parentElement = d.root; }
test('実DOM Twitter: 検証済みfallback→同一post iframeの描画遷移を本文変更にしない', async () => {
  const d = domBackend(); mountTwitter(d, twitterFixture(true));
  const before = await d.tab.playwright.evaluate(readNoteDom);
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); mountTwitter(d, twitterFixture()); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
  const after = await d.tab.playwright.evaluate(readNoteDom);
  assert.deepEqual(JSON.parse(before.blocksJson)[3], JSON.parse(after.blocksJson)[3]);
  assert.notEqual(before.rawHtml, after.rawHtml); assert(before.rawHtml.includes('BLOCKQUOTE'));
});
test('実DOM Twitter: 同一sourceのvolatilewidget ID変更もidentityを保つ', async () => {
  const d = domBackend(); mountTwitter(d, twitterFixture());
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); mountTwitter(d, twitterFixture(false, 'twitter-widget-999')); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
});
for (const [name, change] of [
  ['wrong host', f => { f.frame.attributes.find(a => a.name === 'src').value = 'https://evil.example/embed/Tweet.html?id=12345'; }],
  ['wrong iframe id', f => { f.frame.attributes.find(a => a.name === 'src').value = 'https://platform.twitter.com/embed/Tweet.html?id=999'; }],
  ['wrong data-tweet-id', f => { f.frame.attributes.find(a => a.name === 'data-tweet-id').value = '999'; }],
  ['wrong figure URL', f => { f.figure.attributes.find(a => a.name === 'data-src').value = 'https://x.com/creator/status/999'; }],
  ['editable figure', f => { f.figure.attributes.find(a => a.name === 'contenteditable').value = 'true'; }],
  ['unknown renderer', f => { f.renderer.tagName = 'SECTION'; }],
  ['author image inside wrapper', f => { f.span.childNodes.push(new Element('IMG', { src: 'author.png' })); }],
  ['untrusted script', f => { f.script.attributes.find(a => a.name === 'src').value = 'https://evil.example/widgets.js'; }],
  ['protected outer id', f => { f.figure.attributes.find(a => a.name === 'id').value = 'different'; }],
]) test(`実DOM Twitter: ${name}はprojectionで隠さず拒否`, async () => {
  const d = domBackend(); mountTwitter(d, twitterFixture(true));
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); const f = twitterFixture(); change(f); mountTwitter(d, f); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});
for (const [name, change] of [
  ['fallback anchor別post', f => { f.quote.childNodes.at(-1).attributes.find(a => a.name === 'href').value = 'https://x.com/creator/status/999'; }],
  ['fallback中wrongframehost', f => { f.frame.attributes.push({ name: 'src', value: 'https://evil.example/embed/Tweet.html?id=12345' }); }],
  ['fallbackに画像混入', f => { f.quote.childNodes.push(new Element('IMG', { src: 'author.png' })); }],
  ['fallback消失かつsrcなし', f => { f.span.childNodes.splice(1, 1); }],
]) test(`実DOM Twitter: ${name}は同一tweet投影として扱わない`, async () => {
  const d = domBackend(); mountTwitter(d, twitterFixture(true));
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); const f = twitterFixture(true); change(f); mountTwitter(d, f); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});
for (const lost of ['image', 'TOC', 'link']) test(`実DOM Twitter: 正常描画遷移でも著者の${lost}欠落は拒否`, async () => {
  const d = domBackend(); mountTwitter(d, twitterFixture(true));
  const extra = new Element('P', {}, [new Element(lost === 'image' ? 'IMG' : 'A', lost === 'image' ? { src: 'author.png' } : { href: 'https://author.example/' }, lost === 'image' ? [] : ['著者リンク'])]);
  d.root.childNodes.push(extra); extra.parentElement = d.root;
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); mountTwitter(d, twitterFixture()); if (lost === 'TOC') d.root.childNodes.splice(2, 1); else d.root.childNodes.pop(); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});

test('実DOM読取: native URL textareaの一意・focus・可視・入力値を観測する', async () => {
  const d = domBackend(), input = new Element('TEXTAREA', { placeholder: 'https://example.com' });
  input.value = payload;
  const query = d.document.querySelectorAll;
  d.document.querySelectorAll = selector => selector === 'textarea[placeholder="https://example.com"]' ? [input] : query(selector);
  d.document.activeElement = input;
  const observed = await d.tab.playwright.evaluate(readNoteDom);
  assert.deepEqual(JSON.parse(JSON.stringify(observed.embedInput)), { count: 1, active: true, visible: true, value: payload });
  assert.equal(observed.focused, false);
});
function tocRecords() {
  return [1, 2].map((n) => ({ node: { type: 'heading', attrs: { level: 2, align: '', id: `heading-${n}` },
    content: [{ type: 'text', text: `見出し${n}` }] }, pos: n * 100, text: `見出し${n}`, level: 2 }));
}
test('実DOM読取: invalidJSON/未知TOC shapeを正規化せず保持する', async () => {
  for (const raw of ['[見出し]', JSON.stringify([{ ...tocRecords()[0], extra: true }])]) {
    const d = domBackend(); d.toc.attributes.find(a => a.name === 'toc').value = raw;
    const observed = await d.tab.playwright.evaluate(readNoteDom);
    const blocks = JSON.parse(observed.blocksJson);
    assert.equal(blocks[2].attrs.find(a => a[0] === 'toc')[1], raw);
  }
});
test('実DOM読取: 正規TOCの数値posだけの変化を許し他の全fieldは保持', async () => {
  const d = domBackend(); const toc = d.toc.attributes.find(a => a.name === 'toc');
  toc.value = JSON.stringify(tocRecords());
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); const records = tocRecords(); records.forEach(r => { r.pos += 77; }); toc.value = JSON.stringify(records); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
});
for (const [name, change] of [
  ['title', records => { records[0].text = '変更'; records[0].node.content[0].text = '変更'; }],
  ['id', records => { records[0].node.attrs.id = '別id'; }],
  ['order', records => { records.reverse(); }],
  ['未知shape', records => { records[0].unknown = true; }],
  ['非数値pos', records => { records[0].pos = '100'; }],
]) test(`実DOM読取: TOC ${name}変更は既存保護差分として拒否`, async () => {
  const d = domBackend(), toc = d.toc.attributes.find(a => a.name === 'toc');
  toc.value = JSON.stringify(tocRecords());
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); const records = tocRecords(); change(records); toc.value = JSON.stringify(records); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});

test('実DOM読取関数→fresh再取得→paste→全文比較を同じ入口で通す', async () => {
  const { tab, iframe } = domBackend(); const input = guard(tab); const checkpoint = await input.observe();
  assert.equal(checkpoint.state, 'observed');
  iframe.attributes.find(a => a.name === 'height').value = '900';
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
  assert.equal(tab.writes.length, 1); assert.equal(tab.reads, 3);
});
test('入力後のfocus表示と直下Pのparagraphマーカーだけは本文変更にしない', async () => {
  const d = domBackend();
  const paragraph = new Element('P', { class: 'paragraph' }, ['保持する本文']);
  paragraph.parentElement = d.root; d.root.childNodes.push(paragraph);
  d.root.attributes.find(a => a.name === 'class').value = 'ProseMirror ProseMirror-focused';
  const input = guard(d.tab); const checkpoint = await input.observe();
  const effect = d.tab.effect;
  d.tab.effect = () => {
    effect();
    d.root.attributes.find(a => a.name === 'class').value = 'ProseMirror ProseMirror-focused ProseMirror-hideselection';
    paragraph.attributes = [];
  };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
});
test('直下ULのbulletList表示class消失だけでは入力結果を破損扱いしない', async () => {
  const d = domBackend();
  const list = new Element('UL', { class: 'bulletList', id: 'protected-list' }, [
    new Element('LI', {}, [new Element('P', {}, ['保持する要点'])]),
  ]);
  list.parentElement = d.root; d.root.childNodes.push(list);
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); list.attributes = list.attributes.filter(a => a.name !== 'class'); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
  assert.equal(d.tab.writes.length, 1);
});
for (const [name, change, nested = false] of [
  ['style', n => n.attributes.push({ name: 'style', value: 'display:none' })],
  ['class', n => n.attributes.push({ name: 'class', value: 'hidden' })],
  ['id', n => { n.attributes.find(a => a.name === 'id').value = 'changed-list'; }],
  ['本文', n => { n.childNodes[0].childNodes[0].childNodes[0].textContent = '変更'; }],
  ['項目欠落', n => { n.childNodes = []; }],
  ['OL化', n => { n.tagName = 'OL'; }],
  ['LI型', n => { n.childNodes[0].tagName = 'P'; }],
  ['リンク先', n => { n.childNodes[0].childNodes[0].childNodes[0].attributes[0].value = 'https://example.org/changed'; }],
  ['入れ子UL', () => {}, true],
]) test(`bulletList許容でも${name}は入力後に停止する`, async () => {
  const d = domBackend();
  const list = new Element('UL', { class: 'bulletList', id: 'protected-list' }, [
    new Element('LI', {}, [new Element('P', {}, name === 'リンク先'
      ? [new Element('A', { href: 'https://example.org/original' }, ['保持する要点'])] : ['保持する要点'])]),
  ]);
  const wrapper = nested ? new Element('BLOCKQUOTE', {}, [list]) : list;
  wrapper.parentElement = d.root; d.root.childNodes.push(wrapper);
  const input = guard(d.tab), checkpoint = await input.observe(), effect = d.tab.effect;
  d.tab.effect = () => { effect(); list.attributes = list.attributes.filter(a => a.name !== 'class'); change(list); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
  assert.equal(d.tab.writes.length, 1);
});
test('直下Pの意味あるclass変更は入力後も停止する', async () => {
  const d = domBackend();
  const paragraph = new Element('P', { class: 'paragraph' }, ['保持する本文']);
  paragraph.parentElement = d.root; d.root.childNodes.push(paragraph);
  const input = guard(d.tab); const checkpoint = await input.observe();
  const effect = d.tab.effect;
  d.tab.effect = () => { effect(); paragraph.attributes[0].value = 'paragraph hidden'; };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});
for (const [name, change] of [
  ['style', node => { node.attributes.push({ name: 'style', value: 'display:none' }); }],
  ['本文', node => { node.childNodes[0].textContent = '変更された本文'; }],
]) test(`直下Pのparagraph表示class許容でも${name}変化は拒否する`, async () => {
  const d = domBackend();
  const paragraph = new Element('P', { class: 'paragraph' }, ['保持する本文']);
  paragraph.parentElement = d.root; d.root.childNodes.push(paragraph);
  const input = guard(d.tab); const checkpoint = await input.observe(); const effect = d.tab.effect;
  d.tab.effect = () => { effect(); paragraph.attributes = []; change(paragraph); };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
});
test('入れ子Pのparagraph classは表示用として除外しない', async () => {
  const d = domBackend();
  const paragraph = new Element('P', { class: 'paragraph' }, ['保持する本文']);
  const wrapper = new Element('BLOCKQUOTE', {}, [paragraph]);
  wrapper.parentElement = d.root; d.root.childNodes.push(wrapper);
  const input = guard(d.tab); const checkpoint = await input.observe(); const effect = d.tab.effect;
  d.tab.effect = () => { effect(); paragraph.attributes = []; };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
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

function nativeBackend() {
  const d = domBackend();
  delete d.document.hasFocus;
  delete d.tab.paste;
  delete d.tab.getAXState;
  d.tab.axReads = 0;
  d.tab.ax = {
    async get(kind, options) {
      assert.equal(kind, 'state'); assert.deepEqual(options, { disableDiffing: true });
      d.tab.axReads++;
      const value = d.root.textContent;
      const state = `Browser tab: ${d.tab.id}, Title: ${JSON.stringify(d.document.title)}, URL: ${JSON.stringify(d.window.location.href)}.\n` +
        `  428 text entry area (settable) title\n  430 text entry area (settable) ${value}\n` +
        `The focused UI element is 430 text entry area (settable) ${value}`;
      return d.axChange ? d.axChange(state, d.tab.axReads) : state;
    },
    async paste(...args) { d.tab.writes.push(args); d.tab.effect?.(); },
  };
  return d;
}

for (const line of ['2026 report', '1 example', '  1 example', '12 button 本文の記述',
  '7 text entry area (settable) 本文の記述',
  '430 text entry area (settable) 本文の記述', '2026 🤖 report']) {
  test(`native AX: 数字始まりの本文行を保持する ${line}`, async () => {
    const d = nativeBackend();
    const paragraph = new Element('P', {}, [`前文\n${line}\n末尾`]);
    paragraph.parentElement = d.root; d.root.childNodes.push(paragraph);
    const input = guard(d.tab), checkpoint = await input.observe();
    assert.equal(checkpoint.state, 'observed');
    assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'completed');
    assert.equal(d.tab.writes.length, 1);
  });
  test(`native dialog: 数字始まりの本文行で誤停止しない ${line}`, async () => {
    const { tab, caption, sync } = dialogBackend();
    tab.current.blocks[0] = p(`前文\n${line}\n末尾`); sync();
    assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
    assert.equal(tab.writes.filter(w => w[0] === '適用').length, 1);
  });
}
test('native dialog: DOM本文の後の未知のAX追加本文を受理しない', async () => {
  const { tab, caption } = dialogBackend(), get = tab.ax.get;
  tab.ax.get = async () => (await get()).replace(tab.current.bodyText, tab.current.bodyText + '\n2026 report');
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert.equal(tab.writes.length, 0);
});
test('native AX: 実在する同ID本文rowの重複は拒否する', async () => {
  const d = nativeBackend();
  d.axChange = s => s.replace('The focused UI element is ',
    `  430 text entry area (settable) ${d.root.textContent}\nThe focused UI element is `);
  assert.equal((await guard(d.tab).observe()).state, 'blocked');
  assert.equal(d.tab.writes.length, 0);
});
test('native dialog: 実在する別ID本文rowの重複は拒否する', async () => {
  const { tab, caption } = dialogBackend(), get = tab.ax.get;
  tab.ax.get = async () => (await get()).replace('The focused UI element is ',
    `  431 text entry area (settable) ${tab.current.bodyText}\nThe focused UI element is `);
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert.equal(tab.writes.length, 0);
});
test('native AXはhasFocus未提供でも対象Tab・本文全文・選択のfresh一致で単一paste', async () => {
  const d = nativeBackend(); const input = guard(d.tab);
  const checkpoint = await input.observe(); assert.equal(checkpoint.state, 'observed');
  const result = await input.pasteUrl({ checkpoint, payload });
  assert.equal(result.state, 'completed');
  assert.deepEqual(d.tab.writes, [[null, payload, { format: 'text' }]]);
  assert.equal(d.tab.reads, 6); assert.equal(d.tab.axReads, 4);
});

for (const [name, change] of [
  ['AX別tab', d => { d.axChange = s => s.replace(`Browser tab: ${d.tab.id},`, 'Browser tab: other,'); }],
  ['AX別URL', d => { d.axChange = s => s.replace(noteUrl, 'https://editor.note.com/notes/nother/edit/'); }],
  ['AX別title', d => { d.axChange = s => s.replace(JSON.stringify(d.document.title), '"wrong title"'); }],
  ['AXタイトル欄focus', d => { d.axChange = s => s.replace('The focused UI element is 430', 'The focused UI element is 428'); }],
  ['AX全文差分', d => { d.axChange = s => s + 'unexpected'; }],
  ['AX本文row欠落', d => { d.axChange = s => s.replace('  430 text entry area', '  431 text entry area'); }],
  ['AXfocusなし', d => { d.axChange = s => s.split('The focused UI element')[0]; }],
  ['AXfresh間ID変更', d => { d.axChange = (s, n) => n % 2 ? s : s.replaceAll('430 text entry area', '431 text entry area'); }],
  ['DOMhasFocus false', d => { d.document.hasFocus = () => false; }],
  ['DOMactiveElementはrootの子', d => { d.document.activeElement = d.title; }],
  ['DOMselection非collapsed', d => { d.selection.isCollapsed = false; }],
  ['AX取得中navigation', d => { d.axChange = s => { d.window.location.href = 'https://editor.note.com/notes/nother/edit/'; return s; }; }],
]) test(`native ${name}はpaste未実行でblocked`, async () => {
  const d = nativeBackend(); change(d);
  const result = await guard(d.tab).observe(); assert.equal(result.state, 'blocked'); assert.equal(d.tab.writes.length, 0);
});

test('native AX全文は改行・空白のみの表現差を許す', async () => {
  const d = nativeBackend(); d.axChange = s => s.replace('The focused UI element is 430 text entry area (settable) ', 'The focused UI element is 430 text entry area (settable) \n\n');
  assert.equal((await guard(d.tab).observe()).state, 'observed');
});

test('native observe後のAXfocus driftは再取得でwrite前に止める', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  d.axChange = s => s.replace('The focused UI element is 430', 'The focused UI element is 428');
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked'); assert.equal(d.tab.writes.length, 0);
});

test('native本文rowのtruncateをfocused全文一致で代替しない', async () => {
  const d = nativeBackend(); d.axChange = s => s.replace(`  430 text entry area (settable) ${d.root.textContent}`, '  430 text entry area (settable) short');
  assert.equal((await guard(d.tab).observe()).state, 'blocked'); assert.equal(d.tab.writes.length, 0);
});

test('native非同期pendingはread-only reconcileし単一pasteを維持', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  d.tab.effect = () => { d.root.childNodes[1] = new Element('P', {}, [payload]); d.root.childNodes[1].parentElement = d.root; };
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'pending');
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'pending');
  d.root.childNodes[1] = new Element('FIGURE', { 'data-src': payload }); d.root.childNodes[1].parentElement = d.root;
  assert.equal((await input.reconcile()).state, 'completed'); assert.equal(d.tab.writes.length, 1);
});

// カード生成は入力位置の焦点を移す。入力前の焦点と、入力後の本文保持を分ける。
test('nativeカード生成後の焦点移動でも本文保持を確認して完了する', async () => {
  const d = nativeBackend(); const input = guard(d.tab);
  const checkpoint = await input.observe();
  d.axChange = state => d.tab.writes.length ? state.replace(/The focused UI element is 430 text entry area \(settable\) [\s\S]*/, 'The focused UI element is 0 AXWebArea 無害fixture') : state;
  const result = await input.pasteUrl({ checkpoint, payload });
  assert.equal(result.state, 'completed');
  assert.equal(d.tab.writes.length, 1);
});
test('nativeカード生成後の焦点移動でも保護本文変更は拒否する', async () => {
  const d = nativeBackend(); const input = guard(d.tab);
  const checkpoint = await input.observe(); const originalEffect = d.tab.effect;
  d.tab.effect = () => { originalEffect(); d.root.childNodes[0].childNodes[0].textContent = '不正に変わった本文'; };
  d.axChange = state => d.tab.writes.length ? state.replace(/The focused UI element is 430 text entry area \(settable\) [\s\S]*/, 'The focused UI element is 0 AXWebArea 無害fixture') : state;
  assert.equal((await input.pasteUrl({ checkpoint, payload })).state, 'blocked');
  assert.equal(d.tab.writes.length, 1);
});

test('貼付け後の読取り失敗を再入力なしで照合復旧する', async () => {
  const {tab,input,checkpoint}=await prepared();
  tab.effect=()=>{tab.current.blocks[1]=card();tab.current.rawHtml+='<figure></figure>';tab.readFailure=true;};
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  assert.equal((await input.reconcile()).state,'pending');
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  tab.readFailure=false;
  assert.equal((await input.reconcile()).state,'completed');
  assert.equal(tab.writes.length,1);
});
test('読取り復旧後の保護本文変更は停止を維持する', async () => {
  const {tab,input,checkpoint}=await prepared();
  tab.effect=()=>{tab.current.blocks[1]=card();tab.readFailure=true;};
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  tab.readFailure=false;tab.current.blocks[0]=p('未承認の本文変更');
  assert.equal((await input.reconcile()).state,'blocked');
  assert.equal((await input.observe()).state,'blocked');
  assert.equal(tab.writes.length,1);
});

test('native入力後はAX取得障害と選択移動を本文差分として扱わない', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  const effect = d.tab.effect;
  d.tab.effect = () => {
    effect();
    d.selection.anchorNode = d.title.childNodes[0]; d.selection.focusNode = d.title.childNodes[0];
    d.selection.anchorOffset = 2; d.selection.focusOffset = 2;
  };
  d.axChange = state => { if (d.tab.writes.length) throw Error('秘密のAXエラー'); return state; };
  const result = await input.pasteUrl({checkpoint,payload});
  assert.equal(result.state, 'completed'); assert.equal(d.tab.writes.length, 1);
  assert.equal(d.tab.axReads, 4);
});

test('native入力後の一時的なDOM読取り障害は安全な診断を残して読取りだけで復旧する', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  const evaluate = d.tab.playwright.evaluate;
  d.tab.playwright.evaluate = async fn => {
    if (d.tab.writes.length && d.failRead !== false) throw Error('秘密本文と認証値');
    return evaluate(fn);
  };
  const result = await input.pasteUrl({checkpoint,payload});
  assert.equal(result.state, 'pending');
  assert.deepEqual(result.diagnostic, {code:'dom_read_unavailable',phase:'dom_read',recoverable:true});
  assert(!JSON.stringify(result).includes('秘密'));
  d.failRead = false;
  assert.equal((await input.reconcile()).state, 'completed');
  assert.equal(d.tab.writes.length, 1);
});

for (const [name, change, code] of [
  ['別tab', tab => {tab.id += '-different';}, 'target_tab_changed'],
  ['別note', tab => {tab.current.url = 'https://editor.note.com/notes/nother/edit/';}, 'target_url_changed'],
  ['複数root', tab => {tab.current.rootCount = 2;}, 'editor_root_ambiguous'],
]) test(`入力後の${name}はpendingへ丸めず即座に停止する`, async () => {
  const {tab,input,checkpoint} = await prepared();
  tab.effect = () => {tab.current.blocks[1] = card(); change(tab);};
  const result = await input.pasteUrl({checkpoint,payload});
  assert.equal(result.state,'blocked'); assert.equal(result.diagnostic.code,code);
  assert.equal(result.diagnostic.recoverable,false); assert.equal(tab.writes.length,1);
});

test('root読込み途中はpending、復旧後は保護本文を再照合する', async () => {
  const {tab,input,checkpoint} = await prepared();
  tab.effect = () => {tab.current.blocks[1] = card(); tab.current.rootCount = 0;};
  const result = await input.pasteUrl({checkpoint,payload});
  assert.equal(result.state,'pending'); assert.equal(result.diagnostic.code,'editor_root_loading');
  tab.current.rootCount = 1; tab.current.blocks[0] = p('後から変更された本文');
  const after = await input.reconcile();
  assert.equal(after.state,'blocked'); assert.equal(after.diagnostic.code,'protected_document_changed');
  assert.equal(tab.writes.length,1);
});

test('native意味DOM読取り中の変化はpending、安定後に保護差分を判定する', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  const evaluate = d.tab.playwright.evaluate; let postReads = 0;
  d.tab.playwright.evaluate = async fn => {
    if (d.tab.writes.length && ++postReads === 2) d.title.childNodes[0].textContent = '保護本文の不正変更';
    return evaluate(fn);
  };
  const result = await input.pasteUrl({checkpoint,payload});
  assert.equal(result.state,'pending'); assert.equal(result.diagnostic.code,'document_unstable');
  const after = await input.reconcile();
  assert.equal(after.state,'blocked'); assert.equal(after.diagnostic.code,'protected_document_changed');
  assert.equal(d.tab.writes.length,1);
});

for (const mode of ['read_failure','card_loading']) test(`${mode}は最大6回で待機を終了し再入力を禁止する`, async () => {
  const {tab,input,checkpoint} = await prepared();
  tab.effect = () => {
    tab.current.blocks[1] = loadingBlock();
    if (mode === 'read_failure') tab.readFailure = true;
  };
  const first = await input.pasteUrl({checkpoint,payload});
  assert.equal(first.state,'pending'); assert.equal(first.reconcile_attempt,0);
  for (let n=1;n<6;n++) {
    const result = await input.reconcile();
    assert.equal(result.state,'pending'); assert.equal(result.reconcile_attempt,n);
  }
  const exhausted = await input.reconcile();
  assert.equal(exhausted.state,'blocked'); assert.equal(exhausted.reason,'reconcile_limit_reached');
  assert.equal(exhausted.reconcile_attempt,6); assert.equal(exhausted.max_reconcile_attempts,6);
  assert.equal((await guard(tab).observe()).state,'blocked');
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'blocked');
  assert.equal(tab.writes.length,1); assert(!JSON.stringify(exhausted).includes('秘密'));
});

test('native表示属性の変化は意味DOMの安定読取りを妨げない', async () => {
  const d = nativeBackend(); const input = guard(d.tab); const checkpoint = await input.observe();
  const evaluate = d.tab.playwright.evaluate;
  d.tab.playwright.evaluate = async fn => {
    if (d.tab.writes.length) d.root.attributes.find(a=>a.name==='class').value = d.tab.reads % 2
      ? 'ProseMirror ProseMirror-focused' : 'ProseMirror ProseMirror-hideselection';
    return evaluate(fn);
  };
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'completed');
  assert.equal(d.tab.writes.length,1);
});


test('深い実カードDOMはJSON文字列で転送しhost再帰上限で欠落しない', async () => {
  const d = domBackend();
  const original = d.tab.playwright.evaluate;
  d.tab.playwright.evaluate = async fn => {
    const value = await original(fn);
    assert.equal(typeof value.blocksJson, 'string');
    // Browser bridgeの深さ制限を模擬してもblocksJsonは文字列のまま残る。
    return JSON.parse(JSON.stringify(value));
  };
  const input = guard(d.tab); const checkpoint = await input.observe();
  assert.equal(checkpoint.state, 'observed');
  assert.equal((await input.pasteUrl({checkpoint, payload})).state, 'completed');
  assert.equal(d.tab.writes.length, 1);
});
test('切り詰められたDOMは例外を隠さず安全な診断で読取り停止する', async () => {
  const tab = backend(); tab.current.blocks[0].children = '[MaxDepth]';
  const result = await guard(tab).observe();
  assert.equal(result.state, 'blocked');
  assert.equal(result.diagnostic.code, 'dom_tree_truncated');
  assert.equal(tab.writes.length, 0);
});


test('正規に取得したコメントノードは保持して照合する', async () => {
  const tab = backend(); const comment = {tag: '#8', text: '保持するコメント'};
  tab.current.blocks[0].children.push(comment);
  tab.effect = () => { tab.current.blocks[1] = card(); tab.current.rawHtml += '<figure></figure>'; };
  const input = guard(tab); const checkpoint = await input.observe();
  assert.equal(checkpoint.state, 'observed');
  assert.equal((await input.pasteUrl({checkpoint, payload})).state, 'completed');
  assert.equal(tab.writes.length, 1);
  assert.deepEqual(tab.current.blocks[0].children.at(-1), comment);
});

test('型付き段落はescapeしたHTMLを一度だけ貼り付けて照合する', async () => {
  const {tab,input,checkpoint}=await prepared();
  const paragraphs=['一行<>&"\n二行','次の段落'];
  tab.effect=()=>{tab.current.blocks.splice(1,1,
    {tag:'P',attrs:[],children:[text('一行<>&"'),{tag:'BR',attrs:[],children:[]},text('二行')]},p('次の段落'));};
  const result=await input.pasteParagraphs({checkpoint,paragraphs});
  assert.equal(result.state,'completed');
  assert.deepEqual(tab.writes,[[null,'<p>一行&lt;&gt;&amp;&quot;<br>二行</p><p>次の段落</p>',{format:'html'}]]);
});

// Native Note replaces the empty paragraph's id/name with a fresh pair for
// each pasted paragraph. Only these managed identities may change.
const paragraphIds = [
  'dbc00000-0000-4000-8000-000000000001',
  '840c0000-0000-4000-8000-000000000002',
  '3b400000-0000-4000-8000-000000000003',
];
function identifiedParagraph(value, id, extra = []) {
  return { ...p(value), attrs: [['id', id], ['name', id], ...extra] };
}
async function nativeParagraphFixture(change = () => {}) {
  const tab = backend();
  const extra = [['data-owner', 'preserved']];
  tab.current.blocks[1] = identifiedParagraph('', paragraphIds[0], extra);
  const input = guard(tab); const checkpoint = await input.observe();
  const before = structuredClone(tab.current);
  tab.effect = () => {
    tab.current.blocks.splice(1, 1,
      identifiedParagraph('一段', paragraphIds[1], extra),
      identifiedParagraph('二段', paragraphIds[2], extra));
    change(tab.current);
  };
  return { tab, input, checkpoint, before };
}
test('native段落: 空PのUUID id/nameだけを二つの新UUIDへ束縛し全外側blockを保持', async () => {
  const { tab, input, checkpoint, before } = await nativeParagraphFixture();
  const result = await input.pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] });
  assert.equal(result.state, 'completed');
  assert.equal(tab.writes.length, 1);
  assert.deepEqual(tab.current.blocks.slice(0, 1), before.blocks.slice(0, 1));
  assert.deepEqual(tab.current.blocks.slice(3), before.blocks.slice(2));
  assert.deepEqual(tab.current.rootAttrs, before.rootAttrs);
  assert.equal(tab.current.title, before.title);
  assert.equal(tab.current.url, before.url);
});
for (const [name, change] of [
  ['duplicate inserted identity', s => { s.blocks[2].attrs = structuredClone(s.blocks[1].attrs); }],
  ['mismatched name', s => { s.blocks[1].attrs[1][1] = paragraphIds[2]; }],
  ['missing name', s => { s.blocks[1].attrs.splice(1, 1); }],
  ['unknown identity', s => { s.blocks[1].attrs[0][1] = s.blocks[1].attrs[1][1] = 'spoofed-id'; }],
  ['duplicate id attribute', s => { s.blocks[1].attrs.push(['id', paragraphIds[1]]); }],
  ['nonidentity attribute change', s => { s.blocks[1].attrs[2][1] = 'changed'; }],
  ['nonidentity attribute removal', s => { s.blocks[1].attrs.pop(); }],
  ['unexpected inline element', s => { s.blocks[1].children = [{ tag: 'STRONG', attrs: [], children: [text('一段')] }]; }],
  ['extra break', s => { s.blocks[1].children.push({ tag: 'BR', attrs: [], children: [] }); }],
  ['outside text change', s => { s.blocks[0].children = [text('変化')]; }],
  ['outside identity change', s => { s.blocks[3].attrs = [['id', paragraphIds[2]]]; }],
  ['title change', s => { s.title = '変化'; }],
  ['root change', s => { s.rootAttrs.push(['data-owner', 'changed']); }],
]) test(`native段落: ${name}は一度の入力後にchannelを停止`, async () => {
  const { tab, input, checkpoint } = await nativeParagraphFixture(change);
  assert.equal((await input.pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] })).state, 'blocked');
  assert.equal((await guard(tab).pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] })).state, 'blocked');
  assert.equal(tab.writes.length, 1);
});
for (const identityAttr of ['id', 'name']) test(`native段落: 既存descendantの${identityAttr}とのUUID衝突を停止`, async () => {
  const tab = backend();
  tab.current.blocks[0].children.push({ tag: 'SPAN', attrs: [[identityAttr, paragraphIds[1]]], children: [] });
  tab.current.blocks[1] = identifiedParagraph('', paragraphIds[0]);
  const input = guard(tab); const checkpoint = await input.observe();
  tab.effect = () => { tab.current.blocks.splice(1, 1,
    identifiedParagraph('一段', paragraphIds[1]), identifiedParagraph('二段', paragraphIds[2])); };
  assert.equal((await input.pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] })).state, 'blocked');
  assert.equal(tab.writes.length, 1);
});
for (const identityAttr of ['id', 'name']) test(`native段落: rootの${identityAttr}とのUUID衝突を停止`, async () => {
  const tab = backend();
  tab.current.rootAttrs.push([identityAttr, paragraphIds[1]]);
  tab.current.blocks[1] = identifiedParagraph('', paragraphIds[0]);
  const input = guard(tab); const checkpoint = await input.observe();
  const rootAttrs = structuredClone(tab.current.rootAttrs);
  tab.effect = () => { tab.current.blocks.splice(1, 1,
    identifiedParagraph('一段', paragraphIds[1]), identifiedParagraph('二段', paragraphIds[2])); };
  assert.equal((await input.pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] })).state, 'blocked');
  assert.deepEqual(tab.current.rootAttrs, rootAttrs);
  assert.equal((await guard(tab).pasteParagraphs({ checkpoint, paragraphs: ['一段', '二段'] })).state, 'blocked');
  assert.equal(tab.writes.length, 1);
});
for (const attrs of [[], [['id', 'unknown'], ['name', 'unknown']], [['id', paragraphIds[0]]]])
  test(`native段落: 元Pの未管理identityから再束縛しない ${JSON.stringify(attrs)}`, async () => {
    const tab = backend(); tab.current.blocks[1].attrs = attrs;
    const input = guard(tab); const checkpoint = await input.observe();
    tab.effect = () => { tab.current.blocks.splice(1, 1, identifiedParagraph('一段', paragraphIds[1])); };
    assert.equal((await input.pasteParagraphs({ checkpoint, paragraphs: ['一段'] })).state, 'blocked');
  });

for (const [name,change] of [
  ['前P末尾anchor',q=>{q.ranges[0].start.blockIndex=0;q.ranges[0].start.offset=9;}],
  ['終端が対象外',q=>{q.ranges[0].end.blockIndex=2;}],
  ['widget交差',q=>{q.ranges[0].protectedIntersections=[{blockIndex:2,nodePath:[],offset:0}];}],
  ['Range取得不能',q=>{q.intersectionsKnown=false;}],
  ['Range重複',q=>{q.ranges.push(structuredClone(q.ranges[0]));}],
  ['Range配列欠落',q=>{delete q.ranges;}],
  ['負offset',q=>{q.ranges[0].start.offset=-1;}],
  ['不正node path',q=>{q.ranges[0].start.nodePath=[-1];}],
]) test(`Range ${name}: 文字一致によらず両入力を停止`,async()=>{
  const {tab,input,checkpoint}=await prepared();change(tab.current.selection);
  assert.equal(selectionWithinBlock(tab.current,1),false);
  assert.equal((await input.pasteParagraphs({checkpoint,paragraphs:['追記']})).state,'blocked');
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'blocked');assert.equal(tab.writes.length,0);
});
test('重複文字の段落を文字列で解決せずRange境界で拒否する',async()=>{
  const tab=backend();tab.current.blocks=[p('同じ本文'),p('同じ本文'),p('')];
  tab.current.selection.blockIndex=2;
  tab.current.selection.ranges[0].start.blockIndex=0;
  tab.current.selection.ranges[0].end.blockIndex=1;
  assert.equal((await guard(tab).observe()).state,'blocked');assert.equal(tab.writes.length,0);
});
for (const paragraphs of [null,[],[''],['   '],[9],['本文\r改行'],['本文\u0000'],Array(101).fill('段落')])
  test(`不正typed段落 ${JSON.stringify(paragraphs)?.slice(0,25)}`,async()=>{
    const {tab,input,checkpoint}=await prepared();
    assert.equal((await input.pasteParagraphs({checkpoint,paragraphs})).state,'blocked');assert.equal(tab.writes.length,0);
  });
for (const [method,extra] of [['pasteUrl',{paragraphs:['迂回']}],['pasteParagraphs',{payload:'<p>任意HTML</p>'}],['pasteParagraphs',{html:'<p>任意HTML</p>'}],['pasteParagraphs',{callback:()=>{}}]])
  test(`${method}: 別種payloadやcallbackを拒否 ${Object.keys(extra)[0]}`,async()=>{
    const {tab,input,checkpoint}=await prepared();
    assert.equal((await input[method]({checkpoint,...(method==='pasteParagraphs'?{paragraphs:['追記']}:{payload}),...extra})).state,'blocked');
    assert.equal(tab.writes.length,0);
  });
for (const [name,effect] of [
  ['P数不足',s=>s.blocks.splice(1,1,p('一行二行次'))],
  ['br不足',s=>s.blocks.splice(1,1,p('一行二行'),p('次'))],
  ['br過剰',s=>s.blocks.splice(1,1,{tag:'P',attrs:[],children:[text('一行'),{tag:'BR',attrs:[],children:[]},{tag:'BR',attrs:[],children:[]},text('二行')]},p('次'))],
  ['前本文変更',s=>{s.blocks.splice(1,1,p('一行\n二行'),p('次'));s.blocks[0]=p('変化');}],
  ['後本文変更',s=>{s.blocks.splice(1,1,p('一行\n二行'),p('次'));s.blocks.at(-1).children=[text('変化')];}],
  ['別note',s=>{s.url='https://editor.note.com/notes/nother/edit/';}],
]) test(`段落挿入後 ${name}: 一回で停止`,async()=>{
  const {tab,input,checkpoint}=await prepared();tab.effect=()=>effect(tab.current);
  assert.equal((await input.pasteParagraphs({checkpoint,paragraphs:['一行\n二行','次']})).state,'blocked');
  await input.pasteParagraphs({checkpoint,paragraphs:['一行\n二行','次']});assert.equal(tab.writes.length,1);
});
test('URL pendingを段落入口で迂回できない',async()=>{
  const {tab,input,checkpoint}=await prepared();
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  assert.equal((await guard(tab).pasteParagraphs({checkpoint,paragraphs:['追記']})).state,'pending');assert.equal(tab.writes.length,1);
});
test('段落書込後read失敗は一度だけ貼り付けてread-onlyで復旧',async()=>{
  const {tab,input,checkpoint}=await prepared();
  tab.effect=()=>{tab.current.blocks.splice(1,1,p('一段'),p('二段'));tab.readFailure=true;};
  assert.equal((await input.pasteParagraphs({checkpoint,paragraphs:['一段','二段']})).state,'pending');
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  assert.equal((await input.pasteParagraphs({checkpoint,paragraphs:['一段','二段']})).state,'pending');
  tab.readFailure=false;assert.equal((await input.reconcile()).state,'completed');assert.equal(tab.writes.length,1);
});
test('実DOMはRange両端と保護widget交差を採取する',async()=>{
  const d=domBackend();
  d.selection.getRangeAt=()=>({startContainer:d.title.childNodes[0],startOffset:2,
    endContainer:d.blank,endOffset:0,intersectsNode:n=>n===d.toc});
  const s=await d.tab.playwright.evaluate(readNoteDom);
  assert.deepEqual(JSON.parse(JSON.stringify(s.selection.ranges)),[{start:{blockIndex:0,nodePath:[0],offset:2},
    end:{blockIndex:1,nodePath:[],offset:0},protectedIntersections:[{blockIndex:2,nodePath:[],offset:0}]}]);
  assert.equal(selectionWithinBlock(s,1),false);
  assert.equal((await guard(d.tab).observe()).state,'blocked');assert.equal(d.tab.writes.length,0);
});

function scrollBackend(top = 200) {
  const tab = backend();
  tab.current.view = {width:800,height:600,scrollTop:top,scrollHeight:1200,clientHeight:600,scroller:'document',point:[400,300]};
  tab.scrolls = [];
  tab.ax = { async scroll(...args) { tab.scrolls.push(args); tab.scrollEffect?.(); } };
  return tab;
}
test('先頭到達済みならnative scrollを呼ばない',async()=>{
  const tab=scrollBackend(0); const result=await guard(tab).scrollToEdge({edge:'top'});
  assert.equal(result.reason,'scroll_edge_verified');assert.equal(result.steps,0);assert.equal(tab.scrolls.length,0);
});
for (const edge of ['top','bottom']) test(`${edge}へnative scrollし本文とselectionを保持する`,async()=>{
  const tab=scrollBackend();tab.scrollEffect=()=>{tab.current.view.scrollTop=edge==='top'?0:600;};
  const before=structuredClone(tab.current.selection);
  const result=await guard(tab).scrollToEdge({edge});
  assert.equal(result.state,'completed');assert.equal(result.steps,1);
  assert.deepEqual(tab.scrolls,[[[400,300],edge==='top'?'up':'down',1]]);
  assert.deepEqual(tab.current.selection,before);assert.equal(tab.writes.length,0);
});
for (const [name,effect,expected] of [
  ['進捗なし',()=>{},'scroll_no_progress'],
  ['別対象',t=>{t.current.url='https://editor.note.com/notes/nother/edit/';},'scroll_outcome_unverified'],
  ['本文変化',t=>{t.current.blocks[0]=p('変更');},'scroll_document_changed'],
  ['selection変化',t=>{t.current.selection.anchorOffset=1;},'scroll_document_changed'],
  ['scroll container変化',t=>{t.current.view.scroller='other';},'scroll_document_changed'],
  ['native結果不明',()=>{throw Error('timeout');},'scroll_outcome_unverified'],
]) test(`scroll ${name}は一度で停止し再送しない`,async()=>{
  const tab=scrollBackend();tab.scrollEffect=()=>{tab.current.view.scrollTop=0;effect(tab);};
  if(name==='進捗なし') tab.scrollEffect=()=>{};
  const input=guard(tab);assert.equal((await input.scrollToEdge({edge:'top'})).reason,expected);
  assert.equal((await input.scrollToEdge({edge:'top'})).state,'blocked');assert.equal(tab.scrolls.length,1);
});
for (const request of [{edge:'left'},{edge:'top',maxSteps:0},{edge:'top',maxSteps:21},{edge:'top',timeoutMs:0},{edge:'top',timeoutMs:60001},{edge:'top',callback:()=>{}},null])
  test(`不正scroll要求 ${JSON.stringify(request)}`,async()=>{
    const tab=scrollBackend();assert.equal((await guard(tab).scrollToEdge(request)).state,'blocked');assert.equal(tab.scrolls.length,0);
  });
test('scrollは上限回数で停止する',async()=>{
  const tab=scrollBackend();tab.scrollEffect=()=>{tab.current.view.scrollTop--;};
  assert.equal((await guard(tab).scrollToEdge({edge:'top',maxSteps:2})).reason,'scroll_limit_reached');assert.equal(tab.scrolls.length,2);
});
test('scrollは期限を観測したら新しい操作を始めない',async()=>{
  const tab=scrollBackend();const original=tab.playwright.evaluate;
  tab.playwright.evaluate=async()=>{await new Promise(resolve=>setTimeout(resolve,5));return original();};
  assert.equal((await guard(tab).scrollToEdge({edge:'top',timeoutMs:1})).reason,'scroll_limit_reached');assert.equal(tab.scrolls.length,0);
});
for (const [name,change,reason] of [
  ['viewportなし',t=>{delete t.current.view;},'scroll_observation_unavailable'],
  ['不正寸法',t=>{t.current.view.width=NaN;},'scroll_observation_unavailable'],
  ['点が画面外',t=>{t.current.view.point=[900,300];},'scroll_point_unavailable'],
  ['遮蔽',t=>{t.current.view.point=null;},'scroll_point_unavailable'],
  ['native非対応',t=>{delete t.ax.scroll;},'native_scroll_unavailable'],
]) test(`scroll ${name}は操作前に拒否`,async()=>{
  const tab=scrollBackend();change(tab);assert.equal((await guard(tab).scrollToEdge({edge:'top'})).reason,reason);assert.equal(tab.scrolls.length,0);
});
test('pending入力中はscrollできない',async()=>{
  const tab=scrollBackend();const input=guard(tab);const checkpoint=await input.observe();
  assert.equal((await input.pasteUrl({checkpoint,payload})).state,'pending');
  assert.equal((await input.scrollToEdge({edge:'top'})).state,'pending');assert.equal(tab.scrolls.length,0);
});

test('実DOMで最寄りscroll containerとroot内点を取得する',async()=>{
  const d=domBackend();
  const scroller=new Element('DIV',{},[d.root]);
  Object.assign(scroller,{scrollTop:200,scrollHeight:1200,clientHeight:500,
    getBoundingClientRect:()=>({left:100,right:700,top:50,bottom:550})});
  d.root.getBoundingClientRect=()=>({left:150,right:650,top:-200,bottom:1000});
  Object.assign(d.window,{innerWidth:800,innerHeight:600,getComputedStyle:node=>({overflowY:node===scroller?'auto':'visible'})});
  d.document.scrollingElement={tagName:'HTML'};
  d.document.elementFromPoint=()=>d.blank;
  const snapshot=await d.tab.playwright.evaluate(readNoteDom);
  assert.deepEqual(JSON.parse(JSON.stringify(snapshot.view)),{width:800,height:600,scrollTop:200,scrollHeight:1200,clientHeight:500,scroller:'[false,"DIV",[]]',point:[400,300]});
  d.document.elementFromPoint=()=>new Element('DIALOG');
  assert.equal((await d.tab.playwright.evaluate(readNoteDom)).view.point,null);
});

test('実DOMで非overflowのauto内枠を飛ばし外側scroll containerを採る',async()=>{
  const d=domBackend();
  const inner=new Element('DIV',{},[d.root]);
  Object.assign(inner,{scrollTop:0,scrollHeight:500,clientHeight:500});
  const outer=new Element('DIV',{},[inner]);
  Object.assign(outer,{scrollTop:200,scrollHeight:1400,clientHeight:500,
    getBoundingClientRect:()=>({left:100,right:700,top:50,bottom:550})});
  d.root.getBoundingClientRect=()=>({left:150,right:650,top:-200,bottom:1000});
  Object.assign(d.window,{innerWidth:800,innerHeight:600,getComputedStyle:node=>({overflowY:node===inner||node===outer?'auto':'visible'})});
  d.document.scrollingElement={tagName:'HTML'};d.document.elementFromPoint=()=>d.blank;
  const snapshot=await d.tab.playwright.evaluate(readNoteDom);
  assert.equal(snapshot.view.scrollHeight,1400);assert.equal(snapshot.view.scrollTop,200);
  assert.equal(snapshot.view.scroller,'[false,"DIV",[]]');
});
for(const outside of [false,true]) test(`scroll範囲0のdocumentで本文全体${outside?'画面外は拒否':'表示なら到達済み'}`,async()=>{
  const d=domBackend();
  d.root.getBoundingClientRect=()=>({left:100,right:700,top:outside?700:50,bottom:outside?1100:550});
  Object.assign(d.window,{innerWidth:800,innerHeight:600,getComputedStyle:()=>({overflowX:'visible',overflowY:'visible'})});
  d.document.scrollingElement={tagName:'HTML',scrollTop:0,scrollHeight:600,clientHeight:600};
  d.document.elementFromPoint=()=>d.blank;
  d.tab.ax={async scroll(){throw Error('must not scroll');}};
  const snapshot=await d.tab.playwright.evaluate(readNoteDom);
  if(outside) assert.equal(snapshot.view,null);
  else assert.equal(snapshot.view.scrollHeight,600);
  const result=await guard(d.tab).scrollToEdge({edge:'bottom'});
  assert.equal(result.reason,outside?'scroll_observation_unavailable':'scroll_edge_verified');
});

test('document範囲0でもhidden祖先が本文をclipしていれば中心hitだけで成功にしない',async()=>{
  const d=domBackend();const clipper=new Element('DIV',{},[d.root]);
  Object.assign(clipper,{scrollTop:0,scrollHeight:500,clientHeight:300,
    getBoundingClientRect:()=>({left:100,right:700,top:50,bottom:350})});
  d.root.getBoundingClientRect=()=>({left:100,right:700,top:50,bottom:550});
  Object.assign(d.window,{innerWidth:800,innerHeight:600,getComputedStyle:node=>({overflowX:'visible',overflowY:node===clipper?'hidden':'visible'})});
  d.document.scrollingElement={tagName:'HTML',scrollTop:0,scrollHeight:600,clientHeight:600};
  d.document.elementFromPoint=()=>d.blank;
  d.tab.ax={async scroll(){throw Error('must not scroll');}};
  assert.equal((await d.tab.playwright.evaluate(readNoteDom)).view,null);
  assert.equal((await guard(d.tab).scrollToEdge({edge:'bottom'})).reason,'scroll_observation_unavailable');
});

test('native dialog: 紹介Pのsoft breakとリンクを保持する', async () => {
  const { tab, caption, sync } = dialogBackend();
  tab.current.blocks[2].children = [text(caption.slice(0, 3)), { tag: 'BR', attrs: [], children: [] }, text(caption.slice(3))]; sync();
  const original = structuredClone(tab.current.blocks[2]);
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.deepEqual(tab.current.blocks[2], original);
});

test('native dialog: 一時的なAX本文遅延は読取りだけで安定を待つ', async () => {
  const { tab, caption } = dialogBackend(); const original = tab.ax.get; let calls = 0;
  tab.ax.get = async () => {
    const state = await original();
    return calls++ === 0 ? state.replace(`430 text entry area (settable) ${tab.current.bodyText}`, '430 text entry area (settable) temporary') : state;
  };
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'completed');
  assert.equal(tab.writes.filter(w => w[0] === 'select' && w[1] === caption).length, 1);
  assert.equal(tab.writes.filter(w => w[0] === '適用').length, 1);
});
test('native dialog: AX本文が安定しなければ操作前に拒否する', async () => {
  const { tab, caption } = dialogBackend(); const original = tab.ax.get; let calls = 0;
  tab.ax.get = async () => { calls++; return (await original()).replace(`430 text entry area (settable) ${tab.current.bodyText}`, '430 text entry area (settable) wrong'); };
  assert.equal((await guard(tab).embedViaNativeDialog({ payload, caption })).state, 'blocked');
  assert.equal(calls, 3); assert.equal(tab.writes.length, 0);
});

for (const initialId of [null, 'null']) test(`native dialog: card ID ${initialId}は再Applyせず生成を待つ`, async () => {
  const { tab, caption, sync } = dialogBackend(); const click = tab.ax.click;
  tab.ax.click = async id => { await click(id); tab.current.blocks[3].attrs = [['data-src', payload], ...(initialId === null ? [] : [['id', initialId]])]; sync(); };
  const input = guard(tab); const result = await input.embedViaNativeDialog({ payload, caption });
  assert.equal(result.state, 'pending'); assert.equal(result.reason, 'native_embed_card_id_loading');
  assert.equal((await input.completeNativeEmbed()).state, 'pending');
  assert(!tab.writes.some(w => w[0] === 'Backspace'));
  tab.current.blocks[3].attrs = [['data-src', payload], ['id', 'eventual-native-card']]; sync();
  assert.equal((await input.completeNativeEmbed()).state, 'completed');
  assert.equal(tab.writes.filter(w => w[0] === '適用').length, 1);
  assert.equal(tab.writes.filter(w => w[0] === 'Backspace').length, 1);
});
