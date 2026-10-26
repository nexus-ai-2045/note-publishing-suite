import { createHash } from 'node:crypto';

// CUAのread-only evaluateに渡す。closure、DOMParser、ページ内部stateを使わない。
export function readNoteDom() {
  const roots = [...document.querySelectorAll('.ProseMirror[contenteditable="true"]')];
  if (roots.length !== 1) return { rootCount: roots.length };
  const root = roots[0];
  function derivedToc(value) {
    try {
      const records = JSON.parse(value);
      if (!Array.isArray(records) || !records.every(record => record && typeof record === 'object'
        && !Array.isArray(record) && Object.keys(record).sort().join(',') === 'level,node,pos,text'
        && Number.isSafeInteger(record.pos) && record.pos >= 0 && typeof record.text === 'string'
        && Number.isInteger(record.level) && record.level >= 1 && record.level <= 6
        && record.node?.type === 'heading' && record.node.attrs?.level === record.level
        && typeof record.node.attrs.id === 'string' && record.node.attrs.id.length > 0
        && Array.isArray(record.node.content) && record.node.content.every(part => part?.type === 'text' && typeof part.text === 'string')
        && record.node.content.map(part => part.text).join('') === record.text)) return value;
      // pos is the derived editor offset; all heading content, attrs, order and marks remain protected.
      return JSON.stringify(records.map(({ pos, ...record }) => record));
    } catch { return value; }
  }
  function attrs(node) {
    return [...node.attributes].flatMap(a => {
      // 表示寸法と編集カーソル用マーカーだけを除外。本文styleや他のclassは保持する。
      if (node.tagName === 'IFRAME' && ['width', 'height'].includes(a.name)) return [];
      if (node.tagName === 'TABLE-OF-CONTENTS' && a.name === 'toc') return [[a.name, derivedToc(a.value)]];
      if (a.name === 'class') {
        const transient = node === root ? ['ProseMirror-focused', 'ProseMirror-hideselection']
          : node.tagName === 'P' && node.parentElement === root ? ['paragraph']
            : node.tagName === 'UL' && node.parentElement === root ? ['bulletList'] : [];
        const value = a.value.split(/\s+/).filter(name => name && !transient.includes(name)).join(' ');
        return value ? [[a.name, value]] : [];
      }
      return [[a.name, a.value]];
    }).sort((a, b) => a[0].localeCompare(b[0]));
  }
  function twitterPreview(figure) {
    const get = (node, name) => node.attrs.find(a => a[0] === name)?.[1];
    const significant = node => node.children.filter(child => child.tag !== '#text' || child.text.trim());
    const onlyAttrs = (node, names) => node.attrs.every(([name]) => names.includes(name));
    if (get(figure, 'contenteditable') !== 'false' || get(figure, 'embedded-service') !== 'twitter') return null;
    let source;
    try { source = new URL(get(figure, 'data-src')); } catch { return null; }
    const post = source.pathname.match(/^\/[A-Za-z0-9_]+\/status\/(\d+)\/?$/);
    if (source.protocol !== 'https:' || !['x.com', 'twitter.com'].includes(source.hostname)
      || source.username || source.password || source.port || !post) return null;
    const children = significant(figure), span = children[0];
    if (children.length !== 1 || span.tag !== 'SPAN' || span.attrs.length) return null;
    const inner = significant(span), scripts = inner.filter(n => n.tag === 'SCRIPT');
    if (scripts.length > 1 || scripts.some(script => !onlyAttrs(script, ['async', 'charset', 'src'])
      || !['https://platform.x.com/widgets.js', 'https://platform.twitter.com/widgets.js'].includes(get(script, 'src'))
      || significant(script).length)) return null;
    const renderers = inner.filter(n => n.tag !== 'SCRIPT');
    if (renderers.length < 1 || renderers.length > 2) return null;
    const fallback = renderers[1];
    if (fallback) {
      if (fallback.tag !== 'BLOCKQUOTE' || get(fallback, 'class') !== 'twitter-tweet'
        || fallback.attrs.some(([name, value]) => !['align', 'class', 'data-dnt'].includes(name)
          && !(/^data-twitter-extracted-i\d+$/.test(name) && value === 'true'))) return null;
      let matchingStatus = false;
      function fallbackNode(node) {
        if (node.tag === '#text') return true;
        if (!['BLOCKQUOTE', 'P', 'A', 'BR'].includes(node.tag)) return false;
        if (node !== fallback && !onlyAttrs(node, node.tag === 'P' ? ['dir', 'lang'] : node.tag === 'A' ? ['href', 'tabindex'] : [])) return false;
        if (node.tag === 'A') {
          let href;
          try { href = new URL(get(node, 'href')); } catch { return false; }
          if (href.protocol !== 'https:' || !['x.com', 'twitter.com', 't.co'].includes(href.hostname)
            || href.username || href.password || href.port) return false;
          const status = href.pathname.match(/^\/[A-Za-z0-9_]+\/status\/(\d+)\/?$/);
          if (status && status[1] !== post[1]) return false;
          if (status && ['x.com', 'twitter.com'].includes(href.hostname)) matchingStatus = true;
        }
        return node.children.every(fallbackNode);
      }
      if (!fallbackNode(fallback) || !matchingStatus || scripts.length !== 1) return null;
    }
    const rendered = renderers[0];
    if (rendered.tag !== 'DIV' || !onlyAttrs(rendered, ['class', 'style'])
      || get(rendered, 'class')?.split(/\s+/).sort().join(' ') !== 'twitter-tweet twitter-tweet-rendered') return null;
    const frameNodes = significant(rendered), frame = frameNodes[0];
    if (frameNodes.length !== 1 || frame.tag !== 'IFRAME' || frame.children.length
      || !onlyAttrs(frame, ['allowfullscreen', 'allowtransparency', 'data-tweet-id', 'frameborder', 'id',
        'scrolling', 'src', 'style', 'title', 'width', 'height'])
      || get(frame, 'data-tweet-id') && get(frame, 'data-tweet-id') !== post[1]
      || !/^twitter-widget-\d+$/.test(get(frame, 'id') ?? '')) return null;
    const projection = () => ({ ...figure, children: [{ tag: 'TWITTER-PREVIEW', attrs: [['status-id', post[1]],
      ['status-url', `https://x.com/i/status/${post[1]}`]], children: [] }] });
    // Observed Twitter bootstrap state has a source-less hidden iframe plus the matching fallback.
    if (!get(frame, 'src')) return fallback && /^position: absolute; visibility: hidden; width: 0px; height: 0px;?$/.test(get(frame, 'style') ?? '')
      ? projection() : null;
    let src;
    try { src = new URL(get(frame, 'src')); } catch { return null; }
    if (src.protocol !== 'https:' || src.hostname !== 'platform.twitter.com' || src.pathname !== '/embed/Tweet.html'
      || src.username || src.password || src.port || src.hash || src.searchParams.getAll('id').length !== 1
      || src.searchParams.get('id') !== post[1]
      || src.searchParams.has('embedId') && (src.searchParams.getAll('embedId').length !== 1
        || src.searchParams.get('embedId') !== get(frame, 'id'))
      || [...src.searchParams.keys()].some(key => !['dnt', 'embedId', 'features', 'frame', 'hideCard', 'hideThread',
        'id', 'lang', 'origin', 'sessionId', 'theme', 'widgetsVersion', 'width'].includes(key))) return null;
    return projection();
  }
  function tree(node) {
    if (node.nodeType === 3) return { tag: '#text', text: node.textContent };
    if (node.nodeType !== 1) return { tag: `#${node.nodeType}`, text: node.textContent };
    const result = { tag: node.tagName, attrs: attrs(node), children: [...node.childNodes].map(tree) };
    return node.tagName === 'FIGURE' && node.parentElement === root ? twitterPreview(result) ?? result : result;
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
  let embedInput = null;
  try {
    const inputs = [...document.querySelectorAll('textarea[placeholder="https://example.com"]')];
    const input = inputs[0];
    embedInput = { count: inputs.length, active: inputs.length === 1 && document.activeElement === input,
      visible: inputs.length === 1 && input.getClientRects().length > 0,
      value: inputs.length === 1 ? input.value : null };
  } catch { /* Native dialog input cannot be verified on this host. */ }
  return {
    url: window.location.href, title: document.title, rootCount: 1,
    // 深いカードDOMをhostの再帰上限で欠落させない。文字列を読戻して復元する。
    rootAttrs: attrs(root), blocksJson: JSON.stringify([...root.childNodes].map(tree)),
    rawHtml: root.innerHTML, bodyText: root.textContent,
    documentFocusKnown: typeof document.hasFocus === 'function',
    focused: typeof document.hasFocus === 'function'
      ? document.hasFocus() && (document.activeElement === root || root.contains(document.activeElement)) : null,
    activeElementIsRoot: document.activeElement === root,
    visible: root.getClientRects().length > 0, view, embedInput,
    selection: {
      ranges, intersectionsKnown,
      collapsed: selection?.isCollapsed === true, rangeCount: selection?.rangeCount,
      blockIndex: [...root.childNodes].indexOf(block), inside, emptyPosition,
      sameNode: anchor === selection?.focusNode,
      anchorOffset: selection?.anchorOffset, focusOffset: selection?.focusOffset,
      text: typeof selection?.toString === 'function' ? selection.toString() : null,
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
const mismatchPath = (a, b, path = '$') => {
  if (equal(a, b)) return null;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return path;
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  for (const key of keys) {
    if (!(key in a) || !(key in b)) return `${path}.${key}`;
    const difference = mismatchPath(a[key], b[key], `${path}.${key}`);
    if (difference) return difference;
  }
  return path;
};
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
function nativeBodyRowMatches(state, start, end, bodyText) {
  const expected = bodyText.replace(/\s/gu, '');
  if (!expected) return false;
  let cursor = start, index = 0;
  // Consume the known DOM body first. A body line may itself look like an AX row.
  while (index < expected.length && cursor < end) {
    const unit = state[cursor++];
    if (/\s/u.test(unit)) continue;
    if (unit !== expected[index++]) return false;
  }
  if (index !== expected.length) return false;
  const tail = state.slice(cursor, end);
  return /^\s*$/u.test(tail)
    || /^[ \t\r]*\n\s*(?:\d+ (?:button|container|heading|image|link|text|static text|text entry area|checkbox|radio button|switch|combo box|pop up button|content list)\b|The focused UI element is \d+ )/u.test(tail);
}

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
  const matchingRows = rows.filter(row => nativeBodyRowMatches(state,
    row.index + row[0].length - row[1].length, focused[0].index, snapshot.bodyText));
  if (matchingRows.length !== 1 || !normalize(snapshot.bodyText)
    || normalize(focused[0][2]) !== normalize(snapshot.bodyText)) return null;
  // Bind the focused ID to the body row, not merely to any editable title field.
  return id;
}

// Full body row and target header identify the editor without depending on its opening words.
function nativeBodyRoot(state, lock, snapshot) {
  if (typeof state !== 'string') return null;
  const header = state.match(/^Browser tab: ([^,\r\n]+), Title: ("(?:\\.|[^"\\])*"), URL: ("(?:\\.|[^"\\])*")\./);
  if (!header || header[1].trim() !== lock.tabId || JSON.parse(header[2]) !== snapshot.title
    || JSON.parse(header[3]) !== lock.noteUrl) return null;
  const rows = [...state.matchAll(/^[ \t]*(\d+) text entry area \(settable\) /gm)];
  const matches = rows.filter(row => nativeBodyRowMatches(
    state, row.index + row[0].length, state.length, snapshot.bodyText));
  return matches.length === 1 ? Number(matches[0][1]) : null;
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
  // A native selection event can reach DOM before the AX focus row updates.
  // Settle by observations only; never repeat the selection or a content write.
  async function readNativeSelection(inputFocus = false) {
    if (!inputFocus) return read(false);
    for (let attempt = 0; attempt < 3; attempt++) {
      try { return await read(true); }
      catch (error) {
        const code = error?.diagnostic?.code;
        if (attempt === 2 || !['native_focus_unverified', 'document_unstable'].includes(code)) throw error;
      }
    }
  }
  async function nativeBodyRootFor(readCurrent, rawPayload = null) {
    // Twitter preview text and its AX value can settle on separate turns.
    // Re-observe the exact same target, without repeating any UI action.
    for (let attempt = 0; attempt < 3; attempt++) {
      const first = await readCurrent();
      const state = await tab.ax.get('state', { disableDiffing: true });
      const current = await readCurrent();
      const root = nativeBodyRoot(state, lock, current);
      if (first.bodyText === current.bodyText && root !== null) {
        // A root-wide URL selection can cross a preceding read-only widget. Prefer
        // its exact static text leaf; duplicates/missing leaves retain the guarded root path.
        if (typeof rawPayload === 'string') {
          const leaves = [...state.matchAll(/^[ \t]*(\d+) text ([^\r\n]*)$/gm)].filter(row => row[2] === rawPayload);
          if (leaves.length === 1 && Number.isSafeInteger(Number(leaves[0][1]))) return Number(leaves[0][1]);
        }
        return root;
      }
    }
    throw new ObservationError('native_embed_root_unverified', 'native_embed', true);
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
    const identityAttrs = node => node.attrs.filter(([name]) => ['id', 'name'].includes(name));
    const nonIdentityAttrs = node => node.attrs.filter(([name]) => !['id', 'name'].includes(name));
    // Only Note's observed UUID-v4 id/name pair is managed. Unknown/partial
    // identities never authorize rebinding; identifier-free fixtures stay exact.
    const managedIdentity = node => {
      if (node?.tag !== 'P') return null;
      const entries = identityAttrs(node);
      const id = attr(node, 'id');
      return entries.length === 2 && entries.filter(([name]) => name === 'id').length === 1
        && entries.filter(([name]) => name === 'name').length === 1 && attr(node, 'name') === id
        && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id) ? id : null;
    };
    const original = before.blocks[index];
    const originalId = managedIdentity(original);
    if (originalId) {
      // Protect root identities and all outside descendants on both sides;
      // root/prefix/suffix equality alone cannot detect a new identity collision.
      const outsideIds = new Set([
        { attrs: before.rootAttrs }, { attrs: after.rootAttrs },
        ...before.blocks.filter((_, i) => i !== index),
        ...after.blocks.slice(0, index), ...after.blocks.slice(index + paragraphs.length),
      ].flatMap(descendants).flatMap(node => (node.attrs ?? [])
        .filter(([name]) => ['id', 'name'].includes(name)).map(([, value]) => value)));
      const insertedIds = inserted.map(managedIdentity);
      if (outsideIds.has(originalId) || insertedIds.some(id => !id || outsideIds.has(id))
        || new Set(insertedIds).size !== insertedIds.length) return 'blocked';
    }
    return inserted.length === paragraphs.length && inserted.every((node, i) => {
      if (node.tag !== 'P' || !(originalId ? equal(nonIdentityAttrs(node), nonIdentityAttrs(original))
        : equal(node.attrs, original.attrs))
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
  function nativeEmbedCompare(before, after, index, payload, nativeStage = null) {
    if (before.url !== after.url || before.title !== after.title || !equal(before.rootAttrs, after.rootAttrs)) return 'blocked';
    if (semantic(before) === semantic(after)) return 'pending';
    if (nativeStage && semantic(nativeStage) === semantic(after)) return 'pending';
    if (!equal(before.blocks.slice(0, index), after.blocks.slice(0, index))) return 'blocked';
    const figure = after.blocks[index];
    if (figure?.tag !== 'FIGURE' || attr(figure, 'data-src') !== payload
      || descendants(figure).filter(n => n.tag === 'FIGURE').length !== 1 || textOf(figure).length > 2048) return 'blocked';
    const tail = after.blocks.slice(index + 1), suffix = before.blocks.slice(index + 1);
    if (equal(tail, [before.blocks[index], ...suffix])) return 'pending'; // card placed; raw URL still present
    if (equal(tail, suffix) || tail.length === suffix.length + 1 && empty(tail[0])
      && equal(tail[0].attrs, before.blocks[index].attrs) && equal(tail.slice(1), suffix)) return 'completed';
    return 'blocked';
  }
  async function nativeEmbedFinish(before, index, payload, nativeStage = null,
    cleanupStarted = channel.pending?.cleanupStarted ?? false, nativeCardId = channel.pending?.nativeCardId ?? null) {
    const after = await read(false);
    const state = nativeEmbedCompare(before, after, index, payload, nativeStage);
    if (state === 'blocked' || nativeCardId && (after.blocks[index]?.tag !== 'FIGURE'
      || attr(after.blocks[index], 'id') !== nativeCardId)) return block('native_embed_document_changed', before, after, payload);
    if (state === 'pending') return nativeEmbedPending(before, index, payload, 'native_embed_read_only_required', null, nativeStage, cleanupStarted, nativeCardId);
    channel.state = 'idle';
    const result = receipt('completed', 'native_embed_verified', before, after, payload);
    channel.pending = null;
    return result;
  }
  function nativeEmbedPending(before, index, payload, reason, diagnostic = null, nativeStage = null,
    cleanupStarted = channel.pending?.cleanupStarted ?? false, nativeCardId = channel.pending?.nativeCardId ?? null) {
    const result = pending(before, index, payload, reason, diagnostic);
    if (channel.pending) { channel.pending.nativeEmbed = true; channel.pending.nativeStage = nativeStage;
      channel.pending.cleanupStarted = cleanupStarted; channel.pending.nativeCardId = nativeCardId; }
    return result;
  }
  async function nativeCleanupPlacement(before, index, payload, nativeCardId, inputFocus = false) {
    const current = await readNativeSelection(inputFocus);
    if (!nativeCardId || nativeCardId === 'null' || current.blocks[index]?.tag !== 'FIGURE'
      || attr(current.blocks[index], 'id') !== nativeCardId
      || nativeEmbedCompare(before, current, index, payload) !== 'pending'
      || current.visible !== true || inputFocus && current.focused !== true) {
      throw new ObservationError('native_embed_cleanup_target_changed', 'native_embed_cleanup');
    }
    return current;
  }
  async function embedViaNativeDialog(request = {}) {
    if (channel.state !== 'idle') return receipt(channel.state, 'input_stopped');
    channel.state = 'busy';
    const { payload, caption } = request ?? {};
    if (!request || typeof request !== 'object' || Array.isArray(request)
      || Reflect.ownKeys(request).some(k => !['payload', 'caption'].includes(k))
      || !validPayload(payload) || new URL(payload).port || !validParagraphs([caption])
      || caption.includes('\n') || caption.length > 2048 || typeof tab.ax?.selectText !== 'function'
      || typeof tab.ax?.pressKey !== 'function' || typeof tab.ax?.get !== 'function'
      || typeof tab.ax?.click !== 'function') return block('invalid_native_embed_request');
    let before, index, nativeStage = null, nativeCardId = null, started = false, cleanupStarted = false;
    try {
      before = await read(false);
      const rawParagraph = node => node?.tag === 'P' && attr(node, 'contenteditable') !== 'false'
        && descendants(node).every(n => ['P', 'A', '#text'].includes(n.tag))
        && descendants(node).filter(n => n.tag === 'A').every(n => attr(n, 'href') === payload);
      const captionParagraph = node => node?.tag === 'P' && attr(node, 'contenteditable') !== 'false'
        && descendants(node).every(n => ['P', 'A', 'BR', '#text'].includes(n.tag)
          && attr(n, 'contenteditable') !== 'false' && (n.tag !== 'BR' || n.children.length === 0));
      const raw = before.blocks.flatMap((b, i) => rawParagraph(b) && textOf(b) === payload ? [i] : []);
      const captions = before.blocks.flatMap((b, i) => captionParagraph(b) && textOf(b) === caption ? [i] : []);
      if (raw.length !== 1 || captions.length !== 1 || raw[0] !== captions[0] + 1
        || before.blocks.some(b => descendants(b).some(n => n.tag === 'FIGURE' && attr(n, 'data-src') === payload))) return block('native_embed_target_ambiguous', before);
      index = raw[0];
      async function locked(expected, inputFocus = false) {
        const current = await readNativeSelection(inputFocus);
        if (current.title !== before.title) throw new ObservationError('native_embed_target_changed', 'native_embed');
        if (semantic(current) !== semantic(expected)) throw new ObservationError('native_embed_document_changed_before_action', 'native_embed');
        if (current.visible !== true) throw new ObservationError('native_embed_editor_not_visible', 'native_embed');
        if (inputFocus && current.focused !== true) throw new ObservationError('native_embed_editor_not_focused', 'native_embed');
        return current;
      }
      async function rootFor(expected) {
        return nativeBodyRootFor(() => locked(expected));
      }
      const root = await rootFor(before);
      started = true;
      await tab.ax.selectText(root, caption, { selectionType: 'cursor_after' });
      const cursor = await locked(before, true), q = cursor.selection, range = q?.ranges?.[0];
      const end = range?.end;
      let endNode = before.blocks[index - 1];
      for (const part of end?.nodePath ?? []) endNode = endNode?.children?.[part];
      const atEnd = endNode && end?.offset === (endNode.tag === '#text' ? endNode.text.length : endNode.children.length)
        && (end?.nodePath ?? []).every((part, depth, path) => {
          let node = before.blocks[index - 1];
          for (const ancestor of path.slice(0, depth)) node = node.children[ancestor];
          return part === node.children.length - 1;
        });
      if (!selectionWithinBlock(cursor, index - 1) || !q.collapsed || !q.inside || !atEnd
        || !equal(range.start, range.end)) return block('native_embed_wrong_caption_cursor', before, cursor, payload);
      async function lockedCaptionRange() {
        // The dialog owns focus, but the editor's saved insertion Range must stay at the caption.
        const current = await locked(before);
        if (!selectionWithinBlock(current, index - 1) || !current.selection.collapsed
          || !current.selection.inside || !equal(current.selection.ranges, cursor.selection.ranges)) {
          throw new ObservationError('native_embed_caption_range_changed', 'native_embed');
        }
        return current;
      }
      if (!equal((await locked(before, true)).selection, cursor.selection)) return block('native_embed_cursor_changed', before, null, payload);
      await tab.playwright.getByRole('button', { name: 'メニューを開く', exact: true }).click();
      await lockedCaptionRange();
      await tab.playwright.getByRole('button', { name: '埋め込み', exact: true }).click();
      await tab.playwright.getByPlaceholder('https://example.com', { exact: true }).waitFor({ state: 'visible', timeoutMs: 10000 });
      const staged = await read(false), stagingP = staged.blocks[index];
      const stagingChecks = {
        title: staged.title === before.title, rootAttrs: equal(staged.rootAttrs, before.rootAttrs),
        newEmptyP: empty(stagingP) && stagingP.attrs.every(([name]) => ['id', 'name'].includes(name)),
        prefix: equal(staged.blocks.slice(0, index), before.blocks.slice(0, index)),
        suffix: equal(staged.blocks.slice(index + 1), before.blocks.slice(index)),
      };
      if (Object.values(stagingChecks).some(passed => !passed)) {
        const expected = { rootAttrs: before.rootAttrs, blocks: [...before.blocks.slice(0, index), stagingP, ...before.blocks.slice(index)] };
        return block('native_embed_staging_changed', before, staged, payload,
          { code: 'native_embed_staging_changed', phase: 'native_embed_staging', recoverable: false,
            checks: stagingChecks, mismatch_path: mismatchPath(expected, { rootAttrs: staged.rootAttrs, blocks: staged.blocks }) });
      }
      nativeStage = staged;
      async function lockedDialog(expectedValue) {
        const current = await locked(nativeStage), input = current.embedInput, selection = current.selection;
        if (input?.count !== 1 || input.active !== true || input.visible !== true || input.value !== expectedValue) {
          throw new ObservationError('native_embed_dialog_unverified', 'native_embed');
        }
        // Focusing the actual URL textarea moves browser Selection outside the editor.
        // If this host retains an editor bookmark instead, only the verified caption end
        // or the new empty staging P may remain selected.
        const outside = selection?.inside === false && selection.collapsed === true && selection.intersectionsKnown === true
          && selection.rangeCount === 1 && selection.blockIndex === -1
          && Array.isArray(selection.ranges) && selection.ranges.length === 1
          && selection.ranges[0].start === null && selection.ranges[0].end === null
          && Array.isArray(selection.ranges[0].protectedIntersections)
          && selection.ranges[0].protectedIntersections.length === 0;
        const captionBookmark = selectionWithinBlock(current, index - 1)
          && selection.collapsed === true && selection.inside === true
          && equal(selection.ranges, cursor.selection.ranges);
        const stageBookmark = selectionWithinBlock(current, index) && selection.collapsed === true
          && selection.inside === true && equal(selection.ranges[0].start, selection.ranges[0].end)
          && selection.ranges[0].start.offset === 0
          && selection.ranges[0].start.nodePath.length === 0;
        if (!outside && !captionBookmark && !stageBookmark) {
          throw new ObservationError('native_embed_caption_range_changed', 'native_embed');
        }
        return current;
      }
      await lockedDialog('');
      await tab.playwright.getByPlaceholder('https://example.com', { exact: true }).fill(payload);
      const dialog = await lockedDialog(payload);
      const applyState = await tab.ax.get('state', { disableDiffing: true });
      const applyButtons = typeof applyState === 'string' ? [...applyState.matchAll(/^[ \t]*(\d+) button 適用(?:, ID: [^\s,]+)?[ \t]*$/gm)] : [];
      if (nativeBodyRoot(applyState, lock, dialog) === null || applyButtons.length !== 1) {
        return block('native_embed_apply_unverified', before, dialog, payload);
      }
      const applyId = Number(applyButtons[0][1]);
      if (!Number.isSafeInteger(applyId)) return block('native_embed_apply_unverified', before, dialog, payload);
      await lockedDialog(payload);
      await tab.ax.click(applyId);
      await tab.playwright.locator(`figure[data-src="${payload.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"]`).waitFor({ state: 'attached', timeoutMs: 10000 });
      const placed = await read(false);
      if (nativeEmbedCompare(before, placed, index, payload) !== 'pending'
        || placed.blocks[index]?.tag !== 'FIGURE') return block('native_embed_placement_unverified', before, placed, payload);
      nativeCardId = attr(placed.blocks[index], 'id');
      if (!nativeCardId || nativeCardId === 'null') {
        nativeCardId = null;
        return nativeEmbedPending(before, index, payload, 'native_embed_card_id_loading', null, nativeStage, false, null);
      }
      const cleanupPlacement = inputFocus => nativeCleanupPlacement(before, index, payload, nativeCardId, inputFocus);
      const rawRoot = await nativeBodyRootFor(() => cleanupPlacement(false), payload);
      cleanupStarted = true;
      await tab.ax.selectText(rawRoot, payload, { selectionType: 'text' });
      const selected = await cleanupPlacement(true), selection = selected.selection;
      if (!selectionWithinBlock(selected, index + 1) || selection.collapsed || !selection.inside
        || selection.text !== payload) return block('native_embed_wrong_raw_selection', before, selected, payload);
      if (!equal((await cleanupPlacement(true)).selection, selected.selection)) return block('native_embed_selection_changed', before, null, payload);
      await tab.ax.pressKey(null, 'Backspace');
      return await nativeEmbedFinish(before, index, payload, nativeStage, cleanupStarted, nativeCardId);
    } catch (error) {
      const diagnostic = diagnosticOf(error, 'native_embed');
      if (!started || !diagnostic.recoverable) return block('native_embed_failed', before, null, payload, diagnostic);
      return nativeEmbedPending(before, index, payload, 'native_embed_outcome_unknown', diagnostic, nativeStage, cleanupStarted, nativeCardId);
    }
  }
  async function completeNativeEmbed() {
    if (channel.state !== 'pending' || !channel.pending?.nativeEmbed) return receipt(channel.state, 'no_pending_native_embed');
    if (!equal(channel.pending.lock, lock)) return block('pending_target_changed');
    const { before, index, payload, nativeStage } = channel.pending;
    channel.state = 'busy';
    try {
      const placed = await read(false);
      const state = nativeEmbedCompare(before, placed, index, payload, nativeStage);
      if (state === 'blocked') return block('native_embed_document_changed', before, placed, payload);
      if (channel.pending.nativeCardId && (placed.blocks[index]?.tag !== 'FIGURE'
        || attr(placed.blocks[index], 'id') !== channel.pending.nativeCardId)) return block('native_embed_card_id_unverified', before, placed, payload);
      if (state === 'completed') return await nativeEmbedFinish(before, index, payload, nativeStage);
      if (placed.blocks[index]?.tag !== 'FIGURE') return nativeEmbedPending(before, index, payload, 'native_embed_card_not_ready', null, nativeStage);
      if (channel.pending.cleanupStarted) return nativeEmbedPending(before, index, payload, 'native_embed_cleanup_stopped', null, nativeStage);
      if (typeof tab.ax?.get !== 'function' || typeof tab.ax?.selectText !== 'function'
        || typeof tab.ax?.pressKey !== 'function') return block('native_embed_cleanup_unavailable', before, placed, payload);
      const nativeCardId = channel.pending.nativeCardId ?? attr(placed.blocks[index], 'id');
      if (!nativeCardId || nativeCardId === 'null') return nativeEmbedPending(before, index, payload, 'native_embed_card_id_loading', null, nativeStage, false, null);
      if (attr(placed.blocks[index], 'id') !== nativeCardId) return block('native_embed_card_id_unverified', before, placed, payload);
      channel.pending.nativeCardId = nativeCardId;
      const samePlacement = inputFocus => nativeCleanupPlacement(before, index, payload, nativeCardId, inputFocus);
      const root = await nativeBodyRootFor(() => samePlacement(), payload);
      // A pending insert can be completed once, never re-applied or resent after an uncertain cleanup.
      channel.pending.cleanupStarted = true;
      await tab.ax.selectText(root, payload, { selectionType: 'text' });
      const selected = await samePlacement(true), selection = selected.selection;
      if (!selectionWithinBlock(selected, index + 1) || selection.collapsed || !selection.inside
        || selection.text !== payload) return block('native_embed_wrong_raw_selection', before, selected, payload);
      if (!equal((await samePlacement(true)).selection, selection)) return block('native_embed_selection_changed', before, null, payload);
      await tab.ax.pressKey(null, 'Backspace');
      return await nativeEmbedFinish(before, index, payload, nativeStage);
    } catch (error) {
      const diagnostic = diagnosticOf(error, 'native_embed_cleanup');
      if (!diagnostic.recoverable) return block(diagnostic.code, before, null, payload, diagnostic);
      return nativeEmbedPending(before, index, payload, 'native_embed_cleanup_unknown', diagnostic, nativeStage);
    }
  }
  return Object.freeze({
    scrollToEdge,
    embedViaNativeDialog,
    completeNativeEmbed,
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
      const { before, index, payload, paragraphs, nativeEmbed, nativeStage } = channel.pending;
      channel.pending.attempts++;
      channel.state = 'busy';
      try { return nativeEmbed ? await nativeEmbedFinish(before, index, payload, nativeStage) : await finish(before, index, payload, paragraphs); }
      catch (error) {
        const diagnostic = diagnosticOf(error, 'reconcile');
        if (!diagnostic.recoverable) return block(diagnostic.code, before, null, payload, diagnostic);
        return nativeEmbed ? nativeEmbedPending(before, index, payload, 'reconcile_unavailable_read_only', diagnostic, nativeStage)
          : pending(before, index, payload, 'reconcile_unavailable_read_only', diagnostic, paragraphs);
      }
    },
  });
}
