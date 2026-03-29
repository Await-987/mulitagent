'use strict';
/* ════════════════════════════════════════════════════════════════════
   ORCA OS View — main.js
   ════════════════════════════════════════════════════════════════════ */

// ── 1. CONFIG & CONSTANTS ─────────────────────────────────────────
const CFG = {
  POLL_NOTIF:  2000,   // ms – notification polling
  POLL_DATA:   4000,   // ms – data refresh for open apps
  CACHE_TTL:   3000,   // ms – data cache freshness
  POLL_ICONS:  5000,   // ms – icon asset refresh
};

// Avatar colour palette (one per contact)
const AVATAR_COLORS = [
  '#FF3B30','#FF9500','#FFCC00','#34C759','#00C7BE',
  '#007AFF','#5856D6','#AF52DE','#FF2D55','#A2845E',
];

const HOME_LAYOUT_KEY = 'orca_os_home_layout_v3';

// ── 2. DATA SERVICE ───────────────────────────────────────────────
class DataService {
  constructor() {
    this._cache = new Map();   // endpoint → data
    this._ts    = new Map();   // endpoint → timestamp
  }

  async get(ep, force = false) {
    const now = Date.now();
    if (!force && this._cache.has(ep) && (now - this._ts.get(ep) < CFG.CACHE_TTL)) {
      return this._cache.get(ep);
    }
    try {
      const r = await fetch('/api/' + ep);
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      this._cache.set(ep, data);
      this._ts.set(ep, now);
      return data;
    } catch (e) {
      console.warn('[DS] fetch error:', ep, e.message);
      return this._cache.get(ep) ?? null;
    }
  }

  async post(ep, body) {
    try {
      const r = await fetch('/api/' + ep, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      this._cache.delete(ep);
      this._ts.delete(ep);
      return data;
    } catch (e) {
      console.warn('[DS] post error:', ep, e.message);
      return null;
    }
  }
}

// ── 3. UTILITIES ──────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function escapeHTML(text = '') {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function fmtDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 86400000) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  if (diff < 604800000) {
    const days = ['日','一','二','三','四','五','六'];
    return '周' + days[d.getDay()];
  }
  return `${d.getMonth()+1}/${d.getDate()}`;
}

function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function avatarLetter(name) { return name ? name[0] : '?'; }

function parseConversation(text, contactName) {
  const msgs = [];
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    const colon = t.indexOf(':');
    if (colon < 0) { msgs.push({ isUser: false, speaker: '?', text: t }); continue; }
    const spk = t.slice(0, colon).trim();
    const txt = t.slice(colon + 1).trim();
    msgs.push({ isUser: spk === '用户', speaker: spk, text: txt });
  }
  return msgs;
}

function docIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const map = { pdf:'📄', txt:'📃', md:'📝', json:'📋', py:'🐍',
                js:'📜', ts:'📜', xlsx:'📊', xls:'📊', docx:'📝',
                doc:'📝', png:'🖼️', jpg:'🖼️', jpeg:'🖼️', mp4:'🎬',
                mp3:'🎵', zip:'📦', rar:'📦' };
  return map[ext] || '📁';
}

function formatBytes(b) {
  if (!b) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(1) + ' MB';
}

function sameDay(a, b) {
  return a && b
    && a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

function sameMonth(a, b) {
  return a && b
    && a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth();
}

function monthTitle(date) {
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' });
}

function dateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function parseDateOnly(iso) {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatFullDate(dateLike) {
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  });
}

function renderAppIconContent(app, className = 'app-icon-media') {
  if (app.iconUrl) {
    return `<img class="${className}" src="${app.iconUrl}" alt="${escapeHTML(app.name)}" />`;
  }
  return `<span class="${className} app-icon-glyph">${app.icon}</span>`;
}

function previewNodeFromHTML(html) {
  if (!html) return null;
  const tpl = document.createElement('template');
  tpl.innerHTML = html.trim();
  const node = tpl.content.firstElementChild;
  if (!node) return null;
  node.querySelectorAll('[id]').forEach((item) => item.removeAttribute('id'));
  node.querySelectorAll('input, textarea, button, a, select').forEach((item) => {
    item.setAttribute('tabindex', '-1');
    item.setAttribute('disabled', 'disabled');
  });
  return node;
}

// ── 4. NOTIFICATION MANAGER ───────────────────────────────────────
class NotificationManager {
  constructor(os) { this.os = os; }

  show({ id, app, title, message }) {
    const icons = { search:'🔍', contacts:'📞', documents:'📁', photos:'📸',
                    xiaohongshu:'🌹', notes:'📝', xiecheng:'✈️', calendar:'📅',
                    settings:'⚙️', system:'🔔' };
    const icon = icons[app] || icons.system;

    const card = el('div', 'notif-card');
    card.innerHTML = `
      <span class="notif-icon">${icon}</span>
      <div class="notif-body">
        <div class="notif-title">${title}</div>
        <div class="notif-msg">${message}</div>
      </div>`;

    const layer = $('#notif-layer');
    layer.appendChild(card);

    let timer = setTimeout(() => this._dismiss(card), 4000);
    card.addEventListener('mouseenter', () => clearTimeout(timer));
    card.addEventListener('mouseleave', () => { timer = setTimeout(() => this._dismiss(card), 2000); });
    card.addEventListener('click', () => this._dismiss(card));
  }

  _dismiss(card) {
    card.classList.add('dismissing');
    card.addEventListener('animationend', () => card.remove(), { once: true });
  }
}

// ── 5. APP SWITCHER ───────────────────────────────────────────────
class AppSwitcher {
  constructor(os) {
    this.os      = os;
    this.el      = $('#app-switcher');
    this.cardsEl = $('#switcher-cards');
    this._raf    = 0;

    // Tap / touch the backdrop (outside any card) → go home
    this.el.addEventListener('mousedown', (e) => {
      if (e.target === this.el) this.os.goHome();
    });
    this.el.addEventListener('touchend', (e) => {
      if (e.target === this.el) this.os.goHome();
    }, { passive: true });

    this.cardsEl?.addEventListener('mousedown', (e) => e.stopPropagation());
    this.cardsEl?.addEventListener('scroll', () => this._scheduleDepth());
    window.addEventListener('resize', () => this._scheduleDepth());
    this._bindScrollerDrag();
  }

  show(stack) {
    const apps = stack.map(id => this.os.getApp(id)).filter(Boolean);
    this.cardsEl.innerHTML = '';

    for (const app of apps) {
      const card = el('div', 'switcher-card');
      const preview = el('div', 'switcher-preview');
      const stage = el('div', 'switcher-preview-stage');
      const meta = el('div', 'switcher-meta');
      const previewNode = this.os.buildAppPreviewNode(app);

      preview.innerHTML = `
        <div class="switcher-swipe-hint"></div>
        <div class="switcher-preview-sheen"></div>
      `;
      if (previewNode) {
        stage.appendChild(previewNode);
      } else {
        stage.innerHTML = `<div class="switcher-preview-fallback">${escapeHTML(app.name)}</div>`;
      }
      preview.appendChild(stage);
      meta.innerHTML = `
        <div class="switcher-meta-icon" style="background:${app.iconUrl ? 'transparent' : app.iconBg};">${renderAppIconContent(app, 'switcher-preview-icon')}</div>
        <div class="switcher-meta-copy">
          <div class="switcher-label">${escapeHTML(app.name)}</div>
          <div class="switcher-subtitle">最近使用</div>
        </div>
      `;
      card.appendChild(preview);
      card.appendChild(meta);

      this._bindCard(card, app);
      this.cardsEl.appendChild(card);
    }

    if (!apps.length) { this.os.goHome(); return; }

    this.el.closest('#screen')?.classList.add('switcher-active');
    this.el.classList.remove('hidden');
    requestAnimationFrame(() => {
      this.el.classList.add('is-open');
      this._scheduleDepth();
    });
    // center on the most recently used app
    setTimeout(() => {
      const lastCard = this.cardsEl.lastElementChild;
      if (lastCard) lastCard.scrollIntoView({ behavior:'smooth', inline:'center', block:'nearest' });
      this._scheduleDepth();
    }, 50);
  }

  hide() {
    this.el.classList.remove('is-open');
    this.el.classList.add('hidden');
    this.el.closest('#screen')?.classList.remove('switcher-active');
  }

  _scheduleDepth() {
    cancelAnimationFrame(this._raf);
    this._raf = requestAnimationFrame(() => this._updateDepth());
  }

  _updateDepth() {
    const scroller = this.cardsEl;
    if (!scroller) return;
    const scrollerRect = scroller.getBoundingClientRect();
    const center = scrollerRect.left + scrollerRect.width / 2;

    $$('.switcher-card', scroller).forEach((card) => {
      if (card.classList.contains('closing')) return;
      const preview = $('.switcher-preview', card);
      if (!preview) return;

      const rect = card.getBoundingClientRect();
      const distance = (rect.left + rect.width / 2 - center) / rect.width;
      const limited = clamp(distance, -1.35, 1.35);
      const emphasis = 1 - Math.min(Math.abs(limited), 1) * 0.24;
      const lift = Math.min(Math.abs(limited), 1) * 18;
      card.classList.toggle('is-focused', Math.abs(limited) < 0.24);
      card.style.transform = `translateY(${lift}px)`;
      preview.style.transform = `rotateY(${limited * -26}deg) scale(${emphasis})`;
      preview.style.opacity = `${1 - Math.min(Math.abs(limited), 1) * 0.34}`;
    });
  }

  _bindCard(card, app) {
    const preview = $('.switcher-preview', card);
    let sx = 0, sy = 0, dragging = false, moved = false, mode = '', startScroll = 0;

    // ── shared gesture logic ──────────────────────────────────────
    const onStart = (clientX, clientY) => {
      startScroll = this.cardsEl?.scrollLeft || 0;
      sx = clientX; sy = clientY;
      dragging = true; moved = false; mode = '';
      preview.style.transition = 'none';
    };

    const onMove = (clientX, clientY) => {
      if (!dragging) return false;
      const dx = clientX - sx;
      const dy = clientY - sy;
      if (!mode && (Math.abs(dx) > 6 || Math.abs(dy) > 6)) {
        mode = Math.abs(dx) > Math.abs(dy) ? 'scroll' : 'card';
      }
      if (mode === 'scroll') {
        moved = true;
        if (this.cardsEl) {
          this.cardsEl.scrollLeft = startScroll - dx;
          this.cardsEl.classList.add('is-dragging');
        }
        preview.style.transform = '';
        preview.style.opacity = '';
        this._scheduleDepth();
        return true; // consumed → caller should preventDefault
      }
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) moved = true;
      preview.style.transform = `translate(${dx * 0.08}px, ${Math.min(30, dy)}px) scale(${clamp(1 - Math.abs(dy) / 800, 0.9, 1)})`;
      preview.style.opacity = `${clamp(1 - Math.max(0, -dy) / 220, 0.25, 1)}`;
      return mode === 'card'; // prevent scroll only when dragging card vertically
    };

    const onEnd = (clientX, clientY) => {
      if (!dragging) return;
      dragging = false;
      const dx = clientX - sx;
      const dy = clientY - sy;
      const shouldClose = mode !== 'scroll' && dy < -110 && Math.abs(dy) > Math.abs(dx);
      preview.style.transition = '';
      this.cardsEl?.classList.remove('is-dragging');

      if (mode === 'scroll') {
        preview.style.transform = '';
        preview.style.opacity = '';
        this._scheduleDepth();
        return;
      }
      if (shouldClose) {
        preview.style.transform = 'translateY(-220px) scale(0.94)';
        preview.style.opacity = '0';
        card.classList.add('closing');
        setTimeout(() => {
          card.remove();
          this.os.dismissFromSwitcher(app.id);
          this._scheduleDepth();
          if (!this.os.getOpenStack().length) this.os.goHome();
        }, 220);
        return;
      }
      preview.style.transform = '';
      preview.style.opacity = '';
      if (!moved) { this.hide(); this.os.openApp(app.id, null); }
      this._scheduleDepth();
    };

    // ── Mouse ─────────────────────────────────────────────────────
    preview.addEventListener('mousedown', (e) => {
      onStart(e.clientX, e.clientY);
      e.preventDefault();
      const mm = (evt) => { if (onMove(evt.clientX, evt.clientY)) evt.preventDefault(); };
      const mu = (evt) => { onEnd(evt.clientX, evt.clientY); window.removeEventListener('mousemove', mm); };
      window.addEventListener('mousemove', mm);
      window.addEventListener('mouseup', mu, { once: true });
    });

    // ── Touch ─────────────────────────────────────────────────────
    preview.addEventListener('touchstart', (e) => {
      onStart(e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: true });

    preview.addEventListener('touchmove', (e) => {
      const consumed = onMove(e.touches[0].clientX, e.touches[0].clientY);
      if (consumed) e.preventDefault();
    }, { passive: false });

    preview.addEventListener('touchend', (e) => {
      onEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
    }, { passive: true });
  }

  _bindScrollerDrag() {
    if (!this.cardsEl) return;
    const scroller = this.cardsEl;
    let sx = 0, startScroll = 0, dragging = false, engaged = false, startTarget = null;

    // ── Mouse drag (desktop) ──────────────────────────────────────
    scroller.addEventListener('mousedown', (e) => {
      startTarget = e.target;
      if (e.target.closest('.switcher-preview')) return;
      sx = e.clientX;
      startScroll = scroller.scrollLeft;
      dragging = true;
      engaged = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - sx;
      if (!engaged && Math.abs(dx) > 5) { engaged = true; scroller.classList.add('is-dragging'); }
      if (!engaged) return;
      scroller.scrollLeft = startScroll - dx;
      this._scheduleDepth();
      e.preventDefault();
    });

    window.addEventListener('mouseup', () => {
      if (!dragging) return;
      const shouldGoHome = !engaged && !startTarget?.closest('.switcher-card');
      dragging = false; engaged = false;
      scroller.classList.remove('is-dragging');
      startTarget = null;
      if (shouldGoHome) this.os.goHome();
    });

    // ── Touch (mobile) ────────────────────────────────────────────
    // Horizontal card scrolling is handled by native touch-scroll
    // (overflow-x: scroll on scroller). We only need to:
    //   1. Keep the depth/perspective effect in sync during scroll.
    //   2. Detect a tap on empty space (no card target) → go home.
    let touchStartTarget = null;
    scroller.addEventListener('touchstart', (e) => {
      touchStartTarget = e.target;
    }, { passive: true });

    scroller.addEventListener('touchend', (e) => {
      const wasTap = e.changedTouches[0] &&
        Math.abs(e.changedTouches[0].clientX - (e.touches[0]?.clientX ?? e.changedTouches[0].clientX)) < 10;
      if (wasTap && !touchStartTarget?.closest('.switcher-card')) {
        this.os.goHome();
      }
      touchStartTarget = null;
    }, { passive: true });
  }
}

// ── 6. BASE APP ───────────────────────────────────────────────────
class BaseApp {
  constructor(os, { id, name, icon, iconBg = '#1c1c1e', headerBg = '#fff' }) {
    this.os       = os;
    this.id       = id;
    this.name     = name;
    this.icon     = icon;
    this.iconBg   = iconBg;
    this.headerBg = headerBg;
    this.window   = null;  // DOM node – set by ORCAOS
    this._pollTimer = null;
  }

  // Subclasses implement these:
  buildHTML()    { return '<div class="state-loading"><div class="spinner"></div></div>'; }
  async onOpen() {}
  onClose()      {}

  push(html) {
    if (!this.window) return;
    this.window.innerHTML = html;
    this._bindBack();
  }

  _bindBack() {
    $$('.app-back', this.window).forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const target = btn.dataset.target;
        if (target) { this._showView(target); }
        else         { this.os.closeApp(this.id); }
      });
    });
  }

  _showView(viewId) {
    $$('.app-view', this.window).forEach(v => {
      v.style.display = v.dataset.view === viewId ? 'flex' : 'none';
    });
  }

  startPoll(fn, interval = CFG.POLL_DATA) {
    this._pollTimer = setInterval(fn, interval);
  }
  stopPoll() { clearInterval(this._pollTimer); }
}

// ── 7. SEARCH APP ─────────────────────────────────────────────────
class SearchApp extends BaseApp {
  constructor(os) {
    super(os, { id:'search', name:'搜索', icon:'🔍', iconBg:'#007AFF', headerBg:'#f2f2f7' });
    this._sessionId   = null;
    this._inChat      = false;
    this._isLoading   = false;
    this._initialized = false;
  }

  buildHTML() {
    return `<div class="app-window-inner search-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div id="search-home" style="flex:1;overflow-y:auto;"></div>
      <div id="search-chat-wrap" class="search-chat-wrap" style="display:none;"></div>
    </div>`;
  }

  _heroHTML() {
    const chips = ['多智能体研究','大模型记忆机制','云南旅游攻略','Python异步编程','CVPR 2025'];
    return `<div class="search-hero">
      <div class="search-logo">ORCA</div>
      <div style="font-size:14px;color:#888;margin-top:-16px;letter-spacing:1px;">Search Agent</div>
      <div class="search-box">
        <input id="search-q" type="text" placeholder="搜索…" autocomplete="off" />
        <button id="search-btn">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="7.5" cy="7.5" r="5.5" stroke="currentColor" stroke-width="1.8"/>
            <line x1="11.5" y1="11.5" x2="16" y2="16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <div class="search-links">
        ${chips.map(c=>`<div class="search-chip" data-q="${c}">${c}</div>`).join('')}
      </div>
    </div>`;
  }

  _chatHTML() {
    return `
      <div class="search-chat-header">
        <span class="search-chat-title">🔍 ORCA 搜索</span>
        <button class="search-chat-reset" id="search-reset-btn">重置</button>
      </div>
      <div class="search-chat-messages" id="search-chat-msgs"></div>
      <div class="search-chat-input-row">
        <input id="search-chat-input" type="text" placeholder="继续提问…" autocomplete="off" />
        <button id="search-chat-send" title="发送">
          <svg width="16" height="16" viewBox="0 0 18 18"><path d="M2 9L16 2l-7 14V10H2z" fill="currentColor"/></svg>
        </button>
      </div>`;
  }

  onOpen() {
    if (!this._initialized) {
      this._initialized = true;
      this._renderHome();
    }
  }

  _renderHome() {
    const home = $('#search-home', this.window);
    const chat = $('#search-chat-wrap', this.window);
    if (home) { home.innerHTML = this._heroHTML(); home.style.display = ''; }
    if (chat) chat.style.display = 'none';
    this._inChat    = false;
    this._isLoading = false;
    this._bindSearch();
  }

