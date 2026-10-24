import { createHash } from 'node:crypto';

// CUAのread-only evaluateに渡す。closure、DOMParser、ページ内部stateを使わない。
export function readNoteDom() {
  const roots = [...document.querySelectorAll('.ProseMirror[contenteditable="true"]')];
  if (roots.length !== 1) return { rootCount: roots.length };
  const root = roots[0];
  function attrs(node) {
    return [...node.attributes].filter(a => {
      // iframeの表示寸法だけ除外。本文class、caption、TOCの内容と順序は保持する。
      if (node.tagName === 'IFRAME' && ['width', 'height'].includes(a.name)) return false;
      return true;
    }).map(a => [a.name, a.value]).sort((a, b) => a[0].localeCompare(b[0]));
  }
  function tree(node) {
    if (node.nodeType === 3) return { tag: '#text', text: node.textContent };
    if (node.nodeType !== 1) return { tag: `#${node.nodeType}`, text: node.textContent };
    return { tag: node.tagName, attrs: attrs(node), children: [...node.childNodes].map(tree) };
  }
  const selection = window.getSelection();
  const anchor = selection?.anchorNode;
  let block = anchor?.nodeType === 1 ? anchor : anchor?.parentElement;
  while (block && block.parentElement !== root) block = block.parentElement;
  const inside = !!anchor && root.contains(anchor) && !!selection?.focusNode && root.contains(selection.focusNode);
  const emptyPosition = !!block && (anchor === block || (anchor?.nodeType === 3 && anchor.textContent === '' && anchor.parentElement === block));
  return {
    url: window.location.href, title: document.title, rootCount: 1,
    rootAttrs: attrs(root), blocks: [...root.childNodes].map(tree),
    rawHtml: root.innerHTML, bodyText: root.textContent,
    focused: document.hasFocus() && (document.activeElement === root || root.contains(document.activeElement)),
    visible: root.getClientRects().length > 0,
    selection: {
      collapsed: selection?.isCollapsed === true, rangeCount: selection?.rangeCount,
      blockIndex: [...root.childNodes].indexOf(block), inside, emptyPosition,
      sameNode: anchor === selection?.focusNode,
      anchorOffset: selection?.anchorOffset, focusOffset: selection?.focusOffset,
    },
  };
}

const digest = value => createHash('sha256').update(value, 'utf8').digest('hex');
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const semantic = s => JSON.stringify([s.rootAttrs, s.blocks]);
const empty = block => block?.tag === 'P' && attr(block, 'contenteditable') !== 'false'
  && block.children.filter(n => n.tag === 'BR').length <= 1 && block.children.every(n =>
    (n.tag === '#text' && n.text === '') || (n.tag === 'BR' && n.children.length === 0));
const textOf = node => node.tag === '#text' ? node.text : (node.children ?? []).map(textOf).join('');
const attr = (node, name) => node.attrs?.find(a => a[0] === name)?.[1];
const descendants = node => [node, ...(node.children ?? []).flatMap(descendants)];
const channels = new Map(); // 同一module・tabでpending/blockedを別factoryからも再入力できない。

function validNoteUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && ['editor.note.com', 'note.com'].includes(u.hostname)
      && /^\/notes\/n[a-z0-9]+\/edit\/?$/.test(u.pathname)
      && !u.username && !u.password && !u.port && !u.search && !u.hash;
  } catch { return false; }
}
function validPayload(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\s\u0000-\u001f\u007f<>]/u.test(value)) return false;
  try { const u = new URL(value); return u.protocol === 'https:' && !!u.hostname && !u.username && !u.password; }
  catch { return false; }
}

