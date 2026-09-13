/* Cart, order payload and delivery. Shared by index.html and kitchen.html.
   Depends on menu.js (MENU, VENUE) and config.js (CONFIG).                     */

const STORE = {
  cart: "mastara.cart",
  table: "mastara.table",
  orders: "mastara.orders",   // everything placed on this device
  queue: "mastara.queue",     // placed but not yet accepted by the endpoint
};

/* localStorage throws in private mode and in some embedded webviews — never let
   a storage failure take the menu down with it. */
function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch { return fallback; }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; }
  catch { return false; }
}

function money(n) {
  return `${CONFIG.currencySymbol} ${Math.round(n).toLocaleString("en-PK")}`;
}

/* ------------------------------------------------------------------- table */
const Table = {
  get: () => read(STORE.table, ""),
  set(value) {
    const clean = String(value || "").trim().toUpperCase().replace(/[^A-Z0-9-]/g, "").slice(0, 6);
    write(STORE.table, clean);
    return clean;
  },
};

/* -------------------------------------------------------------------- cart */
const listeners = [];

const Cart = {
  items() {
    // Drop anything whose dish no longer exists (menu edited since the guest's
    // last visit) so a stale cart can never produce a bogus line on a ticket.
    return read(STORE.cart, []).filter(i => MENU.some(d => d.slug === i.slug));
  },
  save(items) {
    write(STORE.cart, items);
    listeners.forEach(fn => fn());
  },
  onChange(fn) { listeners.push(fn); },

  qtyOf(slug) {
    return this.items().find(i => i.slug === slug)?.qty || 0;
  },
  add(slug, qty = 1) {
    if (!MENU.some(d => d.slug === slug)) return;
    const items = this.items();
    const line = items.find(i => i.slug === slug);
    if (line) line.qty = Math.min(CONFIG.maxQtyPerItem, line.qty + qty);
    else items.push({ slug, qty: Math.min(CONFIG.maxQtyPerItem, Math.max(1, qty)) });
    this.save(items);
  },
  setQty(slug, qty) {
    const items = this.items().filter(i => i.slug !== slug);
    const n = Math.min(CONFIG.maxQtyPerItem, Math.max(0, Math.round(qty)));
    if (n > 0) items.push({ slug, qty: n });
    this.save(items);
  },
  remove(slug) { this.save(this.items().filter(i => i.slug !== slug)); },
  clear() { this.save([]); },

  count() { return this.items().reduce((n, i) => n + i.qty, 0); },

  lines() {
    return this.items().map(i => {
      const dish = MENU.find(d => d.slug === i.slug);
      const unitPrice = Number(dish.price) || 0;
      return {
        slug: dish.slug,
        name: dish.name,
        category: dish.cat,
        unitPrice,
        qty: i.qty,
        lineTotal: unitPrice * i.qty,
      };
    });
  },

  totals() {
    const subtotal = this.lines().reduce((s, l) => s + l.lineTotal, 0);
    const tax = Math.round(subtotal * (CONFIG.taxPercent || 0) / 100);
    const service = Math.round(subtotal * (CONFIG.servicePercent || 0) / 100);
    return {
      subtotal,
      taxPercent: CONFIG.taxPercent || 0, tax,
      servicePercent: CONFIG.servicePercent || 0, service,
      total: subtotal + tax + service,
    };
  },
};

/* ------------------------------------------------------------------- order */
function orderId(table) {
  const d = new Date();
  const stamp = String(d.getDate()).padStart(2, "0") + String(d.getHours()).padStart(2, "0")
              + String(d.getMinutes()).padStart(2, "0");
  const rand = Math.random().toString(36).slice(2, 5).toUpperCase();
  return `MST-${table || "NA"}-${stamp}-${rand}`;
}