  _bindSearch() {
    const win = this.window;
    const doSearch = async () => {
      const q = ($('#search-q', win) || {}).value?.trim();
      if (!q || this._isLoading) return;
      this._enterChat();
      this._appendUserMsg(q);
      this._appendThinking();
      this._isLoading = true;
      const data = await this.os.ds.post('search', { query: q, session_id: this._sessionId || '' });
      if (data?.session_id) this._sessionId = data.session_id;
      this._replaceThinking(data?.answer || '搜索出错，请重试。');
      this._isLoading = false;
    };
    const btn = $('#search-btn', win);
    const inp = $('#search-q', win);
    if (btn) btn.addEventListener('click', doSearch);
    if (inp) inp.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    $$('.search-chip', win).forEach(c => {
      c.addEventListener('click', () => {
        const inp2 = $('#search-q', win);
        if (inp2) inp2.value = c.dataset.q;
        doSearch();
      });
    });
  }

  _enterChat() {
    if (this._inChat) return;
    this._inChat = true;
    const home = $('#search-home', this.window);
    const chat = $('#search-chat-wrap', this.window);
    if (home) home.style.display = 'none';
    if (!chat) return;
    chat.style.display = 'flex';
    chat.innerHTML = this._chatHTML();
    this._bindChatInput();
  }

