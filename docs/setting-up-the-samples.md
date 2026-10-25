# Setting up the Python sample

> **This is not an official Bancontact project.** This sample uses the unofficial [BancontactPro.Python](https://github.com/yvebrecht/BancontactPro.Python) library.

This guide takes you from nothing to a payment you made by hand against Bancontact's pre-production, with every call and callback on screen.

## What you need

| You need | Why |
|---|---|
| **Pre-production credentials** from Bancontact | One API key and one PPID (product profile ID) per product, from the onboarding email. See [getting started, step 1](https://github.com/yvebrecht/BancontactPro.Net/blob/main/docs/getting-started.md#1-onboarding-do-this-first--it-has-a-lead-time). |
| **The Bancontact Pay pre-production app** | To scan the QR code and pay. See [Testing with the Bancontact Pay app](https://github.com/yvebrecht/BancontactPro.Net/blob/main/docs/getting-started.md#testing-with-the-bancontact-pay-app) for the download, the placeholder code `123456` and the test cards. |
| **Python 3.11 or later** *or* **Docker** | To run the app. |
| **A public HTTPS address** (only for callbacks) | Bancontact has to reach `POST /bancontact/callback`. Without it, payments still work and the page follows them by polling. |

Install the pre-production app on your phone and add a test card **before** the first payment. Install only one build of the app (pre-production or the store version), never both.

## 1. Know your credentials

Each product in the email has its own pair. Take both values of a pair from the **same** product entry and do not swap them: the API key is the long secret, the PPID is the shorter identifier.

| In the email, under a product | Variable (in `.env` or the environment) |
|---|---|
| "A unique **API key**" | `BANCONTACT_<PRODUCT>_API_KEY` |
| "A unique **Product Profile Identifier** or PPID" | `BANCONTACT_<PRODUCT>_PPID` |
| "... and/or **JWS key**" | none: nothing to fill in |

| Product in the email | `<PRODUCT>` |
|---|---|
| On Display | `ONDISPLAY` |
| On a Receipt | `ONRECEIPT` |
| Static QR | `STATICQR` |
| Top Up | `TOPUP` |

Set the pairs of the products you have and leave the others empty. A product with only one of its two values is treated as not configured. Never commit credentials: `.env` is git-ignored. Payments need the API key alone; Refund and Reconciliation (not used by this sample) also need a signing key.

## 2. Run it

Pick one.

### A. On your own machine

Needs Python 3.11 or later. Clone `BancontactPro.Python` **next to** this repository: `requirements.txt` installs the sister folder.

```text
BancontactPro/
├── BancontactPro.Python/
└── BancontactPro.SDK.Samples.Python/
```

```bash
cd BancontactPro.SDK.Samples.Python
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # .venv/bin/python elsewhere
cp .env.example .env     # fill in the credentials
.venv/Scripts/python run.py
```

Open http://localhost:5086. The app listens on `127.0.0.1` only.

### B. With Docker Compose

This pulls a prebuilt image, `ghcr.io/yvebrecht/bancontactpro-sample-web-python`, so you do not need the library next to the sample.

```bash
cd BancontactPro.SDK.Samples.Python
cp .env.example .env     # fill in the credentials
docker compose up -d
```

Open http://localhost:5086. The port is published on `127.0.0.1` only, because the app has no login.

To build the image yourself (needs `BancontactPro.Python` next to this repository):

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up --build
```

### C. As a stack in Portainer

Portainer cannot run the compose `build:` (it fails with `listing workers for Build`), and a stack from one repository does not have the library beside it. The compose file therefore pulls the prebuilt image, which a workflow builds and publishes on every push to `main`.

1. **Stacks → Add stack → Repository.** Repository URL `https://github.com/yvebrecht/BancontactPro.SDK.Samples.Python`, reference `refs/heads/main`, compose path `docker-compose.yml`.
2. Add the variables of `.env.example` as **environment variables** of the stack: the API key and PPID of each product you have, `BANCONTACT_ENVIRONMENT=Preprod`, and `PUBLIC_BASE_URL` (see step 3).
3. **Deploy the stack.** To update after a new image: **Pull and redeploy**, with **Re-pull image** switched on. Without it Portainer can keep using the old `latest`.
4. The image must be pullable. If it is private, make the package public (the organisation must allow public packages) or add `ghcr.io` as a registry in Portainer with a token that can read packages.

The port is published on `127.0.0.1` of the Docker host. From another machine you cannot reach it until you either put a reverse proxy in front of it or set `SAMPLE_WEB_BIND` to the host's LAN address (or `0.0.0.0`) on purpose.

> **The app has no login.** Whoever can open the page can create and cancel payments with your pre-production keys. Keep it on a trusted network, or put a reverse proxy with its own login in front of the pages. Never expose it unprotected to the internet.

## 3. Callbacks

Bancontact sends a signed callback to the URL you give when you create a payment. The sample sends `PUBLIC_BASE_URL` + `/bancontact/callback`. For it to arrive:

1. **Make the app reachable over public HTTPS**, for example with a reverse proxy, or a tunnel such as Cloudflare Tunnel, to the port the app listens on.
2. Set **`PUBLIC_BASE_URL`** to that address, with no trailing slash, e.g. `https://bancontact-preprod.example.com`, and restart.
3. In front of `/bancontact/callback`:
   - do **not** require a login: Bancontact cannot sign in. Protect the pages, but leave this one path open;
   - do **not** rewrite the path, change the body or compress it in a way the app does not undo: the signature covers the exact bytes and the path;
   - do not let a firewall or bot filter block Bancontact's requests.

Check what Bancontact has for a payment: the `GET /v3/payments/{id}` response in the debug panel shows `creditor.callbackUrl`.

With the default `PUBLIC_BASE_URL` (`http://localhost:5086`) Bancontact cannot reach the app. The payment still completes and the page follows it by polling every two seconds.

The library must include the callback fixes of 2026-10-24 ([BancontactPro.Python PR](https://github.com/yvebrecht/BancontactPro.Python/pull/3)): until then a real callback is rejected.

## 4. Your first payment

1. Open the **Payment** page. Choose a product you configured, e.g. `OnDisplay`, an amount in euro cents (100 is 1.00 EUR), and create the payment.
2. The page shows the QR code, the deeplink and the status, and asks Bancontact for the status every two seconds.
3. In the pre-production app, **scan the QR code** and pay with the test card `5127 8829 9999 9715` (always authorised).
4. The status moves to `SUCCEEDED`. If callbacks reach the app, a `callback ...` line appears in the status history, and the **Callbacks** page lists it.
5. Look at the **Debug** panel under the form: the create call, the status calls and the callback, with headers, bodies and timings.

The other test cards show a failure: `5127 8829 9999 9723` (insufficient funds), `5127 8829 9999 9731` (refused by the issuer).

**Static QR** payments need a POS ID: letters and digits only, at most 36 characters (the default is `POS00001`). A hyphen is rejected by Bancontact.

### The QR test page

**QR test** builds the self-made payload URLs (`https://pay.acc.bancontact.net/t/1/{PPID}` for a fixed amount, `/l/1/{PPID}/{POSId}` for a Static QR till) and the generator image, **without an API call**. Scan the image with the pre-production app and note whether it opens. Whether the app accepts these self-built payloads is not confirmed yet (see [the open issue](https://github.com/yvebrecht/BancontactPro.SDK/issues/5)), so your result is useful.

## 5. Reading the debug panel

Every call the library makes to Bancontact, and every callback, is a line, newest first. Open a line for the details.

| Line | What it shows |
|---|---|
| **Request** (blue) | Method, URL, headers (the API key is masked to its last four characters), request body, response status, headers and body, duration. A failure also shows the `traceId` and `spanId` that Bancontact support asks for. |
| **Callback**, status 200 (green) | The callback arrived and its signature verified: headers, the signature analysis, the raw body, the result. |
| **Callback rejected**, status 401 (red) | The signature did not verify. The **Signature analysis** says which form the header has, decodes the JOSE header and shows the segment sizes. The **raw body** is the exact bytes that were signed. |

The filter box narrows the panel to lines that contain a payment ID. **Clear** empties the log.

## 6. When something goes wrong

| What you see | Cause | What to do |
|---|---|---|
| Portainer: `listing workers for Build` | The stack runs a `build:` | Use the compose file of `main`: it pulls the image. Update the stack to the latest commit and redeploy. |
| Page does not open from another machine | The port is published on `127.0.0.1` | Reverse proxy, or set `SAMPLE_WEB_BIND` (see step 2C). |
| `401` on `POST /v3/payments` | API key and PPID swapped, or the key is for another product | Check the pair in the email against the product you chose, and that the key is the long secret, not the PPID. |
| `... is not configured` | Only one of the pair is set, or the product is empty | Set both values of the pair, or choose another product. |
| `Field posId is invalid` | The POS ID has a character other than a letter or digit | Use letters and digits only, at most 36 characters. |
| No callback line at all | Bancontact cannot reach the URL | `PUBLIC_BASE_URL` is `http://localhost...` or not public; check `creditor.callbackUrl` in the `GET` response. |
| `Callback rejected`, an odd number of dots in the form | A proxy changed the header | Pass the `Signature` header through unchanged. |
| `Callback rejected`, the JOSE header decodes fine | Path or body altered, or an old library | The `path` claim is the registered callback URL: the part after the host must equal the path the app received. Check that nothing rewrites the path or the body, and that the library includes the callback fixes. |
| `Callback rejected`, status 401, again and again | Bancontact retries refused callbacks | Fix the cause. The retries (bursts of four) stop when the app answers 200. |

If it is still unclear, copy the **Signature analysis** and the **raw body** of a rejected callback into an issue: they contain no secrets (the IBAN is masked and the API key never appears).

## 7. Stopping and cleaning up

- Docker: `docker compose down`. Portainer: **Stop** or **Delete** the stack.
- The debug log and the callback list are kept in memory (in files under `var/` for PHP) and are lost when the app restarts or `var/` is emptied.
- Cancel a payment that is still open with the **Cancel** button on the payment page.