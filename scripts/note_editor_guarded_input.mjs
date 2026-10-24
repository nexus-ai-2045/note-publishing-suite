import { createHash } from 'node:crypto';

// CUAのread-only evaluateに渡す。closure、DOMParser、ページ内部stateを使わない。
export function readNoteDom() {
  const roots = [...document.querySelectorAll('.ProseMirror[contenteditable="true"]')];
  if (roots.length !== 1) return { rootCount: roots.length };
  const root = roots[0];
  function attrs(node) {
    return [...node.attributes].flatMap(a => {
      // 表示寸法と編集カーソル用マーカーだけを除外。本文styleや他のclassは保持する。
      if (node.tagName === 'IFRAME' && ['width', 'height'].includes(a.name)) return [];
      if (a.name === 'class') {
        const transient = node === root ? ['ProseMirror-focused', 'ProseMirror-hideselection']
          : node.tagName === 'P' && node.parentElement === root ? ['paragraph'] : [];
        const value = a.value.split(/\s+/).filter(name => name && !transient.includes(name)).join(' ');
        return value ? [[a.name, value]] : [];
      }
      return [[a.name, a.value]];
    }).sort((a, b) => a[0].localeCompare(b[0]));
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
  function endpoint(node, offset) {
    let owner = node?.nodeType === 1 ? node : node?.parentElement;
    while (owner && owner.parentElement !== root) owner = owner.parentElement;
    const nodePath = [];
    let current = node;
    while (current && current !== owner) {
      const parent = current.parentElement;
      if (!parent) return null;
      nodePath.unshift([...parent.childNodes].indexOf(current));
      current = parent;
    }
    return owner && root.contains(node) ? { blockIndex: [...root.childNodes].indexOf(owner), nodePath, offset } : null;
  }
  const ranges = [];
  let intersectionsKnown = selection?.rangeCount === 1 && typeof selection.getRangeAt === 'function';
  if (intersectionsKnown) {
    try {
      const range = selection.getRangeAt(0);
      const protectedNodes = [];
      function visit(node) {
        if (node.nodeType !== 1) return;
        if (['FIGURE', 'TABLE-OF-CONTENTS'].includes(node.tagName)
          || [...node.attributes].some(a => a.name === 'contenteditable' && a.value === 'false')) protectedNodes.push(node);
        for (const child of node.childNodes) visit(child);
      }
      visit(root);
      ranges.push({ start: endpoint(range.startContainer, range.startOffset),
        end: endpoint(range.endContainer, range.endOffset),
        protectedIntersections: protectedNodes.flatMap(node => range.intersectsNode(node) ? [endpoint(node, 0)] : []) });
    } catch { intersectionsKnown = false; }
  }
  let view = null;
  try {
    let scroller = root;
    const overflows = node => Number.isFinite(node.scrollHeight) && Number.isFinite(node.clientHeight)
      && node.clientHeight > 0 && node.scrollHeight > node.clientHeight;
    while (scroller && !(overflows(scroller)
      && ['auto', 'scroll', 'overlay'].includes(window.getComputedStyle(scroller).overflowY))) scroller = scroller.parentElement;
    scroller ??= document.scrollingElement;
    const documentScroll = scroller === document.scrollingElement;
    const rect = root.getBoundingClientRect();
    const bounds = documentScroll ? { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight } : scroller.getBoundingClientRect();
    const left = Math.max(0, rect.left, bounds.left), right = Math.min(window.innerWidth, rect.right, bounds.right);
    const top = Math.max(0, rect.top, bounds.top), bottom = Math.min(window.innerHeight, rect.bottom, bounds.bottom);
    const point = right > left && bottom > top ? [(left + right) / 2, (top + bottom) / 2] : null;
    // Zero document range is not proof that the body is visible: an inner
    // clipping container can hide its tail while its centre still hit-tests.
    let unclipped = true;
    if (documentScroll && scroller.scrollHeight === scroller.clientHeight) {
      for (let node = root; node && node !== scroller; node = node.parentElement) {
        const style = window.getComputedStyle(node);
        if (style.overflowX !== 'visible' || style.overflowY !== 'visible') { unclipped = false; break; }
      }
    }
    const wholeBodyVisible = ['left', 'right', 'top', 'bottom'].every(k => Number.isFinite(rect[k]))
      && rect.left >= 0 && rect.top >= 0 && rect.right <= window.innerWidth && rect.bottom <= window.innerHeight
      && rect.right > rect.left && rect.bottom > rect.top && unclipped && point && root.contains(document.elementFromPoint(...point));
    const path = [];
    for (let node = scroller; node?.parentElement; node = node.parentElement) path.unshift([...node.parentElement.childNodes].indexOf(node));
    view = documentScroll && scroller.scrollHeight === scroller.clientHeight && !wholeBodyVisible ? null : { width: window.innerWidth, height: window.innerHeight,
      scrollTop: scroller.scrollTop, scrollHeight: scroller.scrollHeight, clientHeight: scroller.clientHeight,
      scroller: JSON.stringify([documentScroll, scroller.tagName, path]),
      point: point && root.contains(document.elementFromPoint(...point)) ? point : null };
  } catch { /* viewport capability unavailable: paste remains usable; scroll fails closed. */ }
  return {
    url: window.location.href, title: document.title, rootCount: 1,
    // 深いカードDOMをhostの再帰上限で欠落させない。文字列を読戻して復元する。
    rootAttrs: attrs(root), blocksJson: JSON.stringify([...root.childNodes].map(tree)),
    rawHtml: root.innerHTML, bodyText: root.textContent,
    documentFocusKnown: typeof document.hasFocus === 'function',
    focused: typeof document.hasFocus === 'function'
      ? document.hasFocus() && (document.activeElement === root || root.contains(document.activeElement)) : null,
    activeElementIsRoot: document.activeElement === root,
    visible: root.getClientRects().length > 0, view,
    selection: {
      ranges, intersectionsKnown,
      collapsed: selection?.isCollapsed === true, rangeCount: selection?.rangeCount,
      blockIndex: [...root.childNodes].indexOf(block), inside, emptyPosition,
      sameNode: anchor === selection?.focusNode,
      anchorOffset: selection?.anchorOffset, focusOffset: selection?.focusOffset,
    },
  };
}

// 文字一致では選択範囲を証明できない。Range両端と保護widget交差を必須にする。
export function selectionWithinBlock(snapshot, index) {
  const q = snapshot?.selection;
  const range = q?.ranges?.[0];
  return Number.isInteger(index) && index >= 0 && q?.rangeCount === 1
    && q.intersectionsKnown === true && Array.isArray(q.ranges) && q.ranges.length === 1
    && Array.isArray(range?.protectedIntersections) && range.protectedIntersections.length === 0
    && [range.start, range.end].every(point => point?.blockIndex === index
      && Array.isArray(point.nodePath) && point.nodePath.every(n => Number.isInteger(n) && n >= 0)
      && Number.isInteger(point.offset) && point.offset >= 0);
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
const loading = node => {
  if (node?.tag !== 'P' || textOf(node) !== '' || node.children.length !== 3) return false;
  const [widget, separator, trailing] = node.children;
  return widget.tag === 'DIV' && equal(widget.attrs, [['class', 'placeholder ProseMirror-widget'], ['contenteditable', 'false']])
    && widget.children.length === 3 && widget.children.every(n => n.tag === 'DIV' && !n.attrs.length && !n.children.length)
    && separator.tag === 'IMG' && equal(separator.attrs, [['alt', ''], ['class', 'ProseMirror-separator']]) && !separator.children.length
    && trailing.tag === 'BR' && equal(trailing.attrs, [['class', 'ProseMirror-trailingBreak']]) && !trailing.children.length;
};
const channels = new Map(); // 同一module・tabでpending/blockedを別factoryからも再入力できない。
const MAX_RECONCILE_ATTEMPTS = 6;

// 例外のmessage/stackは記事やURLを含み得るためreceiptへ渡さない。
class ObservationError extends Error {
  constructor(code, phase, recoverable = false) {
    super(code);
    this.diagnostic = { code, phase, recoverable };
  }
}
const diagnosticOf = (error, phase) => error instanceof ObservationError
  ? error.diagnostic : { code: 'operation_unavailable', phase, recoverable: true };

function validNoteUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && ['editor.note.com', 'note.com'].includes(u.hostname)
      && /^\/notes\/n[a-z0-9]+\/edit\/?$/.test(u.pathname)
      && !u.username && !u.password && !u.port && !u.search && !u.hash;
  } catch { return false; }
}
function validParagraphs(value) {
  return Array.isArray(value) && value.length > 0 && value.length <= 100
    && value.every(p => typeof p === 'string' && p.trim().length > 0
      && !/[\r\u0000-\u0008\u000b-\u001f\u007f]/u.test(p))
    && value.join('').length <= 100000;
}
const paragraphHtml = paragraphs => paragraphs.map(p => '<p>' + p.replace(/&/g, '&amp;')
  .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;').replace(/\n/g, '<br>') + '</p>').join('');
function validPayload(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\s\u0000-\u001f\u007f<>]/u.test(value)) return false;
  try { const u = new URL(value); return u.protocol === 'https:' && !!u.hostname && !u.username && !u.password; }
  catch { return false; }
}