  _bindChatInput() {
    const win = this.window;
    const doSend = async () => {
      const inp = $('#search-chat-input', win);
      const q   = inp?.value?.trim();
      if (!q || this._isLoading) return;
      if (inp) inp.value = '';
      this._appendUserMsg(q);
      this._appendThinking();
      this._isLoading = true;
      const data = await this.os.ds.post('search', { query: q, session_id: this._sessionId || '' });
      if (data?.session_id) this._sessionId = data.session_id;
      this._replaceThinking(data?.answer || '出现错误，请重试。');
      this._isLoading = false;
    };
    const sendBtn = $('#search-chat-send', win);
    const inp     = $('#search-chat-input', win);
    if (sendBtn) sendBtn.addEventListener('click', doSend);
    if (inp)     inp.addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });

    const resetBtn = $('#search-reset-btn', win);
    if (resetBtn) resetBtn.addEventListener('click', async () => {
      if (this._sessionId) {
        await this.os.ds.post('search/reset', { session_id: this._sessionId }).catch(() => {});
        this._sessionId = null;
      }
      this._initialized = false;
      this.onOpen();
    });
  }

  _appendUserMsg(text) {
    const msgs = $('#search-chat-msgs', this.window);
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'search-msg search-msg-user';
    div.textContent = text;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  _appendThinking() {
    const msgs = $('#search-chat-msgs', this.window);
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'search-msg search-msg-agent search-msg-thinking';
    div.id = 'search-thinking-msg';
    div.innerHTML = `<span class="search-typing-dot"></span><span class="search-typing-dot"></span><span class="search-typing-dot"></span>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  _replaceThinking(answer) {
    const msgs = $('#search-chat-msgs', this.window);
    if (!msgs) return;
    const thinking = msgs.querySelector('#search-thinking-msg');
    if (thinking) thinking.remove();
    const div = document.createElement('div');
    div.className = 'search-msg search-msg-agent search-msg-markdown';

    // Step 1: Extract LaTeX blocks BEFORE Markdown parsing.
    // marked(breaks:true) inserts <br> inside $$…$$ which splits text nodes
    // and breaks renderMathInElement's delimiter search.
    const mathBlocks = [];
    const PH_L = '\uE100', PH_R = '\uE101'; // private-use Unicode, safe through marked & DOMPurify
    let text = answer;
    // Display math first (greedy-safe with [\s\S]*?)
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
      const idx = mathBlocks.length;
      mathBlocks.push({ display: true, math });
      return `${PH_L}MATH${idx}${PH_R}`;
    });
    // Inline math (no newlines inside)
    text = text.replace(/\$([^$\n]+?)\$/g, (_, math) => {
      const idx = mathBlocks.length;
      mathBlocks.push({ display: false, math });
      return `${PH_L}MATH${idx}${PH_R}`;
    });

    // Step 2: Render Markdown → sanitize → inject
    let html;
    if (window.marked) {
      html = window.marked.parse(text, { breaks: true, gfm: true });
      if (window.DOMPurify) html = window.DOMPurify.sanitize(html);
    } else {
      html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }
    div.innerHTML = html;

    // Step 3: Walk DOM text nodes and replace placeholders with KaTeX output
    if (mathBlocks.length > 0) {
      const walker = document.createTreeWalker(div, NodeFilter.SHOW_TEXT);
      const pending = [];
      let n;
      while ((n = walker.nextNode())) {
        if (n.textContent.includes(PH_L)) pending.push(n);
      }
      pending.forEach(node => {
        const parts = node.textContent.split(new RegExp(`(${PH_L}MATH\\d+${PH_R})`));
        if (parts.length <= 1) return;
        const frag = document.createDocumentFragment();
        parts.forEach(part => {
          const m = part.match(new RegExp(`${PH_L}MATH(\\d+)${PH_R}`));
          if (m) {
            const { math, display } = mathBlocks[+m[1]];
            const span = document.createElement('span');
            if (window.katex) {
              try {
                span.innerHTML = window.katex.renderToString(math, { displayMode: display, throwOnError: false });
              } catch (_) {
                span.textContent = display ? `$$${math}$$` : `$${math}$`;
              }
            } else {
              span.textContent = display ? `$$${math}$$` : `$${math}$`;
            }
            frag.appendChild(span);
          } else if (part) {
            frag.appendChild(document.createTextNode(part));
          }
        });
        node.parentNode.replaceChild(frag, node);
      });
    }

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  onClose() { /* preserve chat state across app switches */ }
}

// ── 8. CONTACTS APP ───────────────────────────────────────────────
class ContactsApp extends BaseApp {
  constructor(os) {
    super(os, { id:'contacts', name:'联系人', icon:'📞', iconBg:'#34C759', headerBg:'#f2f2f7' });
    this._data      = null;
    this._activeTab = 'recents';
    this._viewing   = null;
  }

  buildHTML() {
    return `<div class="app-window-inner contacts-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header no-border" style="background:#f2f2f7;">
        <div class="app-title">📞&nbsp;通讯录</div>
      </div>
      <div class="contacts-tabs">
        <div class="contacts-tab active" data-tab="recents">最近通话</div>
        <div class="contacts-tab" data-tab="contacts">联系人</div>
      </div>
      <div id="contacts-body" class="app-content">
        <div class="state-loading"><div class="spinner"></div></div>
      </div>
    </div>`;
  }

  async onOpen() {
    this._bindTabs();
    await this._loadData();
    this._renderTab(this._activeTab);
    this.startPoll(async () => {
      await this._loadData(true);
      if (!this._viewing) this._renderTab(this._activeTab);
    });
  }

  onClose() { this.stopPoll(); this._viewing = null; }

  _bindTabs() {
    $$('.contacts-tab', this.window).forEach(t => {
      t.addEventListener('click', () => {
        $$('.contacts-tab', this.window).forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        this._activeTab = t.dataset.tab;
        this._viewing = null;
        this._renderTab(this._activeTab);
      });
    });
  }

  async _loadData(force = false) {
    this._data = await this.os.ds.get('contacts', force);
  }

  _renderTab(tab) {
    const body = $('#contacts-body', this.window);
    if (!body) return;
    if (!this._data) { body.innerHTML = '<div class="state-error">无法加载联系人数据</div>'; return; }

    if (tab === 'recents') {
      const history = [...(this._data.history || [])].sort((a, b) => {
        const aLast = a.messages?.[a.messages.length - 1]?.timestamp || '';
        const bLast = b.messages?.[b.messages.length - 1]?.timestamp || '';
        return bLast.localeCompare(aLast);
      });
      if (!history.length) { body.innerHTML = '<div class="state-loading" style="color:#aaa;">暂无通话记录</div>'; return; }
      body.innerHTML = `<div class="contacts-list">
        ${history.map(h => this._recentItem(h)).join('')}
      </div>`;
      $$('.contact-item', body).forEach((item, i) => {
        item.addEventListener('click', () => this._openConversation(history[i]));
      });
    } else {
      const profiles = this._data.profiles || {};
      const names = Object.keys(profiles);
      if (!names.length) { body.innerHTML = '<div class="state-loading" style="color:#aaa;">暂无联系人</div>'; return; }
      body.innerHTML = `<div class="contacts-list">
        ${names.map(name => this._contactItem(name, profiles[name])).join('')}
      </div>`;
      // match to history entry
      $$('.contact-item', body).forEach((item, i) => {
        const name = names[i];
        item.addEventListener('click', () => this._openContactDetail(name));
      });
    }
  }

  _recentItem(h) {
    const contactor = h.contactor;
    const msgs = h.messages || [];
    const last = msgs[msgs.length - 1];
    const previewSender = last ? (last.sender === '我' ? '我' : contactor) : '';
    const preview = last ? `${previewSender}: ${last.content}` : '';
    const lastTime = last ? last.timestamp : '';
    const color = avatarColor(contactor);
    return `<div class="contact-item">
      <div class="contact-avatar" style="background:${color}">${avatarLetter(contactor)}</div>
      <div class="contact-info">
        <div class="contact-name">${escapeHTML(contactor)}</div>
        <div class="contact-preview">${escapeHTML(preview)}</div>
      </div>
      <div class="contact-time">${fmtDate(lastTime)}</div>
    </div>`;
  }

  _contactItem(name, profile) {
    const color = avatarColor(name);
    return `<div class="contact-item">
      <div class="contact-avatar" style="background:${color}">${avatarLetter(name)}</div>
      <div class="contact-info">
        <div class="contact-name">${name}</div>
        <div class="contact-sub">${profile['关系'] || ''}</div>
      </div>
    </div>`;
  }

  _latestHistory(name) {
    return (this._data?.history || []).find(h => h.contactor === name) || null;
  }

  _openContactDetail(name) {
    const profiles = this._data?.profiles || {};
    const profile = profiles[name] || {};
    const latest = this._latestHistory(name);
    const color = avatarColor(name);
    const latestMsgs = latest?.messages || [];
    const latestPreview = latestMsgs.length ? latestMsgs[latestMsgs.length - 1] : null;
    const latestTime = latestPreview?.timestamp || '';
    const body = $('#contacts-body', this.window);
    this._viewing = { type: 'detail', name };

    body.innerHTML = `
      <div class="contact-detail app-content">
        <div class="app-header" style="background:#f2f2f7;border-bottom:1px solid rgba(0,0,0,.08);">
          <button class="app-back" id="contact-detail-back">
            <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
              <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            &nbsp;通讯录
          </button>
          <div class="app-title" style="text-align:center;font-size:15px;">联系人资料</div>
          <div style="width:72px;"></div>
        </div>

        <div class="contact-detail-hero">
          <div class="contact-detail-avatar" style="background:${color}">${avatarLetter(name)}</div>
          <div class="contact-detail-name">${name}</div>
          <div class="contact-detail-relation">${profile['关系'] || '联系人'}</div>
        </div>

        <div class="contact-detail-section">
          <div class="contact-detail-card">
            <div class="contact-detail-label">与我关系</div>
            <div class="contact-detail-value">${profile['关系'] || '未填写'}</div>
          </div>
          <div class="contact-detail-card">
            <div class="contact-detail-label">当前状态</div>
            <div class="contact-detail-value">${profile['当前状态'] || '暂无更新'}</div>
          </div>
          <div class="contact-detail-card">
            <div class="contact-detail-label">联系方式</div>
            <div class="contact-detail-value">${profile.phone_number || '未填写'}</div>
          </div>
        </div>

        <div class="contact-detail-section">
          <div class="contact-detail-block-title">最近联系</div>
          <div class="contact-detail-card">
            <div class="contact-detail-label">最近时间</div>
            <div class="contact-detail-value">${latestTime ? formatFullDate(latestTime) : '暂无记录'}</div>
          </div>
          <div class="contact-detail-card">
            <div class="contact-detail-label">最近一条</div>
            <div class="contact-detail-value">${latestPreview ? `${latestPreview.sender === '我' ? '我' : name}：${escapeHTML(latestPreview.content)}` : '暂无消息'}</div>
          </div>
        </div>

        ${profile['说话态度与语气'] ? `
        <div class="contact-detail-section">
          <details class="contact-tone-details">
            <summary class="contact-tone-summary">
              <span>隐藏信息</span>
              <span class="contact-tone-hint">沟通语气</span>
            </summary>
            <div class="contact-tone-body">${escapeHTML(profile['说话态度与语气'])}</div>
          </details>
        </div>
        ` : ''}

        ${latest ? `
          <div class="contact-detail-actions">
            <button class="contact-detail-action" id="contact-open-chat">查看聊天记录</button>
          </div>
        ` : ''}
      </div>`;

    $('#contact-detail-back', this.window)?.addEventListener('click', () => {
      this._viewing = null;
      this._renderTab(this._activeTab);
    });
    $('#contact-open-chat', this.window)?.addEventListener('click', () => this._openConversation(latest, 'detail'));
  }

  _openConversation(h, source = 'recents') {
    this._viewing = h;
    const contactor = h.contactor;
    const msgs = h.messages || [];
    const lastTime = msgs.length ? msgs[msgs.length - 1].timestamp : '';
    const backLabel = source === 'detail' ? contactor : '通讯录';
    const body = $('#contacts-body', this.window);
    body.innerHTML = `
      <div class="app-header" style="background:#f2f2f7;border-bottom:1px solid rgba(0,0,0,.08);">
        <button class="app-back" id="conv-back">
          <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
            <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          &nbsp;${escapeHTML(backLabel)}
        </button>
        <div class="app-title" style="text-align:center;font-size:15px;">
          <div style="font-weight:600;">${escapeHTML(contactor)}</div>
          <div style="font-size:11px;color:#888;font-weight:400;">${fmtDate(lastTime)}</div>
        </div>
        <div style="width:60px;"></div>
      </div>
      <div class="conversation-view app-content">
        <div class="conversation-msgs">
          ${msgs.map(m => `
            <div class="msg-bubble-wrap ${m.sender === '我' ? 'user' : 'contact'}">
              <div class="msg-bubble">${escapeHTML(m.content)}</div>
              <div class="msg-time">${fmtDate(m.timestamp)}</div>
            </div>`).join('')}
        </div>
      </div>`;
    $('#conv-back', this.window)?.addEventListener('click', () => {
      if (source === 'detail') {
        this._openContactDetail(contactor);
      } else {
        this._viewing = null;
        this._renderTab(this._activeTab);
      }
    });
    // scroll to bottom to show latest messages
    setTimeout(() => { body.scrollTop = body.scrollHeight; }, 80);
  }
}

// ── 9. DOCUMENTS APP ─────────────────────────────────────────────
class DocumentsApp extends BaseApp {
  constructor(os) {
    super(os, { id:'documents', name:'文档', icon:'📁', iconBg:'#FF9500', headerBg:'#f2f2f7' });
  }

  buildHTML() {
    return `<div class="app-window-inner documents-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header" style="background:#f2f2f7;">
        <div class="app-title">📁&nbsp;工作文档</div>
      </div>
      <div id="doc-body" class="app-content">
        <div class="state-loading"><div class="spinner"></div></div>
      </div>
    </div>`;
  }

  async onOpen() {
    await this._render();
    this.startPoll(() => this._render());
  }
  onClose() { this.stopPoll(); }

  async _render(force = false) {
    const data = await this.os.ds.get('documents', force);
    const body = $('#doc-body', this.window);
    if (!body) return;
    if (!data || !data.exists) {
      body.innerHTML = `<div class="doc-empty">
        <div class="doc-empty-icon">📭</div>
        <div class="doc-empty-title">暂无工作文档</div>
        <div class="doc-empty-sub">运行 AIOS 后，Agent 生成的文件将在这里显示。<br>默认路径：demo/working_dir/</div>
      </div>`; return;
    }
    if (!data.files.length) {
      body.innerHTML = `<div class="doc-empty">
        <div class="doc-empty-icon">📂</div>
        <div class="doc-empty-title">文件夹为空</div>
        <div class="doc-empty-sub">工作目录存在但尚无文件。</div>
      </div>`; return;
    }
    body.innerHTML = `<div class="doc-list">
      ${data.files.map(f => `
        <div class="doc-item">
          <span class="doc-item-icon">${f.is_dir ? '📂' : docIcon(f.name)}</span>
          <div class="doc-item-info">
            <div class="doc-item-name">${f.name}</div>
            <div class="doc-item-meta">${f.is_dir ? '文件夹' : formatBytes(f.size)}</div>
          </div>
        </div>`).join('')}
    </div>`;
  }
}

// ── 10. PHOTOS APP ────────────────────────────────────────────────
class PhotosApp extends BaseApp {
  constructor(os) {
    super(os, { id:'photos', name:'相册', icon:'📸', iconBg:'#1c1c1e', headerBg:'#000' });
    this._photos  = [];
    this._viewing = null;
    this._photoIndex = 0;
    this._detailBound = false;
    this._backBound = false;
  }

  buildHTML() {
    return `<div class="app-window-inner photos-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;background:#000;">
      <div id="photos-grid-view" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
        <div class="app-header photos-header">
          <div class="app-title" style="color:#fff;">相册</div>
        </div>
        <div id="photos-grid-wrap" class="app-content photos-grid-wrap">
          <div class="state-loading" style="color:rgba(255,255,255,.4);"><div class="spinner"></div></div>
        </div>
      </div>
      <div id="photos-detail-view" style="display:none;flex:1;flex-direction:column;overflow:hidden;">
        <div class="app-header photos-header">
          <button class="app-back" id="photo-back" style="color:#007AFF;">
            <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
              <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            &nbsp;相册
          </button>
          <div id="photo-detail-title" class="app-title" style="color:#fff;font-size:15px;">照片</div>
          <div style="width:60px;"></div>
        </div>
        <div id="photo-detail-stage" class="app-content photo-detail-stage">
          <div id="photo-detail-viewport" class="photo-detail-viewport">
            <div id="photo-detail-track" class="photo-detail-track"></div>
          </div>
          <div id="photo-detail-counter" class="photo-detail-counter"></div>
          <div id="photo-detail-desc" class="photo-detail-desc"></div>
        </div>
      </div>
    </div>`;
  }

  async onOpen() {
    await this._loadPhotos();
    this._renderGrid();
    this.startPoll(async () => {
      await this._loadPhotos(true);
      this._renderGrid();
      if (this._viewing) {
        this._photoIndex = clamp(this._photoIndex, 0, Math.max(0, this._photos.length - 1));
        this._renderDetail();
      }
    });
    if (!this._backBound) {
      this._backBound = true;
      $('#photo-back', this.window)?.addEventListener('click', () => this._showGrid());
    }
    this._bindDetailViewer();
  }
  onClose() {
    this.stopPoll();
    this._viewing = null;
    this._photoIndex = 0;
    this._showGrid();
  }

  async _loadPhotos(force = false) {
    const data = await this.os.ds.get('photos', force);
    this._photos = data || [];
  }

  _renderGrid() {
    const wrap = $('#photos-grid-wrap', this.window);
    if (!wrap) return;
    if (!this._photos.length) {
      wrap.innerHTML = '<div class="photo-empty" style="color:rgba(255,255,255,.3);">📷<br>相册为空</div>'; return;
    }
    // Group by simple category
    const sections = this._groupPhotos();
    let html = '';
    for (const { label, photos } of sections) {
      html += `<div class="photo-section-title">${label}</div>
        <div class="photos-grid">
          ${photos.map((p, i) => `
            <div class="photo-thumb" data-idx="${p.__idx}">
              <img src="${p.url}" alt="${p.description}" loading="lazy" />
            </div>`).join('')}
        </div>`;
    }
    wrap.innerHTML = html;
    $$('.photo-thumb', wrap).forEach(thumb => {
      thumb.addEventListener('click', () => {
        const idx = parseInt(thumb.dataset.idx);
        this._openPhoto(idx);
      });
    });
  }

  _groupPhotos() {
    const groups = { 'CVPR 2025':[], '云南之旅':[], '生活':[] };
    this._photos.forEach((p, i) => {
      p.__idx = i;
      const name = p.filename;
      if (name.includes('cvpr')) groups['CVPR 2025'].push(p);
      else if (name.includes('云南') || name.includes('洱海') || name.includes('雪山')) groups['云南之旅'].push(p);
      else groups['生活'].push(p);
    });
    return Object.entries(groups).filter(([,v])=>v.length).map(([k,v])=>({label:k, photos:v}));
  }

  _bindDetailViewer() {
    if (this._detailBound) return;
    this._detailBound = true;

    const viewport = $('#photo-detail-viewport', this.window);
    const track = $('#photo-detail-track', this.window);
    const stage = $('#photo-detail-stage', this.window);
    if (!viewport || !track || !stage) return;

    let sx = 0;
    let sy = 0;
    let dx = 0;
    let dy = 0;
    let dragging = false;
    let mode = '';

    const resetStage = (animate = true) => {
      if (animate) viewport.style.transition = '';
      else viewport.style.transition = 'none';
      viewport.style.transform = '';
      viewport.style.opacity = '';
      if (!animate) {
        requestAnimationFrame(() => {
          viewport.style.transition = '';
        });
      }
    };

    const applyHorizontal = () => {
      track.style.transition = 'none';
      track.style.transform = `translate3d(calc(${-this._photoIndex * 100}% + ${dx}px), 0, 0)`;
    };

    const applyVertical = () => {
      const shift = clamp(dy, -220, 220);
      viewport.style.transition = 'none';
      viewport.style.transform = `translateY(${shift}px) scale(${clamp(1 - Math.abs(shift) / 900, 0.92, 1)})`;
      viewport.style.opacity = `${clamp(1 - Math.abs(shift) / 260, 0.36, 1)}`;
    };

    const finish = () => {
      if (!dragging) return;
      dragging = false;

      if (mode === 'horizontal') {
        track.style.transition = '';
        if (Math.abs(dx) > 60) {
          this._setPhotoIndex(this._photoIndex + (dx < 0 ? 1 : -1));
        } else {
          this._syncDetailPhoto();
        }
        resetStage();
      } else if (mode === 'vertical') {
        track.style.transition = '';
        if (Math.abs(dy) > 96) {
          this._showGrid();
        } else {
          this._syncDetailPhoto();
          resetStage();
        }
      } else {
        this._syncDetailPhoto();
        resetStage();
      }

      dx = 0;
      dy = 0;
      mode = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };

    const onMouseMove = (evt) => {
      if (!dragging) return;
      dx = evt.clientX - sx;
      dy = evt.clientY - sy;
      if (!mode && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
        mode = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical';
      }
      if (mode === 'horizontal') applyHorizontal();
      if (mode === 'vertical') applyVertical();
      evt.preventDefault();
    };

    const onMouseUp = () => finish();

    const onTouchMove = (evt) => {
      const touch = evt.touches?.[0];
      if (!touch || !dragging) return;
      dx = touch.clientX - sx;
      dy = touch.clientY - sy;
      if (!mode && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
        mode = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical';
      }
      if (mode === 'horizontal') applyHorizontal();
      if (mode === 'vertical') applyVertical();
      evt.preventDefault();
    };

    const onTouchEnd = () => finish();

    viewport.addEventListener('mousedown', (evt) => {
      if (!this._viewing) return;
      sx = evt.clientX;
      sy = evt.clientY;
      dx = 0;
      dy = 0;
      mode = '';
      dragging = true;
      evt.preventDefault();
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp, { once: true });
    });

    viewport.addEventListener('touchstart', (evt) => {
      const touch = evt.touches?.[0];
      if (!touch || !this._viewing) return;
      sx = touch.clientX;
      sy = touch.clientY;
      dx = 0;
      dy = 0;
      mode = '';
      dragging = true;
      window.addEventListener('touchmove', onTouchMove, { passive: false });
      window.addEventListener('touchend', onTouchEnd, { once: true });
    }, { passive: true });
  }

  _renderDetail() {
    const track = $('#photo-detail-track', this.window);
    if (!track) return;
    track.innerHTML = this._photos.map((photo) => `
      <div class="photo-detail-slide">
        <img src="${photo.url}" alt="${escapeHTML(photo.description || '照片')}" loading="lazy" />
      </div>
    `).join('');
    this._syncDetailPhoto(false);
  }

  _syncDetailPhoto(animate = true) {
    const track = $('#photo-detail-track', this.window);
    const viewport = $('#photo-detail-viewport', this.window);
    const current = this._photos[this._photoIndex];
    if (!track || !current) return;

    if (!animate) track.style.transition = 'none';
    track.style.transform = `translate3d(-${this._photoIndex * 100}%, 0, 0)`;
    if (!animate) {
      requestAnimationFrame(() => {
        track.style.transition = '';
      });
    }

    if (viewport) {
      viewport.style.transition = '';
      viewport.style.transform = '';
      viewport.style.opacity = '';
    }

    this._viewing = current;
    const title = $('#photo-detail-title', this.window);
    const counter = $('#photo-detail-counter', this.window);
    const desc = $('#photo-detail-desc', this.window);
    if (title) title.textContent = '照片';
    if (counter) counter.textContent = `${this._photoIndex + 1} / ${this._photos.length}`;
    if (desc) desc.textContent = current.description || '';
  }

  _setPhotoIndex(index) {
    if (!this._photos.length) return;
    this._photoIndex = clamp(index, 0, this._photos.length - 1);
    this._syncDetailPhoto();
  }

  _openPhoto(photoOrIndex) {
    const index = typeof photoOrIndex === 'number'
      ? photoOrIndex
      : this._photos.findIndex((photo) => photo.url === photoOrIndex?.url);
    this._photoIndex = clamp(index >= 0 ? index : 0, 0, Math.max(0, this._photos.length - 1));
    this._viewing = this._photos[this._photoIndex] || null;
    const gridV  = $('#photos-grid-view', this.window);
    const detailV = $('#photos-detail-view', this.window);
    if (gridV)  { gridV.style.display  = 'none'; }
    if (detailV){ detailV.style.display = 'flex'; }
    this._renderDetail();
  }

  _showGrid() {
    this._viewing = null;
    const gridV   = $('#photos-grid-view',  this.window);
    const detailV = $('#photos-detail-view', this.window);
    if (gridV)  { gridV.style.display   = 'flex'; }
    if (detailV){ detailV.style.display = 'none'; }
  }
}

// ── 11. 小红书 APP ────────────────────────────────────────────────
class XiaoHongShuApp extends BaseApp {
  constructor(os) {
    super(os, { id:'xiaohongshu', name:'小红书', icon:'🌹', iconBg:'#FF2442', headerBg:'#fff' });
    this._posts   = [];
    this._viewing = null;
    this._isComposing = false;
    this._photoLibrary = [];
    this._draft = null;
    this._detailIndex = 0;
  }

  buildHTML() {
    return `<div class="app-window-inner xhs-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header xhs-header">
        <div class="app-title xhs-logo">小红书</div>
      </div>
      <div id="xhs-body" class="app-content" style="background:#f5f5f5;"></div>
    </div>`;
  }

  async onOpen() {
    await Promise.all([this._loadPosts(), this._loadPhotoLibrary()]);
    this._renderFeed();
    this.startPoll(async () => {
      if (this._viewing || this._isComposing) return;
      await this._loadPosts(true);
      this._renderFeed();
    });
  }
  onClose() {
    this.stopPoll();
    this._viewing = null;
    this._isComposing = false;
    this._draft = null;
    this._detailIndex = 0;
  }

  async _loadPosts(force = false) {
    const data = await this.os.ds.get('xiaohongshu', force);
    this._posts = data || [];
  }

  async _loadPhotoLibrary(force = false) {
    const data = await this.os.ds.get('photos', force);
    this._photoLibrary = data || [];
  }

  _renderFeed() {
    const body = $('#xhs-body', this.window);
    if (!body) return;
    body.innerHTML = `
      <div class="xhs-feed-shell">
        <div class="xhs-feed-toolbar">
          <div>
            <div class="xhs-feed-title">我的笔记</div>
            <div class="xhs-feed-subtitle">发布内容会直接写回 mock_data</div>
          </div>
          <button id="xhs-compose-btn" class="xhs-compose-btn">发布</button>
        </div>
        ${this._posts.length ? `
          <div class="xhs-feed">
            ${this._posts.map((p, i) => this._postCard(p, i)).join('')}
          </div>
        ` : '<div class="xhs-empty">🌹<br>暂无笔记</div>'}
      </div>
    `;
    $('#xhs-compose-btn', body)?.addEventListener('click', () => this._openComposer());
    $$('.xhs-card', body).forEach((card, i) => {
      card.addEventListener('click', () => this._openPost(this._posts[i]));
    });
  }

  _postCard(post) {
    const tags = (post.text || '').match(/#[\u4e00-\u9fa5\w]+/g) || [];
    const preview = escapeHTML((post.text || '').replace(/#[\u4e00-\u9fa5\w]+/g, '').trim().slice(0, 80));
    const date = post.created_at ? fmtDate(post.created_at) : '';
    const cover = post.image_urls?.[0];
    return `<div class="xhs-card">
      <div class="xhs-card-img">${cover ? `<img src="${cover}" alt="${escapeHTML(post.title || '小红书封面')}" loading="lazy" />` : '🌹'}</div>
      <div class="xhs-card-body">
        <div class="xhs-card-title">${escapeHTML(post.title || '笔记')}</div>
        <div class="xhs-card-text">${preview}${preview ? '…' : ''}</div>
        <div class="xhs-card-tags">${tags.slice(0,5).map(t=>`<span class="xhs-tag">${t}</span>`).join('')}</div>
        <div class="xhs-card-meta">
          <span class="xhs-card-date">${date}</span>
          <span class="xhs-card-count">${post.image_urls?.length || 0} 图</span>
        </div>
      </div>
    </div>`;
  }

  _openPost(post) {
    this._viewing = post;
    this._isComposing = false;
    this._detailIndex = 0;
    const body = $('#xhs-body', this.window);
    if (!body) return;
    const tags = (post.text||'').match(/#[\u4e00-\u9fa5\w]+/g) || [];
    const content = escapeHTML((post.text||'').replace(/#[\u4e00-\u9fa5\w]+/g,'').trim());
    const date = post.created_at ? new Date(post.created_at).toLocaleDateString('zh-CN') : '';
    const images = (post.image_urls || []).filter(Boolean);
    body.innerHTML = `
      <div class="app-header xhs-header">
        <button class="app-back" id="xhs-back" style="color:#FF2442;">
          <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
            <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          &nbsp;小红书
        </button>
        <div class="app-title xhs-logo">笔记详情</div>
        ${post.id ? '<button id="xhs-delete-btn" class="xhs-delete-btn">删除</button>' : '<div class="xhs-header-spacer"></div>'}
      </div>
      <div class="app-content xhs-detail-scroll" style="padding:0;">
        <div class="xhs-detail-cover ${images.length > 1 ? 'is-carousel' : ''}">
          <div id="xhs-detail-viewport" class="xhs-detail-viewport">
            <div id="xhs-detail-track" class="xhs-detail-track">
              ${(images.length ? images : [null]).map((url, idx) => `
                <div class="xhs-detail-slide ${url ? '' : 'is-empty'}">
                  ${url ? `<img src="${url}" alt="${escapeHTML(`${post.title || '小红书图片'} ${idx + 1}`)}" />` : '<div class="xhs-detail-empty">🌹</div>'}
                </div>
              `).join('')}
            </div>
          </div>
          ${images.length > 1 ? `
            <div id="xhs-detail-counter" class="xhs-detail-counter">1 / ${images.length}</div>
            <div class="xhs-detail-dots">
              ${images.map((_, idx) => `<button class="xhs-detail-dot ${idx === 0 ? 'is-active' : ''}" data-index="${idx}" aria-label="查看第 ${idx + 1} 张图片"></button>`).join('')}
            </div>
          ` : ''}
        </div>
        <div class="xhs-detail">
          <div class="xhs-detail-title">${escapeHTML(post.title||'笔记')}</div>
          <div class="xhs-detail-text">${content}</div>
          <div class="xhs-card-tags" style="margin-top:12px;">${tags.map(t=>`<span class="xhs-tag">${t}</span>`).join('')}</div>
          <div class="xhs-detail-date">${date}</div>
        </div>
      </div>`;
    $('#xhs-back', this.window)?.addEventListener('click', () => {
      this._viewing = null;
      this._detailIndex = 0;
      this._renderFeed();
    });
    $('#xhs-delete-btn', this.window)?.addEventListener('click', () => this._deleteViewingPost());
    this._bindPostCarousel();
    this._syncPostCarousel(false);
  }

  _openComposer() {
    this._viewing = null;
    this._isComposing = true;
    this._draft = this._draft || { title: '', text: '', imageFilenames: [] };

    const body = $('#xhs-body', this.window);
    body.innerHTML = `
      <div class="app-header xhs-header">
        <button class="app-back" id="xhs-compose-back" style="color:#FF2442;">
          <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
            <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          &nbsp;小红书
        </button>
        <div class="app-title xhs-logo">发布笔记</div>
        <button id="xhs-publish-btn" class="xhs-publish-btn">发布</button>
      </div>
      <div class="app-content xhs-compose">
        <div class="xhs-compose-card">
          <div class="xhs-compose-label">标题</div>
          <input id="xhs-title-input" class="xhs-compose-input" type="text" maxlength="60" placeholder="给这条笔记起个标题" value="${escapeHTML(this._draft.title)}" />
        </div>
        <div class="xhs-compose-card">
          <div class="xhs-compose-label">正文</div>
          <textarea id="xhs-text-input" class="xhs-compose-textarea" placeholder="分享此刻的内容、地点、灵感或攻略">${escapeHTML(this._draft.text)}</textarea>
        </div>
        <div class="xhs-compose-card">
          <div class="xhs-compose-head">
            <div class="xhs-compose-label">选择图片</div>
            <div id="xhs-photo-count" class="xhs-photo-count">${this._draft.imageFilenames.length} / ${this._photoLibrary.length}</div>
          </div>
          <div id="xhs-selected-strip" class="xhs-selected-strip"></div>
          <div class="xhs-photo-grid">
            ${this._photoLibrary.map((photo) => `
              <button class="xhs-photo-pick ${this._draft.imageFilenames.includes(photo.filename) ? 'is-selected' : ''}" data-file="${escapeHTML(photo.filename)}">
                <img src="${photo.url}" alt="${escapeHTML(photo.description)}" loading="lazy" />
                <span class="xhs-photo-check"></span>
              </button>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    $('#xhs-compose-back', body)?.addEventListener('click', () => {
      this._isComposing = false;
      this._draft = null;
      this._renderFeed();
    });
    $('#xhs-title-input', body)?.addEventListener('input', (evt) => {
      this._draft.title = evt.target.value;
    });
    $('#xhs-text-input', body)?.addEventListener('input', (evt) => {
      this._draft.text = evt.target.value;
    });
    $('#xhs-publish-btn', body)?.addEventListener('click', () => this._publishDraft());
    $$('.xhs-photo-pick', body).forEach((btn) => {
      btn.addEventListener('click', () => this._toggleDraftPhoto(btn.dataset.file));
    });
    this._renderDraftSelection();
  }

  _toggleDraftPhoto(filename) {
    if (!this._draft) return;
    const picked = new Set(this._draft.imageFilenames);
    if (picked.has(filename)) picked.delete(filename);
    else picked.add(filename);
    this._draft.imageFilenames = [...picked];
    $$('.xhs-photo-pick', this.window).forEach((btn) => {
      btn.classList.toggle('is-selected', picked.has(btn.dataset.file));
    });
    this._renderDraftSelection();
  }

  _renderDraftSelection() {
    const strip = $('#xhs-selected-strip', this.window);
    const count = $('#xhs-photo-count', this.window);
    if (count) count.textContent = `${this._draft?.imageFilenames?.length || 0} / ${this._photoLibrary.length}`;
    if (!strip) return;

    const selected = this._photoLibrary.filter((photo) => this._draft?.imageFilenames?.includes(photo.filename));
    if (!selected.length) {
      strip.innerHTML = '<div class="xhs-selected-empty">未选择图片，发布时也可以只发文字。</div>';
      return;
    }

    strip.innerHTML = selected.map((photo) => `
      <div class="xhs-selected-thumb">
        <img src="${photo.url}" alt="${escapeHTML(photo.description)}" loading="lazy" />
      </div>
    `).join('');
  }

  async _publishDraft() {
    const title = this._draft?.title?.trim() || '';
    const text = this._draft?.text?.trim() || '';
    const imageFilenames = this._draft?.imageFilenames || [];

    if (!title && !text) {
      window.alert('请先输入标题或正文。');
      return;
    }
    if (!window.confirm('确认发布这条小红书笔记吗？')) return;

    const result = await this.os.ds.post('xiaohongshu', { title, text, image_filenames: imageFilenames });
    if (!result?.ok) {
      window.alert('发布失败，请稍后重试。');
      return;
    }

    await this._loadPosts(true);
    this._isComposing = false;
    this._draft = null;
    this._renderFeed();
    this.os.notifMgr.show({
      app: 'xiaohongshu',
      title: '小红书已发布',
      message: result.post?.title || '新笔记已写入 mock_data',
    });
  }

  _bindPostCarousel() {
    const images = this._viewing?.image_urls || [];
    const viewport = $('#xhs-detail-viewport', this.window);
    const track = $('#xhs-detail-track', this.window);
    if (!viewport || !track || images.length < 2) return;

    let dragging = false;
    let startX = 0;
    let deltaX = 0;

    const applyDrag = (clientX) => {
      if (!dragging) return;
      deltaX = clamp(clientX - startX, -180, 180);
      track.style.transition = 'none';
      track.style.transform = `translate3d(calc(${-this._detailIndex * 100}% + ${deltaX}px), 0, 0)`;
    };

    const settle = () => {
      if (!dragging) return;
      dragging = false;
      track.style.transition = '';
      if (Math.abs(deltaX) > 54) {
        this._setPostCarouselIndex(this._detailIndex + (deltaX < 0 ? 1 : -1));
      } else {
        this._syncPostCarousel();
      }
      deltaX = 0;
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };

    const onMouseMove = (evt) => {
      evt.preventDefault();
      applyDrag(evt.clientX);
    };
    const onMouseUp = () => settle();
    const onTouchMove = (evt) => {
      const touch = evt.touches?.[0];
      if (!touch) return;
      applyDrag(touch.clientX);
      evt.preventDefault();
    };
    const onTouchEnd = () => settle();

    viewport.addEventListener('mousedown', (evt) => {
      dragging = true;
      startX = evt.clientX;
      deltaX = 0;
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp, { once: true });
      evt.preventDefault();
    });
    viewport.addEventListener('touchstart', (evt) => {
      const touch = evt.touches?.[0];
      if (!touch) return;
      dragging = true;
      startX = touch.clientX;
      deltaX = 0;
      window.addEventListener('touchmove', onTouchMove, { passive: false });
      window.addEventListener('touchend', onTouchEnd, { once: true });
    }, { passive: true });

    $$('.xhs-detail-dot', this.window).forEach((dot, idx) => {
      dot.addEventListener('click', () => this._setPostCarouselIndex(idx));
    });
  }

  _syncPostCarousel(animate = true) {
    const track = $('#xhs-detail-track', this.window);
    if (track) {
      if (!animate) track.style.transition = 'none';
      track.style.transform = `translate3d(-${this._detailIndex * 100}%, 0, 0)`;
      if (!animate) {
        requestAnimationFrame(() => {
          if (track) track.style.transition = '';
        });
      }
    }

    const total = this._viewing?.image_urls?.length || 0;
    const counter = $('#xhs-detail-counter', this.window);
    if (counter) counter.textContent = `${this._detailIndex + 1} / ${total}`;
    $$('.xhs-detail-dot', this.window).forEach((dot, idx) => {
      dot.classList.toggle('is-active', idx === this._detailIndex);
    });
  }

  _setPostCarouselIndex(index) {
    const total = this._viewing?.image_urls?.length || 0;
    if (!total) return;
    this._detailIndex = clamp(index, 0, total - 1);
    this._syncPostCarousel();
  }

  async _deleteViewingPost() {
    const post = this._viewing;
    if (!post?.id) return;
    if (!window.confirm('确认删除这条小红书笔记吗？')) return;

    const result = await this.os.ds.post('xiaohongshu', {
      action: 'delete',
      id: post.id,
    });
    if (!result?.ok) {
      window.alert('删除失败，请稍后重试。');
      return;
    }

    const title = post.title || '笔记';
    await this._loadPosts(true);
    this._viewing = null;
    this._detailIndex = 0;
    this._renderFeed();
    this.os.notifMgr.show({
      app: 'xiaohongshu',
      title: '小红书已删除',
      message: title,
    });
  }
}

// ── 12. NOTES APP ─────────────────────────────────────────────────
class NotesApp extends BaseApp {
  constructor(os) {
    super(os, { id:'notes', name:'备忘录', icon:'📝', iconBg:'#FFDE01', headerBg:'#f2f2f7' });
    this._notes   = [];
    this._mode    = 'list';
    this._editing = null;
  }

  buildHTML() {
    return `<div class="app-window-inner notes-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header notes-header">
        <div class="app-title">📝&nbsp;备忘录</div>
      </div>
      <div id="notes-body" class="app-content"></div>
    </div>`;
  }

  async onOpen() {
    await this._load();
    this._renderList();
    this.startPoll(async () => {
      if (this._mode !== 'list') return;
      await this._load(true);
      this._renderList();
    });
  }
  onClose() {
    this.stopPoll();
    this._mode = 'list';
    this._editing = null;
  }

  async _load(force = false) {
    const data = await this.os.ds.get('notes', force);
    this._notes = [...(data || [])].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  }

  _renderList() {
    const body = $('#notes-body', this.window);
    if (!body) return;
    this._mode = 'list';
    body.innerHTML = `
      <div class="notes-shell">
        <div class="notes-toolbar">
          <div>
            <div class="notes-toolbar-title">最近编辑</div>
            <div class="notes-toolbar-subtitle">修改后会直接保存到 mock_data</div>
          </div>
          <button id="notes-create-btn" class="notes-create-btn">新建</button>
        </div>
        ${this._notes.length ? `
          <div class="notes-list">
            ${this._notes.map((n, i) => `
              <div class="note-item" data-idx="${i}">
                <div class="note-title">${escapeHTML(n.title || '未命名备忘录')}</div>
                <div class="note-preview">${escapeHTML((n.content || '').replace(/\s+/g, ' ').trim().slice(0,72) || '点击继续编辑内容')}</div>
                <div class="note-meta">${n.updated_at ? formatFullDate(n.updated_at) : ''}</div>
              </div>`).join('')}
          </div>
        ` : '<div class="state-loading" style="color:#aaa;">暂无备忘录</div>'}
      </div>
    `;
    $('#notes-create-btn', body)?.addEventListener('click', () => this._openEditor());
    $$('.note-item', body).forEach(item => {
      item.addEventListener('click', () => this._openEditor(this._notes[+item.dataset.idx]));
    });
  }

  _openEditor(note = null) {
    this._mode = 'editor';
    this._editing = note ? { ...note } : { id: '', title: '', content: '', updated_at: '' };
    const body = $('#notes-body', this.window);
    body.innerHTML = `
      <div class="app-header notes-header" style="border-bottom:1px solid rgba(0,0,0,.08);">
        <button class="app-back" id="note-back">
          <svg width="10" height="17" viewBox="0 0 10 17" fill="none">
            <path d="M9 1L1 8.5L9 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          &nbsp;备忘录
        </button>
        <div class="app-title">编辑备忘录</div>
        <div class="note-header-actions">
          ${this._editing.id ? '<button id="note-delete" class="note-delete-btn">删除</button>' : ''}
          <button id="note-save" class="note-save-btn">保存</button>
        </div>
      </div>
      <div class="app-content note-editor">
        <input id="note-editor-title" class="note-editor-title" type="text" maxlength="80" placeholder="标题" value="${escapeHTML(this._editing.title || '')}" />
        <div class="note-editor-meta">${this._editing.updated_at ? `上次更新 ${formatFullDate(this._editing.updated_at)}` : '新建备忘录'}</div>
        <textarea id="note-editor-content" class="note-editor-content" placeholder="记录你的想法、事项、草稿或命令...">${escapeHTML(this._editing.content || '')}</textarea>
      </div>`;
    $('#note-back', this.window)?.addEventListener('click', () => {
      this._editing = null;
      this._renderList();
    });
    $('#note-delete', this.window)?.addEventListener('click', () => this._deleteEditor());
    $('#note-save', this.window)?.addEventListener('click', () => this._saveEditor());
  }

  async _saveEditor() {
    const title = ($('#note-editor-title', this.window)?.value || '').trim() || '未命名备忘录';
    const content = ($('#note-editor-content', this.window)?.value || '').trim();
    const result = await this.os.ds.post('notes', {
      id: this._editing?.id || '',
      title,
      content,
    });

    if (!result?.ok) {
      window.alert('保存失败，请稍后重试。');
      return;
    }

    await this._load(true);
    this._editing = result.note || null;
    this.os.notifMgr.show({
      app: 'notes',
      title: '备忘录已保存',
      message: title,
    });
    this._openEditor(this._editing);
  }

  async _deleteEditor() {
    const note = this._editing;
    if (!note?.id) return;
    if (!window.confirm('确认删除这条备忘录吗？')) return;

    const result = await this.os.ds.post('notes', {
      action: 'delete',
      id: note.id,
    });
    if (!result?.ok) {
      window.alert('删除失败，请稍后重试。');
      return;
    }

    const title = note.title || '未命名备忘录';
    await this._load(true);
    this._editing = null;
    this._renderList();
    this.os.notifMgr.show({
      app: 'notes',
      title: '备忘录已删除',
      message: title,
    });
  }
}

// ── 13. 携程 APP ──────────────────────────────────────────────────
class XiechengApp extends BaseApp {
  constructor(os) {
    super(os, { id:'xiecheng', name:'携程旅行', icon:'✈️', iconBg:'#0077A8', headerBg:'#0077A8' });
    this._data   = null;
    this._tabIdx = 0;
  }

  buildHTML() {
    return `<div class="app-window-inner xiecheng-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;background:#0077A8;">
      <div class="app-header xiecheng-header">
        <div class="app-title" style="color:#fff;font-size:18px;font-weight:700;">携程旅行</div>
      </div>
      <div class="xiecheng-tabs">
        <div class="xiecheng-tab active" data-tab="0">订单</div>
        <div class="xiecheng-tab" data-tab="1">攻略</div>
        <div class="xiecheng-tab" data-tab="2">景点</div>
      </div>
      <div id="xiecheng-body" class="app-content" style="background:#f2f2f7;"></div>
    </div>`;
  }

  async onOpen() {
    this._bindTabs();
    await this._load();
    this._renderTab(this._tabIdx);
    this.startPoll(async () => { await this._load(true); this._renderTab(this._tabIdx); });
  }
  onClose() { this.stopPoll(); }

  _bindTabs() {
    $$('.xiecheng-tab', this.window).forEach(t => {
      t.addEventListener('click', () => {
        $$('.xiecheng-tab', this.window).forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        this._tabIdx = +t.dataset.tab;
        this._renderTab(this._tabIdx);
      });
    });
  }

  async _load(force = false) {
    this._data = await this.os.ds.get('xiecheng', force);
  }

  _renderTab(idx) {
    const body = $('#xiecheng-body', this.window);
    if (!body || !this._data) return;
    const tabs = ['orders','guides','attractions'];
    const key  = tabs[idx];
    const items = this._data[key] || [];

    if (!items.length) { body.innerHTML = '<div class="state-loading" style="color:#aaa;padding-top:40px;">暂无数据</div>'; return; }

    if (key === 'orders') {
      body.innerHTML = `<div class="xiecheng-list">
        ${items.map(o => this._orderCard(o)).join('')}
      </div>`;
    } else if (key === 'guides') {
      body.innerHTML = `<div class="xiecheng-list">
        ${items.map(g => `<div class="guide-card">
          <div class="guide-title">${g.content?.title || g.title || '攻略'}</div>
          <div class="guide-summary">${(g.content?.itinerary || g.content?.summary || g.content?.data || '').slice(0,160)}</div>
          <div class="guide-meta">${[
            g.content?.destination,
            g.content?.author,
          ].filter(Boolean).join(' · ')}</div>
        </div>`).join('')}
      </div>`;
    } else {
      body.innerHTML = `<div class="xiecheng-list">
        ${items.map(a => `<div class="attr-card">
          <div class="attr-name">${a.content?.name || a.title || '景点'}</div>
          <div class="attr-desc">${(a.content?.description || a.content?.data || '').slice(0,120)}</div>
          <div class="attr-meta">${[
            a.content?.city,
            a.content?.opening_hours,
          ].filter(Boolean).join(' · ')}</div>
        </div>`).join('')}
      </div>`;
    }
  }

  _orderCard(o) {
    const c    = o.content || {};
    const type = c.order_type === 'flight' ? '✈️ 机票'
      : c.order_type === 'hotel' ? '🏨 酒店'
      : c.order_type === 'train' ? '🚄 火车'
      : '🎫 门票';
    const statusMap = {
      completed: ['completed', '已完成'],
      confirmed: ['upcoming', '已确认'],
      planned: ['planned', '计划中'],
    };
    const [status, statusTxt] = statusMap[c.status] || ['upcoming', '待出行'];
    const title = c.order_type === 'flight'
      ? `${c.departure} → ${c.destination}　${c.details?.flight_no||''}`
      : c.order_type === 'hotel'
      ? `${c.destination} ${c.details?.hotel_name||''}`
      : c.order_type === 'train'
      ? `${c.departure} → ${c.destination}　${c.details?.train_no||''}`
      : `${c.details?.attraction_name || c.destination || ''}`;
    return `<div class="order-card">
      <div class="order-type">${type}</div>
      <div class="order-title">${title}</div>
      <div class="order-dates">${c.start_date||''} ${c.end_date&&c.end_date!==c.start_date?' — '+c.end_date:''}</div>
      <div class="order-status ${status}">${statusTxt}</div>
    </div>`;
  }
}

// ── 14. CALENDAR APP ──────────────────────────────────────────────
class CalendarApp extends BaseApp {
  constructor(os) {
    super(os, { id:'calendar', name:'日历', icon:'📅', iconBg:'#FF3B30', headerBg:'#fff' });
    const now = new Date();
    this._cursor = new Date(now.getFullYear(), now.getMonth(), 1);
    this._selected = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    this._events = [];
    this._swipeBound = false;
  }

  buildHTML() {
    return `<div class="app-window-inner calendar-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="calendar-shell">
        <div class="calendar-topbar">
          <div>
            <div class="calendar-caption">今天</div>
            <div id="calendar-today-label" class="calendar-today-label"></div>
          </div>
          <div class="calendar-mini-date" id="calendar-mini-date"></div>
        </div>

        <div class="calendar-header">
          <button class="calendar-nav-btn" id="calendar-prev" aria-label="上个月">‹</button>
          <div class="calendar-month-wrap">
            <div id="calendar-month-title" class="calendar-month-title"></div>
            <div class="calendar-month-sub">行程与提醒</div>
          </div>
          <button class="calendar-nav-btn" id="calendar-next" aria-label="下个月">›</button>
        </div>

        <div class="calendar-weekdays">
          <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
        </div>
        <div id="calendar-grid" class="calendar-grid"></div>
        <div id="calendar-agenda" class="calendar-agenda"></div>
      </div>
    </div>`;
  }

  async onOpen() {
    await this._load(true);
    this._render();
    $('#calendar-prev', this.window)?.addEventListener('click', () => this._shiftMonth(-1));
    $('#calendar-next', this.window)?.addEventListener('click', () => this._shiftMonth(1));
    this._bindSwipe();
    this.startPoll(async () => {
      await this._load(true);
      this._render();
    });
  }

  onClose() { this.stopPoll(); }

  async _load(force = false) {
    const data = await this.os.ds.get('xiecheng', force);
    const orders = data?.orders || [];
    this._events = [];

    for (const order of orders) {
      const c = order.content || {};
      const start = parseDateOnly(c.start_date);
      const end = parseDateOnly(c.end_date || c.start_date);
      if (!start || !end) continue;

      const title = c.order_type === 'flight'
        ? `${c.departure} → ${c.destination}`
        : c.order_type === 'hotel'
        ? `${c.details?.hotel_name || c.destination}`
        : c.order_type === 'train'
        ? `${c.departure} → ${c.destination}`
        : `${c.details?.attraction_name || c.destination || '行程'}`;

      const status = c.status || 'planned';
      const cursor = new Date(start);
      while (cursor <= end) {
        this._events.push({
          day: dateKey(cursor),
          title,
          status,
          type: c.order_type || 'ticket',
          time: c.details?.departure_time || c.details?.visit_date || '',
          raw: order,
        });
        cursor.setDate(cursor.getDate() + 1);
      }
    }
  }

  _shiftMonth(delta) {
    this._cursor = new Date(this._cursor.getFullYear(), this._cursor.getMonth() + delta, 1);
    if (!sameMonth(this._selected, this._cursor)) {
      this._selected = new Date(this._cursor.getFullYear(), this._cursor.getMonth(), 1);
    }
    this._render();
  }

  _bindSwipe() {
    if (this._swipeBound) return;
    this._swipeBound = true;
    const grid = $('#calendar-grid', this.window);
    if (!grid) return;
    let sx = 0, sy = 0, dragging = false;

    grid.addEventListener('mousedown', (e) => {
      sx = e.clientX;
      sy = e.clientY;
      dragging = true;
    });

    window.addEventListener('mouseup', (e) => {
      if (!dragging) return;
      dragging = false;
      const dx = e.clientX - sx;
      const dy = e.clientY - sy;
      if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy)) {
        this._shiftMonth(dx < 0 ? 1 : -1);
      }
    });
  }

  _render() {
    $('#calendar-today-label', this.window).textContent = formatFullDate(new Date());
    $('#calendar-mini-date', this.window).textContent = String(new Date().getDate());
    $('#calendar-month-title', this.window).textContent = monthTitle(this._cursor);

    const grid = $('#calendar-grid', this.window);
    const agenda = $('#calendar-agenda', this.window);
    if (!grid || !agenda) return;

    const first = new Date(this._cursor.getFullYear(), this._cursor.getMonth(), 1);
    const start = new Date(first);
    start.setDate(1 - first.getDay());

    const today = new Date();
    const eventMap = this._events.reduce((acc, item) => {
      (acc[item.day] ||= []).push(item);
      return acc;
    }, {});

    const cells = [];
    for (let i = 0; i < 42; i++) {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      const key = dateKey(day);
      const events = eventMap[key] || [];
      cells.push(`
        <button class="calendar-day ${sameMonth(day, this._cursor) ? '' : 'is-outside'} ${sameDay(day, today) ? 'is-today' : ''} ${sameDay(day, this._selected) ? 'is-selected' : ''}" data-day="${key}">
          <span class="calendar-day-num">${day.getDate()}</span>
          <span class="calendar-day-dots">${events.slice(0, 3).map(item => `<i class="calendar-dot is-${item.status}"></i>`).join('')}</span>
        </button>`);
    }
    grid.innerHTML = cells.join('');

    $$('.calendar-day', grid).forEach(btn => {
      btn.addEventListener('click', () => {
        const chosen = parseDateOnly(btn.dataset.day);
        if (!chosen) return;
        this._selected = chosen;
        if (!sameMonth(chosen, this._cursor)) {
          this._cursor = new Date(chosen.getFullYear(), chosen.getMonth(), 1);
        }
        this._render();
      });
    });

    const selectedEvents = eventMap[dateKey(this._selected)] || [];
    agenda.innerHTML = `
      <div class="calendar-agenda-head">
        <div class="calendar-agenda-title">${formatFullDate(this._selected)}</div>
        <div class="calendar-agenda-count">${selectedEvents.length ? `${selectedEvents.length} 条安排` : '暂无安排'}</div>
      </div>
      <div class="calendar-agenda-list">
        ${selectedEvents.length ? selectedEvents.map(item => `
          <div class="calendar-event-card">
            <div class="calendar-event-type">${item.type}</div>
            <div class="calendar-event-title">${item.title}</div>
            <div class="calendar-event-meta">${item.time || '全天'} · ${item.status}</div>
          </div>
        `).join('') : '<div class="calendar-empty">这一天没有来自 mock_data 的行程。</div>'}
      </div>`;
  }
}

// ── 15. SETTINGS APP ──────────────────────────────────────────────
class SettingsApp extends BaseApp {
  constructor(os) {
    super(os, { id:'settings', name:'设置', icon:'⚙️', iconBg:'#636366', headerBg:'#f2f2f7' });
    this._soul = null;
  }

  buildHTML() {
    return `<div class="app-window-inner settings-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header settings-header">
        <div class="app-title">设置</div>
      </div>
      <div id="settings-body" class="app-content">
        <div class="state-loading"><div class="spinner"></div></div>
      </div>
    </div>`;
  }

  async onOpen() {
    await this._load(true);
    this._render();
    this.startPoll(async () => {
      await this._load(true);
      this._render();
    });
  }

  onClose() { this.stopPoll(); }

  async _load(force = false) {
    this._soul = await this.os.ds.get('soul', force);
  }

  _render() {
    const body = $('#settings-body', this.window);
    if (!body) return;
    if (!this._soul) {
      body.innerHTML = '<div class="state-error">无法读取用户信息</div>';
      return;
    }

    const prefs = this._soul['偏好'] || [];
    const habits = this._soul['习惯'] || [];
    const name = this._soul['姓名'] || '当前用户';
    body.innerHTML = `
      <div class="settings-pane">
        <div class="settings-hero">
          <div class="settings-avatar">${avatarLetter(name)}</div>
          <div>
            <div class="settings-name">${name}</div>
            <div class="settings-sub">${this._soul['社会身份'] || '未填写身份信息'}</div>
          </div>
        </div>

        <div class="settings-group">
          <div class="settings-group-title">用户信息</div>
          <div class="settings-card">
            <div class="settings-row">
              <span>居住地</span>
              <strong>${this._soul['居住地'] || '未填写'}</strong>
            </div>
            <div class="settings-divider"></div>
            <div class="settings-row is-multiline">
              <span>性格</span>
              <strong>${this._soul['性格'] || '未填写'}</strong>
            </div>
          </div>
        </div>

        <div class="settings-group">
          <div class="settings-group-title">偏好</div>
          <div class="settings-card settings-tags">
            ${prefs.map(item => `<span class="settings-tag">${item}</span>`).join('') || '<span class="settings-empty">暂无偏好数据</span>'}
          </div>
        </div>

        <div class="settings-group">
          <div class="settings-group-title">习惯</div>
          <div class="settings-card settings-list">
            ${habits.map(item => `<div class="settings-list-item">${item}</div>`).join('') || '<div class="settings-empty">暂无习惯数据</div>'}
          </div>
        </div>

        <div class="settings-group">
          <div class="settings-group-title">关于本机</div>
          <div class="settings-card">
            <div class="settings-row"><span>设备</span><strong>ORCA Pro Max</strong></div>
            <div class="settings-divider"></div>
            <div class="settings-row"><span>前端访问</span><strong>Web / Browser</strong></div>
            <div class="settings-divider"></div>
            <div class="settings-row"><span>数据来源</span><strong>mock_data/*</strong></div>
          </div>
        </div>
      </div>`;
  }
}

// ── 16. PLACEHOLDER APP ───────────────────────────────────────────
class PlaceholderApp extends BaseApp {
  constructor(os, opts) {
    super(os, opts);
  }

  buildHTML() {
    return `<div class="app-window-inner placeholder-app" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="app-header" style="background:#f2f2f7;">
        <div class="app-title">${this.icon}&nbsp;${this.name}</div>
      </div>
      <div class="placeholder-body">
        <div class="placeholder-icon">${this.icon}</div>
        <div class="placeholder-text">${this.name}</div>
        <div class="placeholder-sub">该应用暂未接入 ORCA。<br>数据与功能持续接入中。</div>
      </div>
    </div>`;
  }
}

// ── 15. 小艺 ASSISTANT ────────────────────────────────────────────
class XiaoYiAssistant {
  constructor(os) {
    this.os         = os;
    this.screen     = $('#screen');
    this.bubble     = $('#xiaoyi-bubble');
    this.panel      = $('#xiaoyi-panel');
    this.input      = $('#xiaoyi-input');
    this.sendBtn    = $('#xiaoyi-send');
    this.closeBtn   = $('#xiaoyi-close');
    this.mask       = $('#xiaoyi-mask');
    this.dotsEl     = $('#xiaoyi-session-dots');
    this.viewport   = $('#xiaoyi-sessions-viewport');
    this.track      = $('#xiaoyi-sessions-track');
    this._open      = false;
    this._sheetMin  = 0.54;
    this._sheetDefault  = 0.70;
    this._sheetExpanded = 0.90;
    this._sheetRatio    = this._sheetDefault;

    // ── Multi-session state ──────────────────────────────────────
    // Each session: { id, cursor, messages: [], pane: <DOM el> }
    this._sessions      = [];
    this._current       = 0;   // index into _sessions
    this._pollTimer     = null;
    this._closedSessions = new Set();  // session IDs closed by the user — never re-adopt

    // ── Confirm dialog ───────────────────────────────────────────
    this._confirmDialog     = $('#confirm-dialog');
    this._confirmPromptEl   = $('#confirm-prompt');
    this._confirmDetailsEl  = $('#confirm-details');
    this._confirmYes        = $('#confirm-yes');
    this._confirmNo         = $('#confirm-no');
    this._pendingConfirm    = null;   // { sessionId }
  }

  // ─────────────────────────────────────────────────────────────
  // Bootstrap
  // ─────────────────────────────────────────────────────────────
  init() {
    this.closeBtn?.addEventListener('click',  () => this.close());
    this.mask?.addEventListener('click',      () => this.close());
    this.sendBtn?.addEventListener('click',   () => this._send());
    this.input?.addEventListener('keydown',   e => { if (e.key === 'Enter') this._send(); });

    // "Close task" button (shown when a session finishes)
    this.closeTaskBtn = $('#xiaoyi-close-task');
    this.closeTaskBtn?.addEventListener('click', () => this._closeCurrentSession());

    // confirm dialog buttons
    this._confirmYes?.addEventListener('click', () => this._respondConfirm(true));
    this._confirmNo?.addEventListener('click',  () => this._respondConfirm(false));
    this._confirmDialog?.querySelector('#confirm-overlay')
      ?.addEventListener('click', () => this._respondConfirm(false));

    // drag-to-resize sheet
    this._bindDragBar();
    // draggable bubble
    this._makeBubbleDraggable();
    this.snapToEdge(true);
    // boot with one empty default session
    this._createDefaultSession();
    // start polling
    this._startPolling();
    // bind track swipe
    this._bindTrackSwipe();
  }

  // ─────────────────────────────────────────────────────────────
  // Session management
  // ─────────────────────────────────────────────────────────────
  _createDefaultSession() {
    if (this.track) this.track.innerHTML = '';
    const pane = this._buildPane();
    this._appendWelcomeBubble(pane);
    this._sessions = [{ id: null, cursor: 0, pane }];
    this._current  = 0;
    this.track?.appendChild(pane);
    this._syncTrack();
    this._syncDots();
    this._syncInputRow();
  }

  _buildPane() {
    const pane = el('div', 'xiaoyi-session-pane');
    return pane;
  }

  _findSessionIndexById(sessionId) {
    if (!sessionId) return -1;
    return this._sessions.findIndex(session => session.id === sessionId);
  }

  _generateSessionId() {
    if (window.crypto?.randomUUID) {
      return `xiaoyi_${window.crypto.randomUUID()}`;
    }
    return `xiaoyi_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }

  _canReuseDefaultSession() {
    return this._sessions.length === 1 && !this._sessions[0]?.id;
  }

  _appendWelcomeBubble(pane) {
    const div = el('div', 'xm xm-ai');
    div.innerHTML = `<div class="xm-bubble">您好！我是小艺，您的智能助手 ✨<br>有什么可以帮您的吗？</div>`;
    pane.appendChild(div);
  }

  /** Create a new backend-linked session (after user sends a message). */
  _startSession(sessionId) {
    const pane = this._buildPane();
    const session = { id: sessionId, cursor: 0, pane };
    this._sessions.push(session);
    this.track?.appendChild(pane);
    this._current = this._sessions.length - 1;
    this._syncTrack(true);
    this._syncDots();
    return session;
  }

  _switchTo(index) {
    if (index < 0 || index >= this._sessions.length) return;
    this._current = index;
    this._syncTrack(true);
    this._syncDots();
    this._syncInputRow();
  }

  /** Sync the input row visibility.
   *  - No task: show input + send button.
   *  - Task running, no pending ask: show only "close task" button.
   *  - Task running, pending ask: show input + send (for reply) AND "close task". */
  _syncInputRow() {
    const session     = this._sessions[this._current];
    const hasTask     = !!(session?.id);
    const pendingAsk  = !!(session?._pendingAsk);
    const showInput   = !hasTask || pendingAsk;
    if (this.input)        this.input.style.display   = showInput ? '' : 'none';
    if (this.sendBtn)      this.sendBtn.style.display  = showInput ? '' : 'none';
    if (this.closeTaskBtn) this.closeTaskBtn.classList.toggle('hidden', !hasTask);
  }

  /** Cancel the backend task then remove the session from the carousel. */
  async _closeCurrentSession() {
    const idx     = this._current;
    const session = this._sessions[idx];
    if (!session) return;
    const sessionId = session.id || null;

    // If a confirm dialog is open for this session, dismiss it immediately.
    if (this._pendingConfirm?.sessionId === sessionId) {
      this._pendingConfirm = null;
      this._confirmDialog?.classList.add('hidden');
    }

    // Cancel any running backend task (also unblocks pending confirms / asks).
    if (sessionId) {
      this._closedSessions.add(sessionId);   // never re-adopt this ID
      try {
        await fetch('/api/assistant/cancel', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ session_id: sessionId }),
        });
      } catch { /* best-effort */ }
    }

    this._sessions = this._sessions.filter((item, itemIdx) => {
      const shouldRemove = sessionId ? item.id === sessionId : itemIdx === idx;
      if (shouldRemove) item.pane?.remove();
      return !shouldRemove;
    });

    if (this._sessions.length === 0) {
      this._createDefaultSession();
    } else {
      this._current = Math.min(idx, this._sessions.length - 1);
      this._syncTrack(false);
      this._syncDots();
      this._syncInputRow();
    }
  }

  /** Adopt a session that was created externally (e.g. by the AIOS listener).
   *  Creates a new pane, opens the panel, and immediately polls for messages. */
  async _adoptExternalSession(sessionId) {
    if (!sessionId || this._closedSessions.has(sessionId)) return null;

    const existingIdx = this._findSessionIndexById(sessionId);
    if (existingIdx !== -1) {
      const existing = this._sessions[existingIdx];
      this._current = existingIdx;
      this._syncTrack(true);
      this._syncDots();
      this._syncInputRow();
      if (!this._open) this.open();
      await this._pollSession(existing);
      return existing;
    }

    let session = null;
    if (this._canReuseDefaultSession()) {
      session = this._sessions[0];
      session.id = sessionId;
      session.cursor = 0;
      session._done = false;
      session._pendingAsk = null;
      session.pane.innerHTML = '';
      this._current = 0;
    } else {
      const pane = this._buildPane();
      session = { id: sessionId, cursor: 0, pane };
      this._sessions.push(session);
      this.track?.appendChild(pane);
      this._current = this._sessions.length - 1;
    }

    this._syncTrack(true);
    this._syncDots();
    this._syncInputRow();
    if (!this._open) this.open();
    // Immediately fetch any messages already queued on the server
    // (the incoming message label + content are in session.messages from server-side push).
    await this._pollSession(session);
    return session;
  }

  /** Poll one session immediately (outside the regular 1.5s tick). */
  async _pollSession(session) {
    try {
      const url = `/api/assistant/poll?session_id=${encodeURIComponent(session.id)}&cursor=${session.cursor}`;
      const r   = await fetch(url);
      if (!r.ok) return;
      const data = await r.json();
      if (!data.found) return;
      session.cursor = data.cursor;
      for (const msg of data.messages) this._renderMsg(session, msg);
      if (data.status === 'done' && !session._done) {
        session._done = true;
        this._onSessionDone(session);
      }
    } catch { /* network glitch — skip */ }
  }

  _syncTrack(animated = false) {
    if (!this.track) return;
    const offset = this._current * 100;
    if (animated) {
      this.track.style.transition = 'transform .3s cubic-bezier(.25,.46,.45,.94)';
      // clear after transition
      const clear = () => { this.track.style.transition = ''; this.track.removeEventListener('transitionend', clear); };
      this.track.addEventListener('transitionend', clear, { once: true });
    } else {
      this.track.style.transition = 'none';
    }
    this.track.style.transform = `translateX(-${offset}%)`;
  }

  _syncDots() {
    if (!this.dotsEl) return;
    this.dotsEl.innerHTML = '';
    if (this._sessions.length <= 1) return;
    this._sessions.forEach((_, i) => {
      const dot = el('div', `xsd-dot${i === this._current ? ' is-active' : ''}`);
      dot.addEventListener('click', () => this._switchTo(i));
      this.dotsEl.appendChild(dot);
    });
  }

  _currentPane() {
    return this._sessions[this._current]?.pane || null;
  }

  // ─────────────────────────────────────────────────────────────
  // Polling
  // ─────────────────────────────────────────────────────────────
  _startPolling() {
    if (this._pollTimer) clearInterval(this._pollTimer);
    this._pollTimer = setInterval(() => this._pollAll(), 1500);
  }

  async _pollAll() {
    await this._discoverSessions();
    for (const session of this._sessions) {
      if (!session.id) continue;
      if (session._done) continue;
      try {
        const url = `/api/assistant/poll?session_id=${encodeURIComponent(session.id)}&cursor=${session.cursor}`;
        const r   = await fetch(url);
        if (!r.ok) continue;
        const data = await r.json();
        if (!data.found) continue;

        session.cursor = data.cursor;
        for (const msg of data.messages) {
          this._renderMsg(session, msg);
        }
        if (data.status === 'done' && !session._done) {
          session._done = true;
          this._onSessionDone(session);
        }
      } catch { /* network glitch — skip */ }
    }
  }

  /** Detect sessions created externally (e.g. by aios_listener) and adopt them. */
  async _discoverSessions() {
    try {
      const r = await fetch('/api/assistant/sessions');
      if (!r.ok) return;
      const { sessions: list } = await r.json();
      const knownIds = new Set(this._sessions.map(s => s.id).filter(Boolean));
      for (const { id, status } of list) {
        // Only adopt sessions that are actively running and not yet known.
        // Skipping done sessions prevents stale/old sessions from being
        // re-adopted as empty pages after a page reload.
        if (status === 'running' && !knownIds.has(id) && !this._closedSessions.has(id)) {
          await this._adoptExternalSession(id);
        }
      }
    } catch { /* network glitch — skip */ }
  }

  _onSessionDone(session) {
    // Show a completion label.
    this._renderMsg(session, { type: 'system', text: '✅ 小艺已完成任务' });

    // Switch the input row to the "close task" button for this session.
    const idx = this._sessions.indexOf(session);
    if (idx === this._current) this._syncInputRow();
  }

  _renderMsg(session, msg) {
    const pane = session.pane;
    if (!pane) return;

    if (msg.type === 'system') {
      const row = el('div', 'xm xm-system');
      row.innerHTML = `<span class="xm-system-label">${escapeHTML(msg.text)}</span>`;
      pane.appendChild(row);

    } else if (msg.type === 'ai') {
      const div = el('div', 'xm xm-ai');
      const safe = DOMPurify.sanitize(
        marked.parse ? marked.parse(msg.text) : marked(msg.text),
        { USE_PROFILES: { html: true } }
      );
      div.innerHTML = `<div class="xm-bubble">${safe}</div>`;
      pane.appendChild(div);
      // open panel if not already
      if (!this._open) this.open();

    } else if (msg.type === 'confirm') {
      // Only show the dialog if this session is still active (not closed/cancelled).
      if (this._sessions.includes(session)) {
        this._showConfirmDialog(session.id, msg.prompt, msg.details, msg.extras);
      }

    } else if (msg.type === 'ask') {
      // Show the question as an AI bubble and mark the session as awaiting reply.
      const div = el('div', 'xm xm-ai');
      div.innerHTML = `<div class="xm-bubble">${escapeHTML(msg.text)}</div>`;
      pane.appendChild(div);
      session._pendingAsk = msg.id;
      if (!this._open) this.open();
      // Reveal the input box so the user can type their reply.
      const idx = this._sessions.indexOf(session);
      if (idx === this._current) this._syncInputRow();
    }

    pane.scrollTop = pane.scrollHeight;
  }

  // ─────────────────────────────────────────────────────────────
  // Confirm dialog
  // ─────────────────────────────────────────────────────────────
  _showConfirmDialog(sessionId, prompt, details, extras) {
    if (!this._confirmDialog) return;
    this._pendingConfirm = { sessionId };
    if (this._confirmPromptEl)  this._confirmPromptEl.textContent  = prompt || '';
    if (this._confirmDetailsEl) this._confirmDetailsEl.textContent = details || '';
    // Render image previews if provided (e.g. XiaoHongShu post).
    const imgContainer = $('#confirm-images');
    if (imgContainer) {
      imgContainer.innerHTML = '';
      const images = extras?.images || [];
      for (const url of images) {
        const img = document.createElement('img');
        img.src = url;
        img.className = 'confirm-img-thumb';
        imgContainer.appendChild(img);
      }
    }
    this._confirmDialog.classList.remove('hidden');
  }

  async _respondConfirm(answer) {
    if (!this._pendingConfirm) return;
    const { sessionId } = this._pendingConfirm;
    this._pendingConfirm = null;
    this._confirmDialog?.classList.add('hidden');
    const imgContainer = $('#confirm-images');
    if (imgContainer) imgContainer.innerHTML = '';
    try {
      await fetch('/api/assistant/confirm', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ session_id: sessionId, answer }),
      });
    } catch { /* best-effort */ }
    // show user choice as a system label
    const session = this._sessions.find(s => s.id === sessionId);
    if (session) {
      const label = answer ? '✅ 已确认' : '❌ 已取消';
      this._renderMsg(session, { type: 'system', text: label });
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Sending a message → reply to pending ask OR start a new AIOS session
  // ─────────────────────────────────────────────────────────────
  async _send() {
    const msg = this.input?.value?.trim();
    if (!msg) return;
    if (this.input) this.input.value = '';

    // If the current session is waiting for a free-text reply, route it back.
    const currentSession = this._sessions[this._current];
    if (currentSession?.id && currentSession._pendingAsk) {
      currentSession._pendingAsk = null;
      this._syncInputRow();   // hide input again while agent continues
      // Show user bubble in the current pane.
      const userDiv = el('div', 'xm xm-user');
      userDiv.innerHTML = `<div class="xm-bubble">${escapeHTML(msg)}</div>`;
      currentSession.pane?.appendChild(userDiv);
      currentSession.pane.scrollTop = currentSession.pane.scrollHeight;
      try {
        await fetch('/api/assistant/reply', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ session_id: currentSession.id, text: msg }),
        });
      } catch { /* best-effort */ }
      return;
    }

    // Remove the default welcome pane if it was never assigned a session
    const defaultIdx = this._sessions.findIndex(s => !s.id);
    if (defaultIdx !== -1) {
      const defaultPane = this._sessions[defaultIdx].pane;
      this._sessions.splice(defaultIdx, 1);
      defaultPane?.remove();
    }

    // Build a new pane and immediately show the user message
    const pane = this._buildPane();
    const userDiv = el('div', 'xm xm-user');
    userDiv.innerHTML = `<div class="xm-bubble">${escapeHTML(msg)}</div>`;
    pane.appendChild(userDiv);

    // Typing indicator
    const typing = el('div', 'xm xm-typing');
    typing.innerHTML = '<div class="xm-bubble">…</div>';
    pane.appendChild(typing);

    const clientSessionId = this._generateSessionId();
    const tmpSession = { id: clientSessionId, cursor: 0, pane };
    this._sessions.push(tmpSession);
    this.track?.appendChild(pane);
    this._current = this._sessions.length - 1;
    this._syncTrack(true);
    this._syncDots();
    this._syncInputRow();

    let data = null;
    try {
      const r = await fetch('/api/assistant', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: msg, session_id: clientSessionId }),
      });
      data = await r.json();
    } catch (e) {
      typing?.remove();
      this._renderMsg(tmpSession, { type: 'ai', text: `❌ 连接失败：${e.message}` });
      return;
    }

    typing?.remove();

    if (data?.session_id) {
      tmpSession.id = data.session_id;
      this._renderMsg(tmpSession, { type: 'system', text: '小艺已接收任务，正在处理…' });
      this._syncInputRow();
    } else {
      this._renderMsg(tmpSession, { type: 'ai', text: data?.message || '（未知错误）' });
    }

    this._syncDots();
  }

  // ─────────────────────────────────────────────────────────────
  // Panel open / close
  // ─────────────────────────────────────────────────────────────
  toggle() { this._open ? this.close() : this.open(); }

  open() {
    this._open = true;
    this.panel.classList.remove('hidden');
    const body = $('#xiaoyi-body');
    if (body) { body.style.transform = ''; body.style.opacity = ''; }
    this._setSheetRatio(this._sheetRatio || this._sheetDefault);
    this.input?.focus();
  }

  close() {
    this._open = false;
    const body = $('#xiaoyi-body');
    this._sheetRatio = this._sheetDefault;
    if (body) {
      body.style.transform = '';
      body.style.opacity   = '';
      body.style.height    = `${(this._sheetDefault * 100).toFixed(1)}%`;
    }
    this.panel.classList.add('hidden');
  }

  // ─────────────────────────────────────────────────────────────
  // Session track swipe (left / right)
  // ─────────────────────────────────────────────────────────────
  _bindTrackSwipe() {
    const viewport = this.viewport;
    const track = this.track;
    if (!viewport || !track) return;

    let sx = 0, sy = 0, startIdx = 0, dragging = false, moved = false, dirLocked = null;
    const THRESHOLD = 40;
    const DIR_LOCK_DIST = 8;

    const onStart = (cx, cy) => {
      sx = cx; sy = cy; startIdx = this._current;
      dragging = true; moved = false; dirLocked = null;
      track.style.transition = 'none';
    };

    // Returns true if the horizontal swipe was consumed (caller should preventDefault).
    const onMove = (cx, cy) => {
      if (!dragging) return false;
      const dx = cx - sx;
      const dy = cy - sy;

      // Lock gesture direction once the finger has moved enough.
      if (!dirLocked && (Math.abs(dx) > DIR_LOCK_DIST || Math.abs(dy) > DIR_LOCK_DIST)) {
        dirLocked = Math.abs(dx) >= Math.abs(dy) ? 'h' : 'v';
        if (dirLocked === 'v') {
          // Vertical scroll — release the drag and let the pane scroll natively.
          dragging = false;
          return false;
        }
      }

      if (dirLocked !== 'h') return false;

      if (Math.abs(dx) > 6) moved = true;
      const base = startIdx * 100;
      const w = viewport.offsetWidth || track.offsetWidth || 393;

      // Apply rubber-band resistance at boundaries so no blank space bleeds through.
      const atLeft  = startIdx === 0 && dx > 0;
      const atRight = startIdx === this._sessions.length - 1 && dx < 0;
      const effectiveDx = (atLeft || atRight) ? dx * 0.15 : dx;

      track.style.transform = `translateX(calc(-${base}% + ${clamp(effectiveDx, -w, w)}px))`;
      return true;
    };

    const onEnd = (cx) => {
      if (!dragging) return;
      dragging = false;
      const dx = cx - sx;
      if (moved && dx < -THRESHOLD) {
        if (startIdx < this._sessions.length - 1) {
          // Navigate to next existing session.
          this._current = startIdx + 1;
          this._syncInputRow();
        }
        // At last session: snap back silently.
      } else if (moved && dx > THRESHOLD && startIdx > 0) {
        this._current = startIdx - 1;
        this._syncInputRow();
      }
      this._syncTrack(true);
      this._syncDots();
    };

    // Mouse (desktop) — direction detection not needed; mouse wheel handles vertical scroll.
    viewport.addEventListener('mousedown', e => { onStart(e.clientX, e.clientY); e.preventDefault(); });
    window.addEventListener('mousemove', e => { if (dragging) onMove(e.clientX, e.clientY); });
    window.addEventListener('mouseup',   e => { if (dragging) onEnd(e.clientX); });

    // Touch — must determine direction before preventing default scroll.
    viewport.addEventListener('touchstart', e => {
      const t = e.touches[0]; if (t) onStart(t.clientX, t.clientY);
    }, { passive: true });
    viewport.addEventListener('touchmove', e => {
      const t = e.touches[0];
      if (t) {
        const consumed = onMove(t.clientX, t.clientY);
        if (consumed) e.preventDefault();
      }
    }, { passive: false });
    viewport.addEventListener('touchend', e => {
      const t = e.changedTouches[0]; if (t) onEnd(t.clientX);
    });
  }

  // ─────────────────────────────────────────────────────────────
  // Drag-bar resize / pull-down-to-close
  // ─────────────────────────────────────────────────────────────
  _bindDragBar() {
    const dragBar = $('#xiaoyi-drag-bar');
    if (!dragBar) return;
    let sy = 0, startRatio = this._sheetDefault, dragging = false;

    dragBar.addEventListener('mousedown', e => {
      if (!this._open) return;
      sy = e.clientY; startRatio = this._sheetRatio; dragging = true;
      this._setSheetRatio(this._sheetRatio, true);
      e.preventDefault();
    });

    window.addEventListener('mousemove', e => {
      if (!dragging) return;
      const body = $('#xiaoyi-body');
      const metrics = this._screenMetrics();
      if (!body || !metrics) return;
      const delta = e.clientY - sy;
      const nextRatio = clamp(startRatio - delta / metrics.height, this._sheetMin, this._sheetExpanded);
      this._sheetRatio = nextRatio;
      body.style.height = `${(nextRatio * 100).toFixed(1)}%`;
      if (delta > 0 && startRatio <= this._sheetDefault + 0.02) {
        const shift = Math.max(0, delta - 10);
        body.style.transform = `translateY(${shift}px)`;
        body.style.opacity   = `${clamp(1 - shift / 380, 0.72, 1)}`;
      } else {
        body.style.transform = '';
        body.style.opacity   = '';
      }
    });

    window.addEventListener('mouseup', e => {
      if (!dragging) return;
      dragging = false;
      const body = $('#xiaoyi-body');
      const delta = e.clientY - sy;
      if (body) body.style.transition = '';

      if (delta > 120 && startRatio <= this._sheetDefault + 0.02) { this.close(); return; }
      if (delta < -60 || this._sheetRatio > (this._sheetDefault + this._sheetExpanded) / 2) {
        this._setSheetRatio(this._sheetExpanded); return;
      }
      if (delta > 36 && startRatio > this._sheetDefault + 0.04) {
        this._setSheetRatio(this._sheetDefault); return;
      }
      const nearExp = Math.abs(this._sheetRatio - this._sheetExpanded) < Math.abs(this._sheetRatio - this._sheetDefault);
      this._setSheetRatio(nearExp ? this._sheetExpanded : this._sheetDefault);
    });
  }

  _setSheetRatio(ratio, immediate = false) {
    const body = $('#xiaoyi-body');
    this._sheetRatio = clamp(ratio, this._sheetMin, this._sheetExpanded);
    if (!body) return;
    body.style.transition = immediate ? 'none' : '';
    body.style.height     = `${(this._sheetRatio * 100).toFixed(1)}%`;
    body.style.transform  = '';
    body.style.opacity    = '';
    if (immediate) {
      requestAnimationFrame(() => { if (body) body.style.transition = ''; });
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Bubble dragging / snap-to-edge
  // ─────────────────────────────────────────────────────────────
  _screenMetrics() {
    const screen = this.screen || $('#screen');
    if (!screen) return null;
    const rect = screen.getBoundingClientRect();
    const width  = screen.clientWidth  || screen.offsetWidth  || rect.width;
    const height = screen.clientHeight || screen.offsetHeight || rect.height;
    return { screen, rect, width, height,
      scaleX: width  ? rect.width  / width  : 1,
      scaleY: height ? rect.height / height : 1 };
  }

  snapToEdge(force = false) {
    const metrics = this._screenMetrics();
    if (!metrics || !this.bubble) return;
    const bw = this.bubble.offsetWidth, bh = this.bubble.offsetHeight;
    const margin = 10, topLimit = 90, bottomLimit = 132;
    let left = this.bubble.offsetLeft, top = this.bubble.offsetTop;
    if (force && !this.bubble.style.left && !this.bubble.style.top) {
      left = metrics.width - bw - margin;
      top  = clamp(metrics.height * 0.42, topLimit, metrics.height - bh - bottomLimit);
    }
    left = left + bw / 2 < metrics.width / 2 ? margin : metrics.width - bw - margin;
    top  = clamp(top, topLimit, metrics.height - bh - bottomLimit);
    this.bubble.style.right  = 'unset';
    this.bubble.style.bottom = 'unset';
    this.bubble.style.left   = `${left}px`;
    this.bubble.style.top    = `${top}px`;
  }

  _makeBubbleDraggable() {
    let sx, sy, ox, oy, scaleX = 1, scaleY = 1, dragging = false;

    const onStart = (clientX, clientY) => {
      const m = this._screenMetrics(); if (!m) return;
      sx = clientX; sy = clientY;
      ox = this.bubble.offsetLeft; oy = this.bubble.offsetTop;
      scaleX = m.scaleX || 1; scaleY = m.scaleY || 1;
      this.bubble.style.transition = 'none';
      dragging = true;
    };

    const onMove = (clientX, clientY) => {
      if (!dragging) return;
      const m = this._screenMetrics(); if (!m) return;
      const dx = (clientX - sx) / scaleX, dy = (clientY - sy) / scaleY;
      const bw = this.bubble.offsetWidth, bh = this.bubble.offsetHeight;
      let nx = clamp(ox + dx, 0, m.width  - bw);
      let ny = clamp(oy + dy, 0, m.height - bh);
      this.bubble.style.right  = 'unset';
      this.bubble.style.bottom = 'unset';
      this.bubble.style.left   = nx + 'px';
      this.bubble.style.top    = ny + 'px';
    };

    const onEnd = (clientX, clientY) => {
      if (!dragging) return;
      dragging = false;
      this.bubble.style.transition = '';
      this.snapToEdge();
      const totalDx = Math.abs((clientX - sx) / scaleX);
      const totalDy = Math.abs((clientY - sy) / scaleY);
      if (totalDx < 8 && totalDy < 8) this.toggle();
    };

    this.bubble.addEventListener('mousedown', e => { onStart(e.clientX, e.clientY); e.preventDefault(); });
    window.addEventListener('mousemove', e => onMove(e.clientX, e.clientY));
    window.addEventListener('mouseup',   e => onEnd(e.clientX, e.clientY));

    this.bubble.addEventListener('touchstart', e => {
      const t = e.touches[0]; if (!t) return;
      onStart(t.clientX, t.clientY); e.preventDefault();
    }, { passive: false });
    window.addEventListener('touchmove', e => {
      const t = e.touches[0]; if (t) onMove(t.clientX, t.clientY);
    }, { passive: false });
    window.addEventListener('touchend', e => {
      const t = e.changedTouches[0]; if (t) onEnd(t.clientX, t.clientY);
    });
  }

  // External: open panel and inject an incoming AI message (used by notification path)
  receiveMessage(text) {
    this.open();
    const session = this._sessions[this._current];
    if (session) this._renderMsg(session, { type: 'ai', text });
  }
}

// ── 17. CONTROL CENTER ────────────────────────────────────────────
class ControlCenter {
  constructor(os) {
    this.os = os;
    this.el = $('#control-center');
    this.panel = $('#control-center-panel');
    this.mask = $('#control-center-mask');
    this.zone = $('#control-grab-zone');
    this.screen = $('#screen');
    this._open = false;
    this._toggles = { wifi: true, bluetooth: true, airplane: false, focus: false };
  }

  init() {
    this.mask?.addEventListener('click', () => this.close());
    this._bindGesture();
    this._bindControls();
    this._updateClock();
    this._applyBrightness();
    setInterval(() => this._updateClock(), 15000);
  }

  isOpen() { return this._open; }

  open() {
    this._open = true;
    this.el.classList.remove('hidden');
    requestAnimationFrame(() => this.el.classList.add('is-open'));
    this._updateClock();
  }

  close() {
    this._open = false;
    this.el.classList.remove('is-open');
    this.el.classList.add('hidden');
  }

  _bindGesture() {
    let startX = 0, startY = 0, dragging = false, openedByDrag = false;

    this.zone?.addEventListener('mousedown', (e) => {
      startX = e.clientX;
      startY = e.clientY;
      dragging = true;
      openedByDrag = false;
      e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
      if (!dragging || this._open) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (dx < -26 && dy > 28 && dy > Math.abs(dx) * 0.65) {
        dragging = false;
        openedByDrag = true;
        this.open();
      }
    });

    window.addEventListener('mouseup', (e) => {
      if (!dragging) return;
      dragging = false;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if ((dx < -18 && dy > 24 && dy > Math.abs(dx) * 0.65) || (Math.abs(dx) < 6 && Math.abs(dy) < 6 && !openedByDrag)) {
        this.open();
      }
    });
  }

  _bindControls() {
    $$('.cc-toggle', this.el).forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.toggle;
        const next = !this._toggles[key];
        this._toggles[key] = next;
        if (key === 'airplane' && next) {
          this._toggles.wifi = false;
          this._toggles.bluetooth = false;
        } else if ((key === 'wifi' || key === 'bluetooth') && next) {
          this._toggles.airplane = false;
        }
        this._renderToggles();
      });
    });

    $('#cc-brightness', this.el)?.addEventListener('input', () => this._applyBrightness());
  }

  _renderToggles() {
    $$('.cc-toggle', this.el).forEach(btn => {
      btn.classList.toggle('is-on', !!this._toggles[btn.dataset.toggle]);
    });
    const wifiChip = $('#cc-chip-wifi');
    const btChip = $('#cc-chip-bluetooth');
    if (wifiChip) wifiChip.textContent = this._toggles.wifi ? 'Wi-Fi: ORCA-LAN' : 'Wi-Fi: 已关闭';
    if (btChip) btChip.textContent = this._toggles.bluetooth ? '蓝牙: 已开启' : '蓝牙: 已关闭';
  }

  _applyBrightness() {
    const val = Number($('#cc-brightness', this.el)?.value || 78);
    if (this.screen) this.screen.style.filter = `brightness(${val / 100})`;
  }

  _updateClock() {
    const now = new Date();
    $('#cc-date', this.el).textContent = now.toLocaleDateString('zh-CN', {
      month: 'long',
      day: 'numeric',
      weekday: 'long',
    });
    $('#cc-time', this.el).textContent = now.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
    this._renderToggles();
  }
}