/** 承認は信頼済みcallerの責務。booleanやreceiptは承認の真正性証明ではない。 */
export function createNoteInputGuard(tab, { tabId, noteUrl }) {
  if (typeof tabId !== 'string' || !tabId || !validNoteUrl(noteUrl)) throw new Error('invalid_target_lock');
  const lock = { tabId, noteUrl }; // callerのoptions変更を参照しない。
  let channel = channels.get(tabId);
  if (!channel) { channel = { state: 'idle', pending: null, checkpoints: new WeakMap() }; channels.set(tabId, channel); }
  function receipt(state, reason, before, after, payload) {
    return Object.freeze({
      schema: 'note-editor-guarded-input/v1', state, reason,
      before_sha256: before ? digest(before.rawHtml) : null,
      after_sha256: after ? digest(after.rawHtml) : null,
      payload_sha256: payload ? digest(payload) : null,
      protected_sha256: before ? digest(semantic(before)) : null,
      approval_authenticity_verified: false, runtime_enforcement_verified: false,
    });
  }
  function block(reason, before, after, payload) {
    channel.state = 'blocked'; channel.pending = null;
    return receipt('blocked', reason, before, after, payload);
  }
  async function read() {
    if (tab.id !== lock.tabId) throw new Error('target_changed');
    const apiUrl = await tab.url();
    const s = await tab.playwright.evaluate(readNoteDom);
    if (tab.id !== lock.tabId || apiUrl !== lock.noteUrl || s.url !== lock.noteUrl || s.rootCount !== 1
      || !Array.isArray(s.blocks) || !Array.isArray(s.rootAttrs) || typeof s.rawHtml !== 'string'
      || typeof s.bodyText !== 'string' || typeof s.title !== 'string') throw new Error('unknown_target');
    return s;
  }
  function position(s) {
    const q = s.selection;
    return s.focused === true && s.visible === true && q?.collapsed === true && q.rangeCount === 1
      && q.inside === true && q.emptyPosition === true && q.sameNode === true
      && q.anchorOffset === 0 && q.focusOffset === 0 && Number.isInteger(q.blockIndex)
      && q.blockIndex >= 0 && empty(s.blocks[q.blockIndex]);
  }
  function compare(before, after, index, payload) {
    if (before.url !== after.url || before.title !== after.title || !equal(before.rootAttrs, after.rootAttrs)) return 'blocked';
    const prefix = before.blocks.slice(0, index);
    const suffix = before.blocks.slice(index + 1);
    if (!equal(prefix, after.blocks.slice(0, index))) return 'blocked';
    let afterSuffix = after.blocks.slice(index + 1);
    // カード直後に生成された空Pを1件だけ許す。既存空Pの欠落・移動は隠さない。
    if (after.blocks[index]?.tag === 'FIGURE' && afterSuffix.length === suffix.length + 1 && empty(afterSuffix[0])) afterSuffix = afterSuffix.slice(1);
    if (!equal(suffix, afterSuffix)) return 'blocked';
    const target = after.blocks[index];
    if (equal(target, before.blocks[index])) return 'pending';
    if (target?.tag === 'P' && textOf(target) === payload) {
      const nodes = descendants(target);
      if (nodes.every(n => ['P', 'A', '#text'].includes(n.tag))
        && nodes.filter(n => n.tag === 'A').every(n => attr(n, 'href') === payload)) return 'pending';
    }
    if (target?.tag !== 'FIGURE' || attr(target, 'data-src') !== payload) return 'blocked';
    const newText = textOf(target);
    if (newText.length > 2048) return 'blocked';
    const newNodes = descendants(target);
    if (newNodes.filter(n => n.tag === 'FIGURE').length !== 1) return 'blocked';
    const newLinks = new Set(newNodes.flatMap(n => [attr(n, 'href'), attr(n, 'data-src')]).filter(Boolean));
    for (const old of before.blocks.filter((_, i) => i !== index)) {
      const oldText = textOf(old);
      // 短文の結合複製も止める。短い一般語の一致はfalse positiveになり得るが安全側に停止。
      if (oldText.trim() && newText.includes(oldText)) return 'blocked';
      if (descendants(old).some(n => [attr(n, 'href'), attr(n, 'data-src')].some(url => url && newLinks.has(url)))) return 'blocked';
    }
    return 'completed';
  }
  async function finish(before, index, payload) {
    const after = await read();
    const state = compare(before, after, index, payload);
    if (state === 'blocked') return block('unexpected_document_change', before, after, payload);
    channel.state = state === 'completed' ? 'idle' : 'pending';
    channel.pending = state === 'pending' ? { before, index, payload, lock } : null;
    return receipt(state, state === 'completed' ? 'single_card_verified' : 'read_only_reconcile_required', before, after, payload);
  }
  return Object.freeze({
    async observe() {
      if (channel.state !== 'idle') return receipt(channel.state, 'input_stopped');
      channel.state = 'busy';
      try {
        const before = await read();
        if (!position(before)) return block('invalid_empty_paragraph_selection');
        const checkpoint = receipt('observed', 'checkpoint_only', before);
        channel.checkpoints.set(checkpoint, { before, lock });
        channel.state = 'idle';
        return checkpoint;
      } catch { return block('observation_failed'); }
    },
    async pasteUrl({ checkpoint, payload } = {}) {
      if (channel.state !== 'idle') return receipt(channel.state, 'input_stopped');
      channel.state = 'busy';
      const saved = checkpoint && channel.checkpoints.get(checkpoint);
      if (!saved || !equal(saved.lock, lock) || !validPayload(payload)) return block('invalid_request');
      channel.checkpoints.delete(checkpoint);
      let before;
      let mutationStarted = false;
      try {
        before = await read();
        if (!position(before) || !equal(saved.before.selection, before.selection)
          || saved.before.title !== before.title || semantic(saved.before) !== semantic(before)) return block('stale_checkpoint', before);
        const index = before.selection.blockIndex;
        mutationStarted = true;
        await tab.paste(null, payload, { format: 'text' }); // 唯一のmutation。Home/Enter/任意callbackなし。
        await tab.getAXState({ emit: false });
        return await finish(before, index, payload);
      } catch { return block(mutationStarted ? 'write_outcome_unknown' : 'precheck_failed', before, null, payload); }
    },
    async reconcile() {
      if (channel.state !== 'pending' || !channel.pending) return receipt(channel.state, 'no_pending_write');
      if (!equal(channel.pending.lock, lock)) return block('pending_target_changed');
      const { before, index, payload } = channel.pending;
      channel.state = 'busy';
      try { return await finish(before, index, payload); }
      catch { return block('reconcile_failed', before, null, payload); }
    },
  });
}
