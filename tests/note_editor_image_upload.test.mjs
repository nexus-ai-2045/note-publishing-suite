import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import { mkdtemp, writeFile, rm, open } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createNoteInputGuard } from '../scripts/note_editor_guarded_input.mjs';

const noteUrl = 'https://editor.note.com/notes/nfixture000001/edit/';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=', 'base64');
let sequence = 0;
async function imageFixture(t, kind = 'body') {
  const directory = await mkdtemp(join(tmpdir(), 'nps-image-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const imagePath = join(directory, 'approved.png');
  await writeFile(imagePath, png);
  const current = {
    url: noteUrl, title: '無害fixture', rootCount: 1, rootAttrs: [], visible: true,
    blocks: [{tag:'P',attrs:[['id','anchor']],children:[{tag:'#text',text:'本文'}]}],
    rawHtml: '<p id="anchor">本文</p>', bodyText: '本文',
    selection: {collapsed:true, rangeCount:1, intersectionsKnown:true, inside:true, blockIndex:0,
      ranges:[{start:{blockIndex:0,nodePath:[0],offset:2},end:{blockIndex:0,nodePath:[0],offset:2},protectedIntersections:[]}]},
  };
  const writes = [];
  let resolve, reject;
  const tab = {
    id: `image-fixture-${++sequence}`, current, writes,
    async url() { return current.url; },
    ax: {
      async get() { return `Browser tab: ${tab.id}, Title: ${JSON.stringify(current.title)}, URL: ${JSON.stringify(current.url)}.\n  430 text entry area (settable) ${current.bodyText}\n  501 ${kind === 'body' ? 'checkbox 画像, Value: 0' : 'button 画像をアップロード 推奨サイズ：1280×670px'}\n`; },
      async paste() { throw Error('No clipboard route'); },
      async click(index) {
        writes.push(`click:${index}`);
        await tab.onClick?.();
        if (tab.waitFailure) reject(Error('private error'));
        else if (!tab.holdChooser) resolve(chooser);
        if (tab.clickFailure) throw Error('private click error');
      },
    },
    playwright: {
      async evaluate() { return structuredClone(current); },
      waitForEvent(event) {
        assert.equal(event, 'filechooser'); writes.push('wait');
        return new Promise((ok, fail) => { resolve = ok; reject = fail; });
      },
    },
  };
  const chooser = { async setFiles(files) {
    writes.push('setFiles'); assert.deepEqual(files, [imagePath]);
    if (tab.selectionFailure) throw Error('private path error');
  } };
  const request = {kind, imagePath, imageSha256:createHash('sha256').update(png).digest('hex'), controlIndex:501,
    ...(kind === 'body' ? {anchorId:'anchor'} : {})};
  const input = createNoteInputGuard(tab, {tabId:tab.id,noteUrl});
  return {tab,input,request,imagePath,chooser,resolveChooser:() => resolve(chooser)};
}

for (const kind of ['body','cover']) test(`native image ${kind}: 待機→click→正式setFiles、選択だけを報告`, async t => {
  const {tab,input,request}=await imageFixture(t,kind);
  const result=await input.chooseImageFile(request);
  assert.deepEqual(tab.writes,['wait','click:501','setFiles']);
  assert.equal(result.state,'selected');
  assert.equal(result.image_sha256,request.imageSha256);
  assert.equal(result.render_verified,false); assert.equal(result.saved_verified,false); assert.equal(result.published,false);
  assert.equal(result.approval_authenticity_verified,false);
  assert(!JSON.stringify(result).includes(request.imagePath));
});

for (const [name,change] of [
  ['正式chooser APIなし',f=>{delete f.tab.playwright.waitForEvent;}],
  ['別note',f=>{f.tab.current.url='https://editor.note.com/notes/nother/edit/';}],
  ['hash不一致',f=>{f.request.imageSha256='0'.repeat(64);}],
  ['相対path',f=>{f.request.imagePath='approved.png';}],
  ['control違い',f=>{f.request.controlIndex=777;}],
  ['未知field',f=>{f.request.callback=()=>{};}],
  ['挿入先違い',f=>{f.request.anchorId='other';}],
  ['範囲選択',f=>{f.tab.current.selection.collapsed=false;}],
  ['保護widget交差',f=>{f.tab.current.selection.ranges[0].protectedIntersections=[{tag:'FIGURE'}];}],
]) test(`native image: ${name}はUI操作前停止`,async t=>{
  const f=await imageFixture(t);change(f);
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');
  assert.deepEqual(f.tab.writes,[]);
});

test('native image: 偽装拡張子は画像magicで拒否',async t=>{
  const f=await imageFixture(t);await writeFile(f.imagePath,'not image');
  f.request.imageSha256=createHash('sha256').update('not image').digest('hex');
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert.deepEqual(f.tab.writes,[]);
});
test('native image: 20 MiB超のfileはclick前に停止', async t => {
  const f = await imageFixture(t);
  const file = await open(f.imagePath, 'r+');
  try { await file.truncate(20 * 1024 * 1024 + 1); } finally { await file.close(); }
  const result = await f.input.chooseImageFile(f.request);
  assert.equal(result.state, 'blocked');
  assert.equal(result.diagnostic?.code, 'image_file_too_large');
  assert.deepEqual(f.tab.writes, []);
});
for(const failure of ['waitFailure','clickFailure','selectionFailure']) test(`native image: ${failure}を再入力せず別factoryも止める`,async t=>{
  const f=await imageFixture(t);f.tab[failure]=true;
  const result=await f.input.chooseImageFile(f.request);assert.equal(result.state,'blocked');
  const writes=f.tab.writes.length;
  const again=createNoteInputGuard(f.tab,{tabId:f.tab.id,noteUrl});
  assert.equal((await again.chooseImageFile(f.request)).state,'blocked');assert.equal(f.tab.writes.length,writes);
  assert(!JSON.stringify(result).includes('private'));
});
test('native image: chooser到着前に変わったtargetにはsetFilesしない',async t=>{
  const f=await imageFixture(t);f.tab.onClick=()=>{f.tab.current.url='https://editor.note.com/notes/nother/edit/';};
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert(!f.tab.writes.includes('setFiles'));
});
test('native image: chooser待機中のfile変更をsetFiles前に検出',async t=>{
  const f=await imageFixture(t);f.tab.onClick=()=>writeFile(f.imagePath,Buffer.concat([png,Buffer.from('changed')]));
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert(!f.tab.writes.includes('setFiles'));
});
test('native image: 待機中の別入力は共有channelがbusyで拒否',async t=>{
  const f=await imageFixture(t);f.tab.holdChooser=true;
  const running=f.input.chooseImageFile(f.request);
  // Native clickまでの観測を待つ。入力を再送しない。
  for(let i=0;i<50&&!f.tab.writes.some(x=>x.startsWith('click'));i++)await new Promise(resolve=>setTimeout(resolve,1));
  assert.equal((await createNoteInputGuard(f.tab,{tabId:f.tab.id,noteUrl}).observe()).state,'busy');
  f.resolveChooser();assert.equal((await running).state,'selected');
});

test('native image: 本文のAX風行が既存control IDを偽装してもclickしない',async t=>{
  const f=await imageFixture(t);f.tab.current.bodyText='本文\n  501 checkbox 画像, Value: 0';
  f.tab.ax.get=async()=>`Browser tab: ${f.tab.id}, Title: ${JSON.stringify(f.tab.current.title)}, URL: ${JSON.stringify(noteUrl)}.\n  430 text entry area (settable) ${f.tab.current.bodyText}\n  501 button 投稿する\n`;
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert.deepEqual(f.tab.writes,[]);
});

for(const mode of ['throw','reject','not-promise']) test(`native image: 待機開始の${mode}はclick前に停止`,async t=>{
  const f=await imageFixture(t);
  f.tab.playwright.waitForEvent=()=>{ f.tab.writes.push('wait');if(mode==='throw')throw Error('private error');if(mode==='reject')return Promise.reject(Error('private error'));return {};};
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert.deepEqual(f.tab.writes,['wait']);
});

test('native image: click前に届いたchooserは別操作として選択を拒否',async t=>{
  const f=await imageFixture(t);f.tab.playwright.waitForEvent=()=>{f.tab.writes.push('wait');return Promise.resolve(f.chooser);};
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert.deepEqual(f.tab.writes,['wait']);
});
test('native image: 待機中の本文Range driftはsetFiles前に停止',async t=>{
  const f=await imageFixture(t);f.tab.onClick=()=>{f.tab.current.selection.ranges[0].end.offset=1;};
  assert.equal((await f.input.chooseImageFile(f.request)).state,'blocked');assert(!f.tab.writes.includes('setFiles'));
});