// ── 18. PHONE OS (MAIN CONTROLLER) ────────────────────────────────
class ORCAOS {
  constructor() {
    this.ds            = new DataService();
    this.notifMgr      = null;
    this.switcher      = null;
    this.assistant     = null;
    this.controlCenter = null;
    this._apps         = {};
    this._stack        = [];
    this._current      = null;
    this.state         = 'home';
    this._homeLayout   = null;
    this._homePage     = 0;
    this._editMode     = false;
    this._suppressIconClickUntil = 0;
    this._dragEdgeTimer = null;
    this._dragEdgeDir = 0;
    this._dragState = null;
  }

  getApp(id) { return this._apps[id]; }
  getOpenStack() { return [...this._stack]; }
  buildAppPreviewNode(app) {
    const sourceHTML = app?._snapshotHTML || app?.window?.firstElementChild?.outerHTML || '';
    return previewNodeFromHTML(sourceHTML);
  }

  _captureAppSnapshot(id) {
    const app = this._apps[id];
    const content = app?.window?.firstElementChild;
    if (!app || !content) return;
    const clone = content.cloneNode(true);
    const sourceFields = $$('input, textarea, select', content);
    const cloneFields = $$('input, textarea, select', clone);

    sourceFields.forEach((field, index) => {
      const mirror = cloneFields[index];
      if (!mirror) return;
      if (field instanceof HTMLTextAreaElement) {
        mirror.value = field.value;
        mirror.textContent = field.value;
      } else if (field instanceof HTMLSelectElement) {
        mirror.value = field.value;
        [...mirror.options].forEach((option) => {
          option.selected = option.value === field.value;
        });
      } else {
        mirror.value = field.value;
        mirror.setAttribute('value', field.value);
        if (field.type === 'checkbox' || field.type === 'radio') {
          mirror.checked = field.checked;
          if (field.checked) mirror.setAttribute('checked', 'checked');
          else mirror.removeAttribute('checked');
        }
      }
    });

    app._snapshotHTML = clone.outerHTML;
  }