const Order = {
  /** Validate before building. Returns [] when the order is good to send. */
  problems({ table, guest }) {
    const out = [];
    if (CONFIG.requireTable && !String(table || "").trim()) out.push("Please enter your table number.");
    if (!Cart.items().length) out.push("Your order is empty.");
    if (guest?.phone && !/^[+0-9][0-9\s-]{6,17}$/.test(guest.phone)) out.push("That phone number doesn't look right.");
    return out;
  },

  build({ table, guest = {}, note = "" }) {
    return {
      orderId: orderId(table),
      placedAt: new Date().toISOString(),
      venue: VENUE.name,
      source: "qr-3d-menu",
      table: String(table || "").trim(),
      guest: { name: (guest.name || "").trim().slice(0, 60), phone: (guest.phone || "").trim().slice(0, 20) },
      note: (note || "").trim().slice(0, 400),
      currency: CONFIG.currency,
      items: Cart.lines(),
      totals: Cart.totals(),
    };
  },

  /** Plain-text ticket — used for WhatsApp, printing and the kitchen screen. */
  ticketText(o) {
    const lines = o.items.map(l =>
      `${l.qty} x ${l.name}${l.unitPrice ? "  —  " + money(l.lineTotal) : ""}`);
    const t = o.totals;
    const extras = [
      t.tax ? `Tax (${t.taxPercent}%): ${money(t.tax)}` : "",
      t.service ? `Service (${t.servicePercent}%): ${money(t.service)}` : "",
    ].filter(Boolean);
    return [
      `${VENUE.name} — new order`,
      `Table ${o.table || "—"}   ·   ${o.orderId}`,
      new Date(o.placedAt).toLocaleString("en-PK"),
      "",
      ...lines,
      "",
      ...extras,
      t.total ? `TOTAL: ${money(t.total)}` : "",
      o.guest.name ? `Guest: ${o.guest.name}` : "",
      o.guest.phone ? `Phone: ${o.guest.phone}` : "",
      o.note ? `Note: ${o.note}` : "",
    ].filter(l => l !== "").join("\n");
  },

  whatsappLink(o) {
    return `https://wa.me/${VENUE.whatsapp}?text=${encodeURIComponent(this.ticketText(o))}`;
  },

  /** POST the order to the configured system. Never throws. */
  async send(o) {
    const { url, method, headers, timeoutMs } = CONFIG.orderEndpoint;
    this.remember(o, url ? "sending" : "local");

    if (!url) return { ok: true, via: "local" };

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs || 8000);
    try {
      const res = await fetch(url, {
        method: method || "POST",
        headers: { "Content-Type": "application/json", ...(headers || {}) },
        body: JSON.stringify(o),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.remember(o, "sent");
      this.dequeue(o.orderId);
      return { ok: true, via: "endpoint" };
    } catch (err) {
      // The kitchen not answering must never lose the guest's order.
      this.enqueue(o);
      this.remember(o, "queued");
      return { ok: false, via: "queue", error: String(err.message || err) };
    } finally {
      clearTimeout(timer);
    }
  },

  /* ---- local record keeping ---- */
  remember(o, status) {
    const all = read(STORE.orders, []).filter(x => x.orderId !== o.orderId);
    all.unshift({ ...o, status });
    write(STORE.orders, all.slice(0, 50));
  },
  history: () => read(STORE.orders, []),
  updateStatus(orderId, status) {
    const all = read(STORE.orders, []).map(o => o.orderId === orderId ? { ...o, status } : o);
    write(STORE.orders, all);
  },

  enqueue(o) {
    const q = read(STORE.queue, []).filter(x => x.orderId !== o.orderId);
    q.push(o);
    write(STORE.queue, q.slice(-20));
  },
  dequeue(orderId) {
    write(STORE.queue, read(STORE.queue, []).filter(o => o.orderId !== orderId));
  },

  /** Retry anything the endpoint refused earlier. Called on page load. */
  async flushQueue() {
    if (!CONFIG.orderEndpoint.url) return;
    for (const o of read(STORE.queue, [])) await this.send(o);
  },
};
