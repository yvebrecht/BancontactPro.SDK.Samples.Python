// Browser side of the sample UI. Shared, unchanged, by the TypeScript, Python and PHP samples: they all serve the same JSON API
//   GET /api/debug, POST /api/debug/clear, POST /api/payments, GET|DELETE /api/payments/{product}/{id}, GET /api/callbacks
// Everything from the servers is written with textContent, never as HTML.
const FINAL = ['SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED', 'AUTHORIZATION_FAILED', 'VOIDED'];

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

const badge = (status) => el('span', { class: `badge ${status}` }, status);
const time = (iso) => new Date(iso).toLocaleTimeString('nl-BE', { hour12: false });
const money = (cents, currency) => `${(cents / 100).toFixed(2)} ${currency}`;

async function api(path, options) {
  const response = await fetch(path, options);
  if (response.status === 204) return undefined;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error ?? `HTTP ${response.status}`);
  return body;
}

// --- Debug panel --------------------------------------------------------------------------------------------------

function headersBlock(title, headers) {
  const lines = Object.entries(headers ?? {}).map(([k, v]) => `${k}: ${v}`);
  return lines.length ? [el('h4', {}, title), el('pre', {}, lines.join('\n'))] : [];
}

function bodyBlock(title, body) {
  return body ? [el('h4', {}, title), el('pre', {}, body)] : [];
}

function renderEntry(e) {
  const failed = e.error || (e.status && e.status >= 400);
  const summary = el('summary', {},
    el('span', { class: 'time' }, time(e.at)),
    el('span', { class: 'kind' }, e.kind),
    ...(e.status ? [el('span', { class: 'status' }, String(e.status))] : []),
    el('span', { class: 'title' }, e.title),
    ...(e.elapsedMs != null ? [el('span', { class: 'muted' }, `${e.elapsedMs} ms`)] : []));
  const details = el('details', { class: `entry ${failed ? 'fail' : e.kind === 'callback' ? 'callback' : ''}` }, summary);
  if (e.url) details.append(el('div', {}, el('strong', {}, e.method ?? ''), ' ', el('code', {}, e.url)));
  if (e.error) details.append(el('div', { class: 'error' }, e.error));
  if (e.traceId || e.spanId) {
    details.append(el('div', { class: 'trace' }, `traceId: ${e.traceId ?? '-'} · spanId: ${e.spanId ?? '-'} (this is what Bancontact support asks for)`));
  }
  details.append(
    ...headersBlock('Request headers', e.requestHeaders),
    ...bodyBlock('Request body', e.requestBody),
    ...headersBlock('Response headers', e.responseHeaders),
    ...bodyBlock(e.kind === 'request' ? 'Response body' : 'Result', e.responseBody));
  return details;
}

function startDebugPanel(root, getFilter) {
  const filterInput = el('input', { placeholder: 'e.g. payment id' });
  const count = el('span', { class: 'muted' });
  const list = el('div');
  const clear = el('button', { type: 'button', onclick: async () => { await api('/api/debug/clear', { method: 'POST' }); refresh(); } }, 'Clear');
  root.append(el('div', { class: 'debug-tools' }, el('label', {}, 'Filter ', filterInput), clear, count), list);

  const open = new Set();
  async function refresh() {
    const entries = await api('/api/debug').catch(() => []);
    const filter = (filterInput.value || getFilter?.() || '').toLowerCase();
    const visible = filter
      ? entries.filter((e) => e.kind === 'info' || [e.title, e.url, e.requestBody, e.responseBody, e.error].some((s) => s?.toLowerCase().includes(filter)))
      : entries;
    count.textContent = `${visible.length} of ${entries.length} entries, newest first`;
    list.replaceChildren(...visible.map((e) => {
      const node = renderEntry(e);
      const key = `${e.at}|${e.title}`;
      node.open = open.has(key);
      node.addEventListener('toggle', () => (node.open ? open.add(key) : open.delete(key)));
      return node;
    }));
  }
  refresh();
  setInterval(refresh, 2000);
}

// --- Payment page -------------------------------------------------------------------------------------------------