  async init() {
    this._drawWallpaper();
    this._startClock();
    this.notifMgr = new NotificationManager(this);
    this.switcher = new AppSwitcher(this);
    this.assistant = new XiaoYiAssistant(this);
    this.controlCenter = new ControlCenter(this);
    this.assistant.init();
    this.controlCenter.init();

    this._registerApps();
    await this._loadIconAssets(true);
    this._loadHomeLayout();
    this._renderHomeScreen();
    this._setupHomeBar();
    this._setupHomeGestures();
    this._startNotifPolling();
    this._startIconPolling();

    window.addEventListener('resize', () => this.onResize());
    this._setupFullscreen();

    window.ORCA = {
      notify:        (n)  => this.notifMgr.show(n),
      openApp:       (id) => this.openApp(id, null),
      goHome:        ()   => this.goHome(),
      xiaoyi:        this.assistant,
      controlCenter: this.controlCenter,
    };

    console.log('%c✅ ORCA OS ready', 'color:#34C759;font-weight:bold;font-size:14px;');
  }

  _setupFullscreen() {
    const enterBtn = $('#fs-enter-btn');
    const exitPill = $('#fs-exit-pill');
    const root     = document.documentElement;

    // Scale the phone shell to fill the (full-screen) viewport while keeping proportions.
    const updateScale = () => {
      const scaleW = window.innerWidth  / 393;
      const scaleH = window.innerHeight / 852;
      root.style.setProperty('--fs-scale', Math.min(scaleW, scaleH) * 0.97);
    };

    const isFS = () => !!document.fullscreenElement;

    // React to browser fullscreen state changes (including user pressing Escape)
    document.addEventListener('fullscreenchange', () => {
      if (isFS()) {
        updateScale();                         // set scale before applying class
        document.body.classList.add('is-fullscreen');
        if (exitPill) {
          exitPill.getBoundingClientRect();    // force reflow for animation
          exitPill.classList.add('is-visible');
        }
      } else {
        exitPill?.classList.remove('is-visible');
        setTimeout(() => {
          document.body.classList.remove('is-fullscreen');
          root.style.removeProperty('--fs-scale');
        }, 280);
      }
    });

    // iOS Safari doesn't support requestFullscreen — show "Add to Home Screen" tip instead
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

    enterBtn?.addEventListener('click', () => {
      if (isIOS || !document.documentElement.requestFullscreen) {
        this.notifMgr?.show({
          app: 'system',
          title: '全屏提示',
          message: '点击底部分享按钮 → "添加到主屏幕"，即可全屏打开',
        });
        return;
      }
      root.requestFullscreen().catch(err => {
        console.warn('[FS] requestFullscreen failed:', err.message);
      });
    });

    // Exit: release browser fullscreen (Escape also works natively)
    exitPill?.addEventListener('click', () => {
      if (isFS()) document.exitFullscreen();
    });

    // Re-scale if window is resized while in fullscreen (e.g. multi-monitor)
    window.addEventListener('resize', () => { if (isFS()) updateScale(); });
  }