// Native AX is tab-bound. Only its documented full state may replace an unavailable
// document.hasFocus; a false DOM focus result is never overridden.
function nativeRootFocus(state, lock, snapshot) {
  if (typeof state !== 'string' || snapshot.activeElementIsRoot !== true
    || snapshot.focused === false || snapshot.documentFocusKnown === true && snapshot.focused !== true) return null;
  const header = state.match(/^Browser tab: ([^,\r\n]+), Title: ("(?:\\.|[^"\\])*"), URL: ("(?:\\.|[^"\\])*")\./);
  if (!header || header[1].trim() !== lock.tabId
    || JSON.parse(header[2]) !== snapshot.title || JSON.parse(header[3]) !== lock.noteUrl) return null;
  const focused = [...state.matchAll(/^The focused UI element is (\d+) text entry area \(settable\) ([\s\S]*)$/gm)];
  if (focused.length !== 1) return null;
  const id = focused[0][1];
  const rows = [...state.matchAll(new RegExp(`^[ \t]*${id} text entry area \\(settable\\) ([^\\r\\n]*)`, 'gm'))];
  const normalize = value => value.replace(/\s/gu, '');
  if (rows.length !== 1 || !normalize(snapshot.bodyText)
    || normalize(focused[0][2]) !== normalize(snapshot.bodyText)) return null;
  // Bind the focused ID to the body row, not merely to any editable title field.
  const rowValueStart = rows[0].index + rows[0][0].length - rows[0][1].length;
  let rowValue = state.slice(rowValueStart, focused[0].index);
  const nextRow = rowValue.match(/^[ \t]*\d+ [a-z][^\r\n]*/m);
  if (nextRow) rowValue = rowValue.slice(0, nextRow.index);
  if (normalize(rowValue) !== normalize(snapshot.bodyText)) return null;
  return id;
}

