"""Server-rendered pages. The behaviour on them is in public/app.js, shared with the other language samples."""

from __future__ import annotations

from html import escape as _escape
from typing import Any


def esc(value: object) -> str:
    return _escape("" if value is None else str(value), quote=True)


_NAV = [("/", "Status"), ("/pay", "Payment"), ("/qr", "QR test"), ("/callbacks", "Callbacks"), ("/debug", "Debug")]


def layout(title: str, path: str, body: str) -> str:
    nav = "".join(f'<a href="{href}"{" class=active" if href == path else ""}>{label}</a>' for href, label in _NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><link rel="stylesheet" href="/app.css"></head>
<body><header class="topbar"><strong>Bancontact Pro sample</strong><nav>{nav}</nav></header>
<main>{body}</main><script src="/app.js" type="module"></script></body></html>"""


def _options(values: list[str], selected: str | None = None) -> str:
    return "".join(f'<option value="{esc(v)}"{" selected" if v == selected else ""}>{esc(v)}</option>' for v in values)


def status_page(environment: str, products: list[tuple[str, bool]], public_base_url: str | None, port: int) -> str:
    callback = f"{public_base_url or f'http://localhost:{port}'}/bancontact/callback"
    rows = "".join(f"<tr><th>{esc(p)}</th><td>{'API key and PPID set' if ok else 'not configured'}</td></tr>" for p, ok in products)
    return layout(
        "Status",
        "/",
        f"""<h1>Status</h1>
<table>
<tr><th>Environment</th><td>{esc(environment)}</td></tr>
<tr><th>PUBLIC_BASE_URL</th><td>{esc(public_base_url or 'not set: Bancontact cannot reach the callback')}</td></tr>
<tr><th>Callback URL</th><td><code>{esc(callback)}</code></td></tr></table>
<h2>Products</h2><table>{rows}</table>
<p class="muted">This app calls Bancontact with your credentials and is meant to stay local: it listens on localhost only.</p>""",
    )


def pay_page(products: list[str]) -> str:
    return layout(
        "Payment",
        "/pay",
        f"""<h1>Payment</h1>
<form id="pay-form"><div class="form-grid">
<label>Product<select name="product">{_options(products, 'OnDisplay')}</select></label>
<label>Amount (euro cents)<input name="amount" type="number" min="1" value="100" required></label>
<label>Description<input name="description" value="sample payment"></label>
<label>Reference<input name="reference"></label>
<label id="pos-field" hidden>POS ID (Static QR)<input name="posId" value="POS00001" maxlength="36" pattern="[A-Za-z0-9]{{1,36}}" title="Letters and digits only, at most 36 characters"></label>
</div><button type="submit">Create payment</button></form>
<p id="pay-error" class="error"></p>
<section id="pay-result"></section>
<h2>Debug</h2><div id="debug-root"></div>""",
    )


def qr_page(products: list[str], q: dict[str, str], result: dict[str, Any] | None = None) -> str:
    if result is None:
        outcome = ""
    elif "error" in result:
        outcome = f'<p class="error">{esc(result["error"])}</p>'
    else:
        outcome = f"""<p>Environment: <strong>{esc(result['environment'])}</strong></p>
<p>Payload URL: <code>{esc(result['payloadUrl'])}</code></p><p>Generator URL: <code>{esc(result['imageUrl'])}</code></p>
<img class="qr" src="{esc(result['imageUrl'])}" alt="QR code">
<p class="muted">No image? Open the generator URL in a tab: a 400 means the generator rejects the payload's host.</p>"""

    def sel(name: str, value: str) -> str:
        return " selected" if q[name] == value else ""

    return layout(
        "QR test",
        "/qr",
        f"""<h1>QR test</h1>
<p>Builds the self-made payload URLs the guides describe, without an API call, with the product's PPID and the hosts of the configured environment.
Scan the QR image with the preprod test app and note whether it opens.</p>
<form method="get" action="/qr"><div class="form-grid">
<label>Product<select name="product">{_options(products, q['product'])}</select></label>
<label>Type<select name="kind"><option value="fixed"{sel('kind', 'fixed')}>Fixed amount (/t/1/{{PPID}})</option><option value="pos"{sel('kind', 'pos')}>Static QR till (/l/1/{{PPID}}/{{POSId}})</option></select></label>
<label>Amount (euro cents, fixed only)<input name="amount" type="number" min="1" value="{esc(q['amount'])}"></label>
<label>Description (fixed only)<input name="description" value="{esc(q['description'])}"></label>
<label>Reference (fixed only)<input name="reference" value="{esc(q['reference'])}"></label>
<label>POS ID (till only)<input name="posId" value="{esc(q['posId'])}" maxlength="36" pattern="[A-Za-z0-9]{{1,36}}" title="Letters and digits only, at most 36 characters"></label>
<label>Format<select name="format"><option{sel('format', 'PNG')}>PNG</option><option{sel('format', 'SVG')}>SVG</option></select></label>
</div><button type="submit">Build QR</button></form>{outcome}""",
    )


def callbacks_page() -> str:
    return layout(
        "Callbacks",
        "/callbacks",
        '<h1>Callbacks</h1><p class="muted">The verified callbacks, newest first. Rejected ones are on the Debug page.</p><div id="callbacks-root"></div>',
    )


def debug_page() -> str:
    return layout(
        "Debug",
        "/debug",
        """<h1>Debug</h1>
<p class="muted">Every call the library makes to Bancontact (Authorization masked, Signature, body, response, trace IDs) and every received callback, including rejected ones.</p>
<div id="debug-root"></div>""",
    )