  _registerApps() {
    const all = [
      new SearchApp(this),
      new ContactsApp(this),
      new DocumentsApp(this),
      new PhotosApp(this),
      new XiaoHongShuApp(this),
      new NotesApp(this),
      new XiechengApp(this),
      new CalendarApp(this),
      new SettingsApp(this),
      new PlaceholderApp(this, { id:'weibo', name:'微博', icon:'🐦', iconBg:'#E6162D' }),
    ];

    for (const app of all) {
      this._apps[app.id] = app;
      const win = el('div', 'app-window');
      win.id = 'app-win-' + app.id;
      win.innerHTML = app.buildHTML();
      $('#app-layer').appendChild(win);
      app.window = win;
    }
  }

  _defaultHomeLayout() {
    return {
      pages: [
        // Page 1 — system built-in apps
        ['photos', 'notes', 'calendar', 'settings'],
        // Page 2 — social / travel
        ['xiaohongshu', 'xiecheng'],
        // Page 3 — social media
        ['weibo'],
      ],
      // Fixed dock: browser · contacts · documents
      dock: ['search', 'contacts', 'documents'],
    };
  }

  _loadHomeLayout() {
    let parsed = null;
    try {
      parsed = JSON.parse(localStorage.getItem(HOME_LAYOUT_KEY) || 'null');
    } catch {}
    this._homeLayout = this._normalizeHomeLayout(parsed || this._defaultHomeLayout());
  }

