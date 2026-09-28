#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""课件查看器"桥接脚本"：随 viewer 页面注入，接受聊天父页面的 postMessage 指令，
在课件内定位关键词、临时高亮并滚动居中，或把 hint/reveal/step 等操作指令
转交给课件自己实现的 ``window.__aiteacherCmd`` 钩子。

sandbox iframe（opaque origin）不影响 postMessage 双向通信，因此无需放宽
iframe 权限；AI
"""

BRIDGE_JS = r"""
(() => {
  if (window.__aiteacherBridge) return;
  window.__aiteacherBridge = true;
  const MARK_CLASS = 'aiteacher-hl';
  let styleAdded = false;
  let clearTimer = null;

  function ensureStyle() {
    if (styleAdded) return;
    styleAdded = true;
    const style = document.createElement('style');
    style.textContent =
      '@keyframes aiteacher-hl-flash{0%,100%{background:#ffe08a}50%{background:#fff3c4}}' +
      'mark.' + MARK_CLASS + '{background:#ffe08a;color:#5a4408;border-radius:4px;' +
      'padding:0 2px;animation:aiteacher-hl-flash 1s ease 3;}' +
      '@media (prefers-reduced-motion: reduce){mark.' + MARK_CLASS + '{animation:none}}';
    document.head.appendChild(style);
  }

  function clearHighlights() {
    document.querySelectorAll('mark.' + MARK_CLASS).forEach(mark => {
      const parent = mark.parentNode;
      if (!parent) return;
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
      parent.removeChild(mark);
      parent.normalize();
    });
  }

  // 只匹配单个文本节点内的完整关键词；被标签拆开的词属于已知限制。
  function highlightText(query) {
    const target = query.toLowerCase();
    let count = 0;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const name = node.parentElement ? node.parentElement.tagName : '';
        if (name === 'SCRIPT' || name === 'STYLE' || name === 'MARK' || name === 'TEXTAREA') {
          return NodeFilter.FILTER_REJECT;
        }
        if (!node.nodeValue || node.nodeValue.toLowerCase().indexOf(target) === -1) {
          return NodeFilter.FILTER_SKIP;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const text = node.nodeValue;
      const lower = text.toLowerCase();
      let idx = lower.indexOf(target);
      if (idx === -1) return;
      const frag = document.createDocumentFragment();
      let last = 0;
      while (idx !== -1) {
        if (idx > last) frag.appendChild(document.createTextNode(text.slice(last, idx)));
        const mark = document.createElement('mark');
        mark.className = MARK_CLASS;
        mark.textContent = text.slice(idx, idx + query.length);
        frag.appendChild(mark);
        count += 1;
        last = idx + query.length;
        idx = lower.indexOf(target, last);
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
    return count;
  }

  window.addEventListener('message', event => {
    if (event.source !== window.parent) return;
    const data = event.data || {};
    if (data.type !== 'aiteacher-highlight') return;
    const query = String(data.query || '').trim().slice(0, 100);
    ensureStyle();
    if (clearTimer) { window.clearTimeout(clearTimer); clearTimer = null; }
    clearHighlights();
    let count = 0;
    if (query) {
      count = highlightText(query);
      if (count) {
        const first = document.querySelector('mark.' + MARK_CLASS);
        if (first && first.scrollIntoView) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
        clearTimer = window.setTimeout(() => { clearTimer = null; clearHighlights(); }, 6000);
      }
    }
    try {
      parent.postMessage({ type: 'aiteacher-highlight-result', query: query, count: count }, '*');
    } catch (_) {}
  });

  // 反向操作课件：桥接层只做传输与兜底回执，具体表现由课件实现 __aiteacherCmd。
  // 没实现钩子的课件（历史课件、AI 生成的课件）回 handled=false，由聊天页提示用户。
  window.addEventListener('message', event => {
    if (event.source !== window.parent) return;
    const data = event.data || {};
    if (data.type !== 'aiteacher-cmd') return;
    const action = String(data.action || '').slice(0, 20);
    const value = String(data.value || '').slice(0, 100);
    let handled = false;
    try {
      if (typeof window.__aiteacherCmd === 'function') {
        handled = window.__aiteacherCmd({ action: action, value: value }) === true;
      }
    } catch (_) {
      handled = false;
    }
    try {
      parent.postMessage({
        type: 'aiteacher-cmd-result', action: action, value: value, handled: handled,
      }, '*');
    } catch (_) {}
  });
})();
"""

BRIDGE_TAG = '<script id="aiteacher-material-bridge">' + BRIDGE_JS + '</script>'


def inject_bridge(html):
    """把桥接脚本插到最后一个 </body> 前；没有 </body> 就追加到末尾。"""
    idx = html.lower().rfind('</body>')
    if idx != -1:
        return html[:idx] + BRIDGE_TAG + html[idx:]
    return html + BRIDGE_TAG
