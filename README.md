# BancontactPro.SDK.Samples.Python

> **This is not an official Bancontact project.** Independent samples for the unofficial [BancontactPro.SDK](https://github.com/yvebrecht/BancontactPro.SDK) libraries.

A small web UI over the Python client, to try a payment by hand against Bancontact's preprod with the Bancontact Pay test app,
and to see what goes over the wire while you do. It is a Starlette app and is meant to run **locally**: it listens on `127.0.0.1` only
and has no login, because it calls Bancontact with your credentials.

The package is not published yet, so the sample installs the sister folder: clone `BancontactPro.Python` next to this repo
(`requirements.txt` has `-e ../BancontactPro.Python`). Once published, that line becomes a normal requirement.

## Pages

| Page | What it does |
|---|---|
| Status | Environment, which products have credentials, the callback URL. |
| Payment | Creates a payment (or a Static QR payment with a POS ID), shows the QR code and deeplink, follows the status every 2 s and from callbacks, cancels. The debug panel below follows that payment. |
| QR test | Builds the self-made payload URLs (`/t/1/{PPID}` and `/l/1/{PPID}/{POSId}`) and the generator image, without an API call. Scan with the preprod test app. |
| Callbacks | The verified callbacks Bancontact sent to `POST /bancontact/callback`. |
| Debug | Everything below, unfiltered. |

## Debug information

Every call the library makes to Bancontact and every callback goes into the debug log:

- request: method, URL, headers (the `Authorization` API key is masked to its last 4 characters; the `Signature` header is shown), body;
- response: status, headers, body, duration; for errors the `traceId` and `spanId` that Bancontact support asks for;
- callback: all received headers (including `Signature`), the exact body, and the verification result. A rejected callback shows the reason;
- the JWKS fetches of the callback verifier appear as requests too.

This works through an `httpx` transport (`DebugTransport` in `sample_web/debug.py`) on the `httpx.AsyncClient` that is passed to
`BancontactClientFactory(http_client=...)`. The library adds the `Authorization` and `Signature` headers before the client sends the
request, so the log shows the request as it was sent.

## Run

Needs Python 3.11 or later.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # .venv/bin/python elsewhere
cp .env.example .env   # fill in the API key and PPID of each product you want to try
.venv/Scripts/python run.py
```

Open http://localhost:5086. The environment is `Preprod` unless `BANCONTACT_ENVIRONMENT=Production`: do not point this sample at production with real money.

## Docker

Because the library is a sister folder, the image is built from the folder that holds both repositories (`docker-compose.yml` sets that context).

```bash
cp .env.example .env   # fill in the credentials
docker compose up --build
```

Open http://localhost:5086. The port is published on `127.0.0.1` only, as the app has no login. `.env` also sets `PUBLIC_BASE_URL` and `SAMPLE_WEB_PORT`.

## Callbacks

Bancontact must reach `POST /bancontact/callback` over public HTTPS. Start a tunnel to port 5086, set `PUBLIC_BASE_URL` to the tunnel's address
(no trailing slash) in `.env`, and restart. The Payment page sends `PUBLIC_BASE_URL` + `/bancontact/callback` as the payment's `callbackUrl`.
Without it the callback URL is `http://localhost:5086/...`, which Bancontact cannot reach: the payment still works, you just follow it by polling.
The signature covers the request path, so the tunnel must not rewrite it.

## Licence

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 Axel Dewaele.

This is an independent, unofficial project. It is not affiliated with, endorsed by or sponsored by Bancontact. "Bancontact" and "Bancontact Pro" are trademarks of their respective owner. The names are used here only to describe what the samples work with. The licence does not grant any right in those trademarks, and the copyright holder does not claim any.