  _normalizeHomeLayout(layout) {
    const fallback = this._defaultHomeLayout();
    const pool = Object.keys(this._apps);
    const dockSource = Array.isArray(layout.dock) ? layout.dock : fallback.dock;
    const seen = new Set();
    const dock = [];

    for (const id of dockSource) {
      if (!this._apps[id] || seen.has(id) || dock.length >= 4) continue;
      dock.push(id);
      seen.add(id);
    }

    const pagesSource = Array.isArray(layout.pages) ? layout.pages : fallback.pages;
    const pages = pagesSource
      .map(page => (Array.isArray(page) ? page : []).filter(id => {
        if (!this._apps[id] || seen.has(id)) return false;
        seen.add(id);
        return true;
      }))
      .filter(page => page.length);

    if (!pages.length) pages.push([]);

    for (const id of pool) {
      if (!this._apps[id] || seen.has(id)) continue;
      pages[pages.length - 1].push(id);
      seen.add(id);
    }

    return { pages, dock };
  }

  _saveHomeLayout() {
    localStorage.setItem(HOME_LAYOUT_KEY, JSON.stringify(this._homeLayout));
  }

  _compactHomePages(pages) {
    const compacted = pages.filter(page => page.length);
    return compacted.length ? compacted : [[]];
  }

  _findHomePlacement(appId, layout = this._homeLayout) {
    const dockIndex = layout.dock.indexOf(appId);
    if (dockIndex >= 0) {
      return { location: 'dock', index: dockIndex };
    }

    for (let pageIndex = 0; pageIndex < layout.pages.length; pageIndex++) {
      const index = layout.pages[pageIndex].indexOf(appId);
      if (index >= 0) {
        return { location: 'page', pageIndex, index };
      }
    }

    return null;
  }

  _cleanupHomeLayout(preferredPage = this._homePage) {
    const pages = this._compactHomePages(this._homeLayout.pages.map(page => [...page]));
    this._homeLayout.pages = pages;
    this._homePage = clamp(preferredPage, 0, Math.max(0, pages.length - 1));
    this._saveHomeLayout();
  }

  async _loadIconAssets(force = false) {
    const aliases = {
      search: ['search'],
      contacts: ['contacts', 'contactors'],
      documents: ['documents', 'document'],
      photos: ['photos'],
      xiaohongshu: ['xiaohongshu', 'xhs'],
      notes: ['notes'],
      xiecheng: ['xiecheng', 'ctrip'],
      calendar: ['calendar'],
      settings: ['settings', 'setting'],
      weibo: ['weibo'],
    };
    const data = await this.ds.get('app-icons', force);
    const iconMap = data?.icons || {};
    let changed = false;

    for (const app of Object.values(this._apps)) {
      const next = (aliases[app.id] || [app.id]).map(key => iconMap[key]).find(Boolean) || null;
      if (app.iconUrl !== next) {
        app.iconUrl = next;
        changed = true;
      }
    }
    return changed;
  }

  _startIconPolling() {
    setInterval(async () => {
      const changed = await this._loadIconAssets(true);
      if (changed && !this._editMode) this._renderHomeScreen();
    }, CFG.POLL_ICONS);
  }

  _renderHomeScreen() {
    document.body.classList.toggle('homescreen-editing', this._editMode);
    document.body.classList.toggle('homescreen-dragging', !!this._dragState);
    const pagesEl = $('#home-pages');
    const dockEl = $('#dock-icons');
    const dotsEl = $('#page-dots');
    if (!pagesEl || !dockEl || !dotsEl) return;

    pagesEl.innerHTML = '';
    this._homeLayout.pages.forEach((ids, pageIndex) => {
      const page = el('div', 'home-page');
      page.dataset.page = pageIndex;
      const grid = el('div', 'app-grid');
      ids.forEach((id, index) => {
        const app = this._apps[id];
        if (app) grid.appendChild(this._iconEl(app, { location: 'page', pageIndex, index }));
      });
      page.appendChild(grid);
      pagesEl.appendChild(page);
    });

    dockEl.innerHTML = '';
    this._homeLayout.dock.forEach((id, index) => {
      const app = this._apps[id];
      if (app) dockEl.appendChild(this._iconEl(app, { location: 'dock', index }));
    });

    dotsEl.innerHTML = this._homeLayout.pages.map((_, index) => `
      <button class="page-dot ${index === this._homePage ? 'is-active' : ''}" data-page="${index}" aria-label="第 ${index + 1} 页"></button>
    `).join('');
    $$('.page-dot', dotsEl).forEach(btn => {
      btn.addEventListener('click', () => this._setHomePage(Number(btn.dataset.page)));
    });

    this._setHomePage(this._homePage, false);
  }

  _captureHomeIconLayout() {
    const layout = new Map();
    $$('.app-icon-wrap[data-location]').forEach((item) => {
      const rect = item.getBoundingClientRect();
      layout.set(item.dataset.appId, {
        left: rect.left,
        top: rect.top,
        location: item.dataset.location || 'page',
        page: Number(item.dataset.page || 0),
        index: Number(item.dataset.index || 0),
      });
    });
    return layout;
  }

  _homeReflowDistance(prev, next, focus = {}) {
    const focusLocation = focus.location || 'page';
    const focusPage = focus.pageIndex ?? focus.page ?? this._homePage;
    const focusIndex = focus.index ?? 0;
    const project = (entry) => {
      if (!entry) return 6;
      if (entry.location === 'dock') {
        return focusLocation === 'dock' ? Math.abs((entry.index ?? 0) - focusIndex) : 4 + (entry.index ?? 0);
      }
      const pageDistance = Math.abs((entry.page ?? focusPage) - focusPage);
      if (focusLocation === 'dock') {
        return 3 + pageDistance * 4 + (entry.index ?? 0);
      }
      if (!pageDistance) return Math.abs((entry.index ?? focusIndex) - focusIndex);
      return pageDistance * 5 + (entry.index ?? 0);
    };
    return Math.min(project(prev), project(next));
  }

  _animateHomeReflow(prevLayout, focus = {}) {
    if (!prevLayout?.size) return;
    const nextLayout = this._captureHomeIconLayout();
    const draggedId = focus.draggedAppId;

    nextLayout.forEach((next, appId) => {
      if (appId === draggedId) return;
      const prev = prevLayout.get(appId);
      if (!prev) return;

      const dx = prev.left - next.left;
      const dy = prev.top - next.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;

      const node = next.location === 'dock'
        ? $(`.app-icon-wrap[data-app-id="${appId}"][data-location="dock"][data-index="${next.index}"]`)
        : $(`.app-icon-wrap[data-app-id="${appId}"][data-location="page"][data-page="${next.page}"][data-index="${next.index}"]`);
      const motionNode = $('.app-icon-stack', node) || node;
      if (!motionNode?.animate) return;

      const distance = this._homeReflowDistance(prev, next, focus);
      const delay = Math.min(140, distance * 22);
      motionNode.animate([
        { transform: `translate(${dx}px, ${dy}px) scale(1.015)` },
        { transform: 'translate(0, 0) scale(1)' },
      ], {
        duration: 320,
        delay,
        easing: 'cubic-bezier(.22, 1, .36, 1)',
      });
    });
  }

  _iconEl(app, meta = {}) {
    const isDragging = this._dragState?.appId === app.id;
    const wrap = el('div', `app-icon-wrap ${this._editMode ? 'is-editing' : ''} ${isDragging ? 'is-drag-source' : ''}`);
    const iconClass = `app-icon ${app.iconUrl ? 'has-asset' : ''}`;
    const iconStyle = app.iconUrl ? '' : ` style="background:${app.iconBg};"`;
    wrap.dataset.appId = app.id;
    wrap.dataset.location = meta.location || 'page';
    if (meta.pageIndex !== undefined) wrap.dataset.page = meta.pageIndex;
    if (meta.index !== undefined) wrap.dataset.index = meta.index;
    wrap.innerHTML = `
      <div class="app-icon-stack">
        <div class="${iconClass}"${iconStyle}>${renderAppIconContent(app)}</div>
        <div class="app-label">${app.name}</div>
      </div>`;

    wrap.addEventListener('click', () => {
      if (Date.now() < this._suppressIconClickUntil || this._editMode || this.state !== 'home') return;
      this.openApp(app.id, $('.app-icon', wrap));
    });

    if (meta.location === 'page' || meta.location === 'dock') {
      wrap.addEventListener('mousedown', (e) => this._handleHomeIconMouseDown(e, wrap, app, meta));
    }
    return wrap;
  }

  _handleHomeIconMouseDown(e, wrap, app, meta) {
    if (e.button !== 0 || this.state !== 'home' || this.controlCenter.isOpen()) return;

    if (this._editMode) {
      this._startHomeIconDrag(e, wrap, app, meta);
      return;
    }

    const startX = e.clientX;
    const startY = e.clientY;
    const timer = setTimeout(() => {
      this._editMode = true;
      this._suppressIconClickUntil = Date.now() + 250;
      window.removeEventListener('mousemove', moveCancel);
      window.removeEventListener('mouseup', cancel);
      this._startHomeIconDrag({ clientX: startX, clientY: startY }, wrap, app, meta);
    }, 420);

    const cancel = () => {
      clearTimeout(timer);
      window.removeEventListener('mousemove', moveCancel);
      window.removeEventListener('mouseup', cancel);
    };
    const moveCancel = (evt) => {
      if (Math.abs(evt.clientX - startX) > 8 || Math.abs(evt.clientY - startY) > 8) cancel();
    };

    window.addEventListener('mousemove', moveCancel);
    window.addEventListener('mouseup', cancel, { once: true });
  }

  _startHomeIconDrag(e, wrap, app, meta) {
    const rect = wrap.getBoundingClientRect();
    const ghost = wrap.cloneNode(true);
    ghost.classList.add('app-icon-ghost');
    ghost.style.width = `${rect.width}px`;
    ghost.style.height = `${rect.height}px`;
    document.body.appendChild(ghost);

    const startPlacement = {
      location: meta.location || 'page',
      pageIndex: meta.pageIndex ?? this._homePage,
      index: meta.index ?? 0,
    };
    this._dragState = {
      appId: app.id,
      currentPlacement: startPlacement,
    };
    this._editMode = true;
    this._suppressIconClickUntil = Date.now() + 300;
    this._renderHomeScreen();

    const moveGhost = (clientX, clientY) => {
      ghost.style.left = `${clientX - rect.width / 2}px`;
      ghost.style.top = `${clientY - rect.height / 2}px`;
    };
    moveGhost(e.clientX, e.clientY);

    const onMove = (evt) => {
      moveGhost(evt.clientX, evt.clientY);
      this._maybeShiftHomePage(evt.clientX);
      const nextPlacement = this._detectHomeDropTarget(evt.clientX, evt.clientY, app.id);
      if (!this._dragState) return;
      const current = this._dragState.currentPlacement;
      const sameTarget = current.location === nextPlacement.location
        && current.index === nextPlacement.index
        && (current.location === 'dock' || current.pageIndex === nextPlacement.pageIndex);
      if (!sameTarget) {
        const prevLayout = this._captureHomeIconLayout();
        const moved = this._moveHomeItem(current, nextPlacement, app.id);
        this._dragState.currentPlacement = moved;
        this._renderHomeScreen();
        this._animateHomeReflow(prevLayout, {
          ...moved,
          draggedAppId: app.id,
        });
      }
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      clearTimeout(this._dragEdgeTimer);
      this._dragEdgeTimer = null;
      this._dragEdgeDir = 0;
      ghost.remove();
      const preferredPage = this._dragState?.currentPlacement?.pageIndex ?? this._homePage;
      this._dragState = null;
      this._cleanupHomeLayout(preferredPage);
      this._renderHomeScreen();
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp, { once: true });
  }

  _maybeShiftHomePage(clientX) {
    const screenRect = $('#screen').getBoundingClientRect();
    const edge = 42;
    let dir = 0;
    if (clientX < screenRect.left + edge) dir = -1;
    if (clientX > screenRect.right - edge) dir = 1;

    if (!dir) {
      clearTimeout(this._dragEdgeTimer);
      this._dragEdgeTimer = null;
      this._dragEdgeDir = 0;
      return;
    }

    if (this._dragEdgeTimer && this._dragEdgeDir === dir) return;
    clearTimeout(this._dragEdgeTimer);
    this._dragEdgeDir = dir;
    this._dragEdgeTimer = setTimeout(() => {
      if (dir > 0 && this._dragState && this._homePage >= this._homeLayout.pages.length - 1) {
        this._homeLayout.pages.push([]);
        this._saveHomeLayout();
        this._renderHomeScreen();
      }
      this._setHomePage(this._homePage + dir);
      this._dragEdgeTimer = null;
    }, 280);
  }