function startPayPage() {
  const form = document.getElementById('pay-form');
  const result = document.getElementById('pay-result');
  const errorBox = document.getElementById('pay-error');
  const product = form.elements.product;
  const posField = document.getElementById('pos-field');
  let current; // {product, payment}
  let timeline = [];
  let timer;

  const syncPos = () => { posField.hidden = product.value !== 'StaticQr'; };
  product.addEventListener('change', syncPos);
  syncPos();

  function render() {
    if (!current) return result.replaceChildren();
    const p = current.payment;
    result.replaceChildren(
      el('h2', {}, `Payment ${p.paymentId}`),
      el('p', {}, 'Status: ', badge(p.status), ` · ${money(p.amount, p.currency)} · expires ${time(p.expiresAt)}`,
        ...(timer ? [el('span', { class: 'muted' }, ' (polled every 2 s)')] : [])),
      el('div', { class: 'qr-row' },
        el('img', { src: p.qrcode, alt: 'QR code', class: 'qr' }),
        el('div', {},
          el('p', {}, 'Scan with the Bancontact Pay test app.'),
          el('p', {}, 'QR URL: ', el('code', {}, p.qrcode)),
          el('p', {}, 'Deeplink: ', el('a', { href: p.deeplink }, el('code', {}, p.deeplink))),
          el('button', { type: 'button', disabled: FINAL.includes(p.status) ? '' : null, onclick: cancel }, 'Cancel'),
          ' ',
          el('button', { type: 'button', onclick: poll }, 'Refresh now'))),
      el('h3', {}, 'Status history'),
      el('ul', { class: 'timeline' }, ...timeline.map((t) => el('li', {}, el('span', { class: 'time' }, time(t.at)), ' ', badge(t.status), ' ', el('span', { class: 'muted' }, t.source)))));  }

  function record(source, status, at = new Date().toISOString()) {
    timeline.push({ at, source, status });
    timeline.sort((a, b) => a.at.localeCompare(b.at));
  }

  async function poll() {
    if (!current) return;
    try {
      const { payment } = current;
      const fresh = await api(`/api/payments/${current.product}/${payment.paymentId}`);
      if (fresh.status !== payment.status) record('polled', fresh.status);
      current.payment = fresh;
      const callbacks = await api(`/api/callbacks?paymentId=${encodeURIComponent(payment.paymentId)}`);
      for (const c of callbacks) {
        const source = `callback ${c.requestId}`;
        if (!timeline.some((t) => t.source === source)) record(source, c.payload.status, c.receivedAt);
      }
      if (FINAL.includes(current.payment.status)) stop();
    } catch (error) {
      errorBox.textContent = `Polling stopped: ${error.message}`;
      stop();
    }
    render();
  }

  function stop() { clearInterval(timer); timer = undefined; }

  async function cancel() {
    errorBox.textContent = '';
    try {
      await api(`/api/payments/${current.product}/${current.payment.paymentId}`, { method: 'DELETE' });
    } catch (error) {
      errorBox.textContent = error.message;
    }
    poll();
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.textContent = '';
    stop();
    timeline = [];
    const data = Object.fromEntries(new FormData(form));
    try {
      const payment = await api('/api/payments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, amount: Number(data.amount) }),
      });
      current = { product: data.product, payment };
      record('created', payment.status);
      timer = setInterval(poll, 2000);
    } catch (error) {
      errorBox.textContent = error.message; // the request and Bancontact's answer are in the debug panel
      current = undefined;
    }
    render();
  });

  startDebugPanel(document.getElementById('debug-root'), () => current?.payment.paymentId);
}

// --- Callbacks page -----------------------------------------------------------------------------------------------

function startCallbacksPage(root) {
  async function refresh() {
    const callbacks = await api('/api/callbacks').catch(() => []);
    if (!callbacks.length) return root.replaceChildren(el('p', {}, 'No callbacks received yet.'));
    const row = (c) => el('tr', {},
      el('td', {}, time(c.receivedAt)),
      el('td', {}, el('code', {}, c.payload.paymentId)),
      el('td', {}, badge(c.payload.status)),
      el('td', {}, money(c.payload.amount, c.payload.currency)),
      el('td', {}, `${c.payload.debtor?.name ?? ''} ${c.payload.debtor?.iban ?? ''}`),
      el('td', {}, el('code', {}, c.requestId)));
    root.replaceChildren(el('table', {},
      el('tr', {}, ...['Received', 'Payment', 'Status', 'Amount', 'Debtor', 'Request ID'].map((h) => el('th', {}, h))),
      ...callbacks.map(row)));
  }
  refresh();
  setInterval(refresh, 2000);
}

if (document.getElementById('pay-form')) startPayPage();
else if (document.getElementById('callbacks-root')) startCallbacksPage(document.getElementById('callbacks-root'));
else if (document.getElementById('debug-root')) startDebugPanel(document.getElementById('debug-root'));