/** 承認は信頼済みcallerの責務。booleanやreceiptは承認の真正性証明ではない。 */
export function createNoteInputGuard(tab, { tabId, noteUrl }) {
  if (typeof tabId !== 'string' || !tabId || !validNoteUrl(noteUrl)) throw new Error('invalid_target_lock');
  const nativeAx = typeof tab.ax?.get === 'function' && typeof tab.ax?.paste === 'function';
  const lock = { tabId, noteUrl }; // callerのoptions変更を参照しない。
  let channel = channels.get(tabId);
  if (!channel) { channel = { state: 'idle', pending: null, checkpoints: new WeakMap() }; channels.set(tabId, channel); }
  function receipt(state, reason, before, after, payload, diagnostic = null) {
    return Object.freeze({
      schema: 'note-editor-guarded-input/v1', state, reason,
      diagnostic, reconcile_attempt: channel.pending?.attempts ?? 0,
      max_reconcile_attempts: MAX_RECONCILE_ATTEMPTS,
      before_sha256: before ? digest(before.rawHtml) : null,
      after_sha256: after ? digest(after.rawHtml) : null,
      payload_sha256: payload ? digest(payload) : null,
      protected_sha256: before ? digest(semantic(before)) : null,
      approval_authenticity_verified: false, runtime_enforcement_verified: false,
    });
  }
  function block(reason, before, after, payload, diagnostic = null) {
    channel.state = 'blocked';
    const result = receipt('blocked', reason, before, after, payload, diagnostic);
    channel.pending = null;
    return result;
  }
  function pending(before, index, payload, reason, diagnostic = null, paragraphs = null) {
    const attempts = channel.pending?.attempts ?? 0;
    channel.pending = { before, index, payload, lock, attempts, paragraphs };
    if (attempts >= MAX_RECONCILE_ATTEMPTS) return block('reconcile_limit_reached', before, null, payload, diagnostic);
    channel.state = 'pending';
    return receipt('pending', reason, before, null, payload, diagnostic);
  }
  async function read(requireInputFocus = true) {
    async function dom() {
      if (tab.id !== lock.tabId) throw new ObservationError('target_tab_changed', 'target');
      let apiUrl;
      try { apiUrl = await tab.url(); }
      catch { throw new ObservationError('target_url_unavailable', 'target_url', true); }
      if (apiUrl !== lock.noteUrl) throw new ObservationError('target_url_changed', 'target');
      let s;
      try { s = await tab.playwright.evaluate(readNoteDom); }
      catch { throw new ObservationError('dom_read_unavailable', 'dom_read', true); }
      if (tab.id !== lock.tabId) throw new ObservationError('target_tab_changed', 'target');
      if (!s || typeof s !== 'object') throw new ObservationError('dom_snapshot_incomplete', 'dom_read', true);
      if (typeof s.blocksJson === 'string') {
        try { s.blocks = JSON.parse(s.blocksJson); }
        catch { throw new ObservationError('dom_tree_unreadable', 'dom_read', true); }
      }
      function validTree(node) {
        return !!node && typeof node === 'object' && typeof node.tag === 'string'
          && ((node.tag === '#text' || /^#[0-9]+$/.test(node.tag)) ? typeof node.text === 'string'
            : Array.isArray(node.attrs) && Array.isArray(node.children) && node.children.every(validTree));
      }
      if (Array.isArray(s.blocks) && !s.blocks.every(validTree)) {
        throw new ObservationError('dom_tree_truncated', 'dom_read', true);
      }
      // rootが無い読込み途中と、別note/複数rootの確定差分を分ける。
      if (s.rootCount === 0) throw new ObservationError('editor_root_loading', 'dom_read', true);
      if (s.url !== lock.noteUrl) throw new ObservationError('target_url_changed', 'target');
      if (s.rootCount !== 1) throw new ObservationError('editor_root_ambiguous', 'target');
      if (!Array.isArray(s.blocks) || !Array.isArray(s.rootAttrs) || typeof s.rawHtml !== 'string'
        || typeof s.bodyText !== 'string' || typeof s.title !== 'string') {
        throw new ObservationError('dom_snapshot_incomplete', 'dom_read', true);
      }
      return s;
    }
    const first = await dom();
    if (!nativeAx) return first;
    async function ax() {
      try { return await tab.ax.get('state', { disableDiffing: true }); }
      catch { throw new ObservationError('native_ax_unavailable', 'native_ax', true); }
    }
    // 入力後はカード変換が選択と焦点を動かす。再入力しない読取りにAX焦点を要求しない。
    const firstFocus = requireInputFocus ? nativeRootFocus(await ax(), lock, first) : null;
    const second = await dom();
    const secondFocus = requireInputFocus ? nativeRootFocus(await ax(), lock, second) : null;
    if (tab.id !== lock.tabId) throw new ObservationError('target_tab_changed', 'target');
    let finalUrl;
    try { finalUrl = await tab.url(); }
    catch { throw new ObservationError('target_url_unavailable', 'target_url', true); }
    if (finalUrl !== lock.noteUrl) throw new ObservationError('target_url_changed', 'target');
    if (first.title !== second.title) throw new ObservationError('target_title_changed', 'target');
    if (semantic(first) !== semantic(second)) throw new ObservationError('document_unstable', 'stable_read', true);
    if (requireInputFocus && (!firstFocus || firstFocus !== secondFocus || !equal(first.selection, second.selection))) {
      throw new ObservationError('native_focus_unverified', 'input_focus');
    }
    return requireInputFocus ? { ...second, focused: true } : second;
  }
  function position(s) {
    const q = s.selection;
    return s.focused === true && s.visible === true && q?.collapsed === true && q.rangeCount === 1
      && q.inside === true && q.emptyPosition === true && q.sameNode === true
      && q.anchorOffset === 0 && q.focusOffset === 0 && Number.isInteger(q.blockIndex)
      && q.blockIndex >= 0 && empty(s.blocks[q.blockIndex]) && selectionWithinBlock(s, q.blockIndex)
      && q.ranges[0].start.offset === 0 && q.ranges[0].end.offset === 0
      && equal(q.ranges[0].start, q.ranges[0].end);
  }
  function compare(before, after, index, payload) {
    if (before.url !== after.url || before.title !== after.title || !equal(before.rootAttrs, after.rootAttrs)) return 'blocked';
    const prefix = before.blocks.slice(0, index);
    const suffix = before.blocks.slice(index + 1);
    if (!equal(prefix, after.blocks.slice(0, index))) return 'blocked';
    let afterSuffix = after.blocks.slice(index + 1);
    // カード直後に生成された空Pを1件だけ許す。既存空Pの欠落・移動は隠さない。
    if ((after.blocks[index]?.tag === 'FIGURE' || loading(after.blocks[index]))
      && afterSuffix.length === suffix.length + 1 && empty(afterSuffix[0])) afterSuffix = afterSuffix.slice(1);
    if (!equal(suffix, afterSuffix)) return 'blocked';
    const target = after.blocks[index];
    if (equal(target, before.blocks[index])) return 'pending';
    // URL未確定の読込み表示は成功にせず、再入力禁止のpendingで実カードを待つ。
    if (loading(target) && equal(target.attrs, before.blocks[index].attrs)) return 'pending';
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
  function compareParagraphs(before, after, index, paragraphs) {
    if (before.url !== after.url || before.title !== after.title || !equal(before.rootAttrs, after.rootAttrs)) return 'blocked';
    if (semantic(before) === semantic(after)) return 'pending';
    if (!equal(before.blocks.slice(0, index), after.blocks.slice(0, index))
      || !equal(before.blocks.slice(index + 1), after.blocks.slice(index + paragraphs.length))) return 'blocked';
    const inserted = after.blocks.slice(index, index + paragraphs.length);
    return inserted.length === paragraphs.length && inserted.every((node, i) => {
      if (node.tag !== 'P' || !equal(node.attrs, before.blocks[index].attrs)
        || node.children.some(n => n.tag !== '#text' && !(n.tag === 'BR' && !n.children.length
          && (!n.attrs.length || equal(n.attrs, [['class', 'ProseMirror-trailingBreak']]))))) return false;
      const children = [...node.children];
      // ProseMirror末尾マーカーはsoft breakに数えない。
      if (attr(children.at(-1) ?? {}, 'class') === 'ProseMirror-trailingBreak') children.pop();
      const observed = children.map(n => n.tag === 'BR' ? '\n' : n.text).join('');
      return observed === paragraphs[i] && children.filter(n => n.tag === 'BR').length === paragraphs[i].split('\n').length - 1;
    }) ? 'completed' : 'blocked';
  }
  async function finish(before, index, payload, paragraphs = null) {
    // Card conversion may move focus; post-write verification still binds the
    // same tab, URL, root and stable document, then checks every protected block.
    const after = await read(false);
    const state = paragraphs ? compareParagraphs(before, after, index, paragraphs) : compare(before, after, index, payload);
    if (state === 'blocked') return block('unexpected_document_change', before, after, payload,
      { code: before.title !== after.title ? 'target_title_changed' : 'protected_document_changed', phase: 'card_compare', recoverable: false });
    if (state === 'pending') return pending(before, index, payload, 'read_only_reconcile_required',
      { code: loading(after.blocks[index]) ? 'card_loading' : 'card_not_resolved', phase: 'card_compare', recoverable: true }, paragraphs);
    channel.state = 'idle';
    const result = receipt('completed', paragraphs ? 'paragraphs_verified' : 'single_card_verified', before, after, payload);
    channel.pending = null;
    return result;
  }
  async function paste(request, kind) {
    if (channel.state !== 'idle') return receipt(channel.state, 'input_stopped');
    channel.state = 'busy';
    const allowed = kind === 'paragraphs' ? ['checkpoint', 'paragraphs'] : ['checkpoint', 'payload'];
    if (!request || typeof request !== 'object' || Array.isArray(request)
      || Reflect.ownKeys(request).some(key => !allowed.includes(key))) return block('invalid_request');
    let { checkpoint, payload, paragraphs = null } = request;
    const saved = checkpoint && channel.checkpoints.get(checkpoint);
    if (!saved || !equal(saved.lock, lock) || !(kind === 'paragraphs' ? validParagraphs(paragraphs) : validPayload(payload))) return block('invalid_request');
    channel.checkpoints.delete(checkpoint);
    if (kind === 'paragraphs') { paragraphs = [...paragraphs]; payload = paragraphHtml(paragraphs); }
    let before;
    let mutationStarted = false;
    try {
      before = await read();
      if (!position(before) || !equal(saved.before.selection, before.selection)
        || saved.before.title !== before.title || semantic(saved.before) !== semantic(before)) return block('stale_checkpoint', before);
      const index = before.selection.blockIndex;
      mutationStarted = true;
      // Exactly one target-bound paste; no DOM write, global focus or arbitrary callback.
      if (nativeAx) await tab.ax.paste(null, payload, { format: paragraphs ? 'html' : 'text' });
      else await tab.paste(null, payload, { format: paragraphs ? 'html' : 'text' });
      if (!nativeAx) await tab.getAXState({ emit: false });
      return await finish(before, index, payload, paragraphs);
    } catch (error) {
      const diagnostic = diagnosticOf(error, mutationStarted ? 'paste_or_verify' : 'precheck');
      if (!mutationStarted) return block('precheck_failed', before, null, payload, diagnostic);
      if (!diagnostic.recoverable) return block(diagnostic.code, before, null, payload, diagnostic);
      // 入力の結果が不明でもbeforeを捨てない。再入力は禁止し、読取りでのみ解消する。
      return pending(before, before.selection.blockIndex, payload, 'write_outcome_unknown_read_only', diagnostic, paragraphs);
    }
  }
  async function scrollToEdge(request = {}) {
    if (channel.state !== 'idle') return receipt(channel.state, 'input_stopped');
    channel.state = 'busy';
    const { edge, maxSteps = 8, timeoutMs = 10000 } = request ?? {};
    if (!request || typeof request !== 'object' || Array.isArray(request)
      || Reflect.ownKeys(request).some(key => !['edge', 'maxSteps', 'timeoutMs'].includes(key))
      || !['top', 'bottom'].includes(edge) || !Number.isInteger(maxSteps) || maxSteps < 1 || maxSteps > 20
      || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 60000) return block('invalid_scroll_request');
    const validView = s => {
      const v = s.view, q = s.selection;
      const endpointKnown = point => point && Number.isInteger(point.blockIndex) && point.blockIndex >= 0
        && Array.isArray(point.nodePath) && point.nodePath.every(n => Number.isInteger(n) && n >= 0)
        && Number.isInteger(point.offset) && point.offset >= 0;
      return v && ['width', 'height', 'scrollHeight', 'clientHeight'].every(k => Number.isFinite(v[k]) && v[k] > 0)
        && Number.isFinite(v.scrollTop) && v.scrollTop >= 0 && v.scrollHeight >= v.clientHeight
        && v.scrollTop <= v.scrollHeight - v.clientHeight + 1 && typeof v.scroller === 'string' && !!v.scroller
        && Array.isArray(q?.ranges) && (q.rangeCount === 0 && q.ranges.length === 0
          || q.rangeCount === 1 && q.ranges.length === 1 && q.intersectionsKnown === true
            && endpointKnown(q.ranges[0].start) && endpointKnown(q.ranges[0].end)
            && Array.isArray(q.ranges[0].protectedIntersections));
    };
    const atEdge = v => edge === 'top' ? v.scrollTop <= 1 : v.scrollHeight - v.clientHeight - v.scrollTop <= 1;
    const deadline = performance.now() + timeoutMs;
    let before, current;
    try {
      before = current = await read(false);
      if (!validView(current)) return block('scroll_observation_unavailable', before);
      for (let steps = 0; ; steps++) {
        if (atEdge(current.view)) {
          channel.state = 'idle';
          return Object.freeze({ ...receipt('completed', 'scroll_edge_verified', before, current), edge, steps });
        }
        if (steps >= maxSteps || performance.now() >= deadline) return block('scroll_limit_reached', before, current);
        if (typeof tab.ax?.scroll !== 'function') return block('native_scroll_unavailable', before, current);
        const point = current.view.point;
        if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)
          || point[0] <= 0 || point[0] >= current.view.width || point[1] <= 0 || point[1] >= current.view.height) return block('scroll_point_unavailable', before, current);
        // Await the sole native action. Unknown outcome is never automatically resent.
        await tab.ax.scroll(point, edge === 'top' ? 'up' : 'down', 1);
        const after = await read(false);
        if (!validView(after) || semantic(before) !== semantic(after) || before.title !== after.title
          || !equal(before.selection, after.selection) || current.view.scroller !== after.view.scroller
          || current.view.width !== after.view.width || current.view.height !== after.view.height
          || current.view.scrollHeight !== after.view.scrollHeight || current.view.clientHeight !== after.view.clientHeight) return block('scroll_document_changed', before, after);
        if ((after.view.scrollTop - current.view.scrollTop) * (edge === 'top' ? -1 : 1) <= 0) return block('scroll_no_progress', before, after);
        current = after;
      }
    } catch (error) {
      return block('scroll_outcome_unverified', before, current, null, diagnosticOf(error, 'scroll_or_readback'));
    }
  }
  return Object.freeze({
    scrollToEdge,
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
      } catch (error) { return block('observation_failed', null, null, null, diagnosticOf(error, 'observe')); }
    },
    async pasteUrl(request = {}) { return paste(request, 'url'); },
    async pasteParagraphs(request = {}) { return paste(request, 'paragraphs'); },
    async reconcile() {
      if (channel.state !== 'pending' || !channel.pending) return receipt(channel.state, 'no_pending_write');
      if (!equal(channel.pending.lock, lock)) return block('pending_target_changed');
      const { before, index, payload, paragraphs } = channel.pending;
      channel.pending.attempts++;
      channel.state = 'busy';
      try { return await finish(before, index, payload, paragraphs); }
      catch (error) {
        const diagnostic = diagnosticOf(error, 'reconcile');
        if (!diagnostic.recoverable) return block(diagnostic.code, before, null, payload, diagnostic);
        return pending(before, index, payload, 'reconcile_unavailable_read_only', diagnostic, paragraphs);
      }
    },
  });
}