  _computeDropIndex(pageIndex, clientX, clientY, appId) {
    const page = $(`.home-page[data-page="${pageIndex}"]`, document);
    const items = page
      ? $$('.app-icon-wrap[data-location="page"]', page).filter(item => item.dataset.appId !== appId)
      : [];
    if (!items.length) return 0;

    let bestItem = items[0];
    let bestDist = Number.POSITIVE_INFINITY;
    for (const item of items) {
      const r = item.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dist = Math.hypot(clientX - cx, clientY - cy);
      if (dist < bestDist) {
        bestDist = dist;
        bestItem = item;
      }
    }

    const rect = bestItem.getBoundingClientRect();
    const index = Number(bestItem.dataset.index || 0);
    const after = clientY > rect.top + rect.height * 0.65 || clientX > rect.left + rect.width / 2;
    return index + (after ? 1 : 0);
  }

  _computeDockDropIndex(clientX, appId) {
    const dock = $('#dock-icons', document);
    const items = dock
      ? $$('.app-icon-wrap[data-location="dock"]', dock).filter(item => item.dataset.appId !== appId)
      : [];
    if (!items.length) return 0;

    let bestItem = items[0];
    let bestDist = Number.POSITIVE_INFINITY;
    for (const item of items) {
      const rect = item.getBoundingClientRect();
      const center = rect.left + rect.width / 2;
      const dist = Math.abs(clientX - center);
      if (dist < bestDist) {
        bestDist = dist;
        bestItem = item;
      }
    }

    const rect = bestItem.getBoundingClientRect();
    const index = Number(bestItem.dataset.index || 0);
    return clientX > rect.left + rect.width * 0.58 ? index + 1 : index;
  }

  _detectHomeDropTarget(clientX, clientY, appId) {
    const dockRect = $('#dock')?.getBoundingClientRect();
    const currentPlacement = this._findHomePlacement(appId);
    const dockWithoutDragged = this._homeLayout.dock.filter(id => id !== appId);
    const canUseDock = currentPlacement?.location === 'dock' || dockWithoutDragged.length < 4;
    const inDockZone = dockRect
      && clientX >= dockRect.left - 14
      && clientX <= dockRect.right + 14
      && clientY >= dockRect.top - 26
      && clientY <= dockRect.bottom + 18;

    if (canUseDock && inDockZone) {
      return {
        location: 'dock',
        index: this._computeDockDropIndex(clientX, appId),
      };
    }

    return {
      location: 'page',
      pageIndex: this._homePage,
      index: this._computeDropIndex(this._homePage, clientX, clientY, appId),
    };
  }

  _moveHomeItem(fromPlacement, toPlacement, appId) {
    const pages = this._homeLayout.pages.map(page => page.filter(id => id !== appId));
    const dock = this._homeLayout.dock.filter(id => id !== appId);

    if (toPlacement.location === 'dock') {
      if (dock.length >= 4) return fromPlacement;
      const finalIndex = clamp(toPlacement.index, 0, dock.length);
      dock.splice(finalIndex, 0, appId);
      this._homeLayout = {
        pages: this._compactHomePages(pages),
        dock,
      };
      this._homePage = clamp(this._homePage, 0, Math.max(0, this._homeLayout.pages.length - 1));
      this._saveHomeLayout();
      return { location: 'dock', index: finalIndex };
    }

    while (pages.length <= toPlacement.pageIndex) pages.push([]);
    const insertList = pages[toPlacement.pageIndex];
    const finalIndex = clamp(toPlacement.index, 0, insertList.length);
    insertList.splice(finalIndex, 0, appId);
    this._homeLayout = {
      pages: this._compactHomePages(pages),
      dock,
    };
    const finalPlacement = this._findHomePlacement(appId, this._homeLayout) || { location: 'page', pageIndex: 0, index: 0 };
    this._homePage = clamp(finalPlacement.pageIndex ?? this._homePage, 0, Math.max(0, this._homeLayout.pages.length - 1));
    this._saveHomeLayout();
    return finalPlacement;
  }

  _setHomePage(index, animate = true) {
    this._homePage = clamp(index, 0, Math.max(0, this._homeLayout.pages.length - 1));
    const pagesEl = $('#home-pages');
    if (!pagesEl) return;
    pagesEl.style.transition = animate ? '' : 'none';
    pagesEl.style.transform = `translateX(${-this._homePage * 100}%)`;
    $$('.page-dot', document).forEach((dot, i) => dot.classList.toggle('is-active', i === this._homePage));
    if (!animate) requestAnimationFrame(() => { pagesEl.style.transition = ''; });
  }

  _setupHomeGestures() {
    const wrap = $('#home-pages-wrap');
    if (!wrap) return;
    let startX = 0, startY = 0, dragging = false;

    // ── shared logic ─────────────────────────────────────────────
    const onDragStart = (x, y) => { startX = x; startY = y; dragging = true; };

    const onDragMove = (x, y) => {
      if (!dragging) return false;
      const dx = x - startX;
      const dy = y - startY;
      // Once we know it's more vertical than horizontal, give up
      if (Math.abs(dy) > Math.abs(dx)) { dragging = false; return false; }
      if (Math.abs(dx) <= 6) return true;
      const pagesEl = $('#home-pages');
      pagesEl.style.transition = 'none';
      pagesEl.style.transform = `translateX(calc(${-this._homePage * 100}% + ${(dx / wrap.clientWidth) * 100}%))`;
      return true; // consumed as horizontal swipe
    };

    const onDragEnd = (x, y) => {
      if (!dragging) return;
      dragging = false;
      const dx = x - startX;
      const dy = y - startY;
      const pagesEl = $('#home-pages');
      pagesEl.style.transition = '';
      if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy)) {
        this._homePage = clamp(this._homePage + (dx < 0 ? 1 : -1), 0, this._homeLayout.pages.length - 1);
        this._suppressIconClickUntil = Date.now() + 240;
      }
      this._setHomePage(this._homePage);
    };

    // ── Mouse events (desktop) ────────────────────────────────────
    wrap.addEventListener('mousedown', (e) => {
      if (this.state !== 'home' || this._editMode || this.controlCenter.isOpen() || e.target.closest('.app-icon-wrap')) return;
      onDragStart(e.clientX, e.clientY);
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => { if (dragging) onDragMove(e.clientX, e.clientY); });
    window.addEventListener('mouseup',   (e) => { onDragEnd(e.clientX, e.clientY); });

    // ── Touch events (mobile / iOS Safari) ───────────────────────
    wrap.addEventListener('touchstart', (e) => {
      if (this.state !== 'home' || this._editMode || this.controlCenter.isOpen() || e.target.closest('.app-icon-wrap')) return;
      const t = e.touches[0];
      onDragStart(t.clientX, t.clientY);
    }, { passive: true });

    wrap.addEventListener('touchmove', (e) => {
      if (!dragging) return;
      const t = e.touches[0];
      const consumed = onDragMove(t.clientX, t.clientY);
      if (consumed) e.preventDefault(); // block browser page-scroll only for horizontal swipes
    }, { passive: false });

    wrap.addEventListener('touchend', (e) => {
      const t = e.changedTouches[0];
      onDragEnd(t.clientX, t.clientY);
    }, { passive: true });

    // ── Exit edit mode on outside tap ────────────────────────────
    document.addEventListener('mousedown', (e) => {
      if (!this._editMode || this.state !== 'home' || this._dragState) return;
      if (e.target.closest('.app-icon-wrap') || e.target.closest('#dock') || e.target.closest('#page-dots')) return;
      this._editMode = false;
      this._renderHomeScreen();
    });
  }

  openApp(id, fromEl) {
    const app = this._apps[id];
    if (!app) return;

    if (this._editMode) {
      this._editMode = false;
      this._renderHomeScreen();
    }
    if (this.controlCenter.isOpen()) this.controlCenter.close();
    if (this.state === 'switcher') this.switcher.hide();
    if (this._current && this._current !== id) this.closeApp(this._current);

    if (fromEl) {
      const iR = fromEl.getBoundingClientRect();
      const sR = $('#screen').getBoundingClientRect();
      const ox = ((iR.left + iR.width / 2 - sR.left) / sR.width * 100).toFixed(1);
      const oy = ((iR.top + iR.height / 2 - sR.top) / sR.height * 100).toFixed(1);
      app.window.style.transformOrigin = `${ox}% ${oy}%`;
    } else {
      app.window.style.transformOrigin = '50% 90%';
    }

    this._stack = this._stack.filter(x => x !== id);
    this._stack.push(id);
    this._current = id;
    this.state = 'app';

    app.window.classList.remove('is-closing');
    requestAnimationFrame(() => {
      requestAnimationFrame(() => app.window.classList.add('is-open'));
    });
    app.onOpen();
  }

  closeApp(id, removeFromStack = false) {
    const app = this._apps[id];
    if (!app) return;

    const wasOpen = app.window.classList.contains('is-open');
    this._captureAppSnapshot(id);
    app.window.classList.remove('is-open');

    if (wasOpen) {
      app.window.classList.add('is-closing');
      setTimeout(() => {
        app.window.classList.remove('is-closing');
        if (removeFromStack) this._stack = this._stack.filter(x => x !== id);
        app.onClose();
      }, 380);
    } else {
      if (removeFromStack) this._stack = this._stack.filter(x => x !== id);
      app.onClose();
    }

    if (this._current === id) this._current = null;
    if (this.state !== 'switcher') this.state = 'home';
  }

  dismissFromSwitcher(id) {
    this._stack = this._stack.filter(x => x !== id);
    const app = this._apps[id];
    if (app) {
      this._captureAppSnapshot(id);
      app.window.classList.remove('is-open', 'is-closing');
      app.onClose();
    }
    if (this._current === id) this._current = null;
  }

  goHome() {
    if (this._current) this.closeApp(this._current);
    if (this.state === 'switcher') this.switcher.hide();
    if (this.controlCenter.isOpen()) this.controlCenter.close();
    this.state = 'home';
  }

  showSwitcher() {
    if (!this._stack.length && !this._current) return;
    if (this.controlCenter.isOpen()) this.controlCenter.close();
    if (this._current) this.closeApp(this._current);
    this.state = 'switcher';
    this.switcher.show(this._stack);
  }

  _setupHomeBar() {
    const bar  = $('#home-bar');
    const pill = $('#home-pill');
    let startY = 0, dragging = false;

    // ── shared logic ─────────────────────────────────────────────
    const onStart = (y) => { startY = y; dragging = true; };

    const onMove = (y) => {
      if (!dragging) return;
      const delta = startY - y;
      if (delta > 10) {
        pill.style.width   = Math.min(180, 134 + delta * 0.3) + 'px';
        pill.style.opacity = '0.65';
      }
    };

    const onEnd = (y) => {
      if (!dragging) return;
      dragging = false;
      pill.style.width   = '134px';
      pill.style.opacity = '';
      const delta = startY - y;
      if (delta > 80) {
        if (this.state === 'app' || (this.state === 'home' && this._stack.length)) this.showSwitcher();
        else if (this.state === 'switcher') this.goHome();
      } else if (delta > 30) {
        if (this.state === 'app') this.goHome();
        else if (this.state === 'home' && this._stack.length) this.showSwitcher();
        else if (this.state === 'switcher') this.goHome();
      }
    };

    // ── Mouse (desktop) ───────────────────────────────────────────
    bar.addEventListener('mousedown', e => { onStart(e.clientY); e.preventDefault(); });
    window.addEventListener('mousemove', e => onMove(e.clientY));
    window.addEventListener('mouseup',   e => onEnd(e.clientY));

    // ── Touch (mobile / iOS Safari) ───────────────────────────────
    bar.addEventListener('touchstart', e => {
      onStart(e.touches[0].clientY);
    }, { passive: true });

    // Listen on window so fast upward swipes aren't lost outside the bar
    window.addEventListener('touchmove', e => {
      if (!dragging) return;
      onMove(e.touches[0].clientY);
      e.preventDefault();   // prevent page bounce during upward swipe
    }, { passive: false });

    window.addEventListener('touchend', e => {
      onEnd(e.changedTouches[0].clientY);
    }, { passive: true });
  }

  _startClock() {
    const update = () => {
      const now = new Date();
      const hh  = String(now.getHours()).padStart(2,'0');
      const mm  = String(now.getMinutes()).padStart(2,'0');
      const el  = $('#status-time');
      if (el) el.textContent = `${hh}:${mm}`;
    };
    update();
    setInterval(update, 15000);
  }

  _drawWallpaper() {
    const canvas = $('#wallpaper-canvas');
    if (!canvas) return;
    const w = canvas.offsetWidth  || 381;
    const h = canvas.offsetHeight || 840;
    canvas.width  = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');

    const base = ctx.createLinearGradient(0, 0, w, h);
    base.addColorStop(0,   '#0d0824');
    base.addColorStop(0.5, '#160d30');
    base.addColorStop(1,   '#040618');
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, w, h);

    const blobs = [
      { x:0.25, y:0.25, r:0.45, c:'rgba(88,40,180,0.45)' },
      { x:0.75, y:0.55, c:'rgba(30,80,200,0.38)', r:0.4  },
      { x:0.5,  y:0.8,  c:'rgba(120,20,140,0.32)', r:0.5  },
      { x:0.1,  y:0.7,  c:'rgba(20,120,150,0.22)', r:0.3  },
    ];
    for (const b of blobs) {
      const rx = b.x * w, ry = b.y * h, rr = b.r * Math.max(w,h);
      const g = ctx.createRadialGradient(rx, ry, 0, rx, ry, rr);
      g.addColorStop(0,   b.c);
      g.addColorStop(1,   'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }

    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    for (let i = 0; i < 80; i++) {
      const sx = Math.random() * w;
      const sy = Math.random() * h;
      const sr = Math.random() * 1.2;
      ctx.beginPath();
      ctx.arc(sx, sy, sr, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _startNotifPolling() {
    // Poll OS notifications (popups)
    setInterval(async () => {
      try {
        const data = await this.ds.get('notifications', true);
        for (const n of data?.notifications || []) this.notifMgr.show(n);
      } catch {}
    }, CFG.POLL_NOTIF);

    // Poll pending D2D messages (user confirms before 小艺 handles)
    this._pendingD2D = null;  // currently shown pending D2D
    this._d2dDialog       = $('#d2d-confirm');
    this._d2dSenderEl     = $('#d2d-confirm-sender');
    this._d2dContentEl    = $('#d2d-confirm-content');
    this._d2dYes          = $('#d2d-confirm-yes');
    this._d2dNo           = $('#d2d-confirm-no');
    this._d2dOverlay      = $('#d2d-confirm-overlay');

    this._d2dYes?.addEventListener('click', () => this._respondD2D(true));
    this._d2dNo?.addEventListener('click', () => this._respondD2D(false));
    this._d2dOverlay?.addEventListener('click', () => this._respondD2D(false));

    setInterval(async () => {
      if (this._pendingD2D) return;  // already showing a dialog
      try {
        const r = await fetch('/api/d2d/pending');
        if (!r.ok) return;
        const { pending } = await r.json();
        if (pending?.length > 0) {
          this._showD2DConfirm(pending[0]);
        }
      } catch {}
    }, CFG.POLL_NOTIF);
  }

  _showD2DConfirm(item) {
    if (!this._d2dDialog) return;
    this._pendingD2D = item;
    if (this._d2dSenderEl)  this._d2dSenderEl.textContent  = item.display_sender ? `来自 ${item.display_sender} 的消息` : '收到新消息';
    if (this._d2dContentEl) this._d2dContentEl.textContent = item.display_content || '';
    this._d2dDialog.classList.remove('hidden');
  }

  async _respondD2D(accept) {
    const item = this._pendingD2D;
    if (!item) return;
    this._pendingD2D = null;
    this._d2dDialog?.classList.add('hidden');
    try {
      if (accept) {
        const r = await fetch('/api/d2d/accept', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ pending_id: item.id }),
        });
        const data = await r.json();
        // Immediately adopt the newly created session so the user sees
        // the chat pane with messages right away (instead of waiting for
        // the next _discoverSessions poll cycle).
        if (data?.session_id && this.assistant) {
          await this.assistant._adoptExternalSession(data.session_id);
        }
      } else {
        await fetch('/api/d2d/dismiss', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ pending_id: item.id }),
        });
      }
    } catch { /* best-effort */ }
  }

  onResize() {
    this._drawWallpaper();
    this._setHomePage(this._homePage, false);
    this.assistant?.snapToEdge?.(true);
  }
}

// ── 17. INIT ──────────────────────────────────────────────────────
const os = new ORCAOS();

// Scale phone to fit viewport — called on load, resize, and fullscreen-exit.
function fitPhone() {
  const phone = document.getElementById('phone');
  if (!phone) return;

  // Mobile full-screen (≤479 px): CSS media query takes over, hands off.
  if (window.innerWidth <= 479) {
    phone.style.transform  = '';
    phone.style.marginBlock = '';
    return;
  }

  // True browser fullscreen: _setupFullscreen() manages its own scale.
  if (document.fullscreenElement) return;

  const vw     = window.innerWidth;
  const vh     = window.innerHeight;
  const PW     = 393;
  const PH     = 852;
  const margin = 32;   // breathing room on each side
  const scale  = Math.min(1, (vw - margin) / PW, (vh - margin) / PH);

  if (scale < 1) {
    phone.style.transform   = `scale(${scale.toFixed(4)})`;
    // ── KEY FIX ────────────────────────────────────────────────────
    // transform: scale() shrinks the visual size but NOT the layout box.
    // The flex parent still thinks phone is 852 px tall and centres it
    // accordingly, pushing the top off-screen.
    // Adding a negative margin-block equal to the "lost" space fixes this:
    //   visual height  = scale × PH
    //   layout height  = PH  (unchanged)
    //   excess space   = (1 – scale) × PH  →  half on each side
    //   fix: margin    = (scale – 1) × PH / 2   (a negative value)
    phone.style.marginBlock = `${((scale - 1) * PH / 2).toFixed(1)}px`;
  } else {
    phone.style.transform   = '';
    phone.style.marginBlock = '';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await os.init();
  fitPhone();

  // Draw wallpaper after layout is settled
  setTimeout(() => os.onResize(), 100);
});

window.addEventListener('resize', fitPhone);

// Re-fit after exiting browser fullscreen
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) fitPhone();
});
