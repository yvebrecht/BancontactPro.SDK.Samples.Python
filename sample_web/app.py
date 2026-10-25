"""A small web UI over the Python client, to try a payment by hand against Bancontact's preprod and see what goes over the wire."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bancontactpro import (
    BancontactApiException,
    BancontactClientFactory,
    BancontactCredentials,
    BancontactEnvironment,
    BancontactProduct,
    BancontactProductNotConfiguredException,
    CreatePaymentRequest,
    CreateStaticQrPaymentRequest,
    InvalidCallbackException,
    ProductCredentials,
    QrCodeImageFormat,
    qr,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import views
from .debug import DebugLog, DebugTransport, pretty

CALLBACK_PATH = "/bancontact/callback"
PRODUCTS = {p.value: p for p in BancontactProduct}

debug = DebugLog()
callbacks: list[dict[str, Any]] = []


def port() -> int:
    return int(os.environ.get("PORT", "5086"))


def public_base_url() -> str | None:
    return os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/") or None


def callback_url() -> str:
    return f"{public_base_url() or f'http://localhost:{port()}'}{CALLBACK_PATH}"


def read_credentials() -> BancontactCredentials:
    """Credentials from the environment (or ``.env``): BANCONTACT_<PRODUCT>_API_KEY and BANCONTACT_<PRODUCT>_PPID. Read on every call."""
    products = {}
    for product in BancontactProduct:
        prefix = f"BANCONTACT_{product.value.upper()}"
        api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
        ppid = os.environ.get(f"{prefix}_PPID", "").strip()
        if api_key and ppid:
            products[product] = ProductCredentials(api_key=api_key, merchant_profile_id=ppid)
    production = os.environ.get("BANCONTACT_ENVIRONMENT") == BancontactEnvironment.PRODUCTION.value
    return BancontactCredentials(environment=BancontactEnvironment.PRODUCTION if production else BancontactEnvironment.PREPROD, products=products)


# Every call to Bancontact, including the JWKS fetches of the callback verifier, goes through the debug transport.
factory = BancontactClientFactory(read_credentials, http_client=httpx.AsyncClient(transport=DebugTransport(debug)))


def payment_view(payment: Any) -> dict[str, Any]:
    expires = payment.expires_at if hasattr(payment, "expires_at") else payment.expire_at
    return {
        "paymentId": payment.payment_id,
        "status": payment.status.value,
        "amount": payment.amount,
        "currency": payment.currency,
        "expiresAt": expires.isoformat(),
        "qrcode": payment.links.qrcode.href if payment.links else "",
        "deeplink": payment.links.deeplink.href if payment.links else "",
    }


def error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, BancontactProductNotConfiguredException):
        return JSONResponse({"error": str(exc)}, status_code=400)
    if isinstance(exc, BancontactApiException):
        status = exc.status_code if exc.status_code >= 400 else 502
        return JSONResponse({"error": f"Bancontact returned {exc.status_code} {exc.code}: {exc}"}, status_code=status)
    return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)


async def status(request: Request) -> Response:
    credentials = read_credentials()
    products = [(p.value, await factory.is_configured(p)) for p in BancontactProduct]
    return HTMLResponse(views.status_page(credentials.environment.value, products, public_base_url(), port()))


async def pay(request: Request) -> Response:
    return HTMLResponse(views.pay_page(list(PRODUCTS)))


async def qr_route(request: Request) -> Response:
    params = request.query_params
    q = {
        "product": params.get("product", "OnDisplay"),
        "kind": params.get("kind", "fixed"),
        "amount": params.get("amount", "100"),
        "description": params.get("description", "sample"),
        "reference": params.get("reference", ""),
        "posId": params.get("posId", "POS00001"),
        "format": params.get("format", "PNG"),
    }
    if "product" not in params:
        return HTMLResponse(views.qr_page(list(PRODUCTS), q))
    try:
        product = PRODUCTS.get(q["product"])
        if product is None:
            raise ValueError(f"Unknown product '{q['product']}'.")
        credentials = read_credentials()
        pair = credentials.get_credentials(product)
        if pair is None:
            raise BancontactProductNotConfiguredException(product)
        ppid = pair.merchant_profile_id or ""
        environment = credentials.environment
        if q["kind"] == "pos":
            payload_url = qr.build_static_qr_location_url(environment, ppid, q["posId"])
        else:
            payload_url = qr.build_fixed_amount_payment_url(environment, ppid, int(q["amount"]), q["description"] or None, q["reference"] or None)
        fmt = QrCodeImageFormat.SVG if q["format"] == "SVG" else QrCodeImageFormat.PNG
        image_url = qr.build_qr_code_image_url(environment, payload_url, fmt)
        debug.info(f"QR payload built ({q['kind']}, {environment.value})", f"payload: {payload_url}\nimage: {image_url}")
        return HTMLResponse(views.qr_page(list(PRODUCTS), q, {"environment": environment.value, "payloadUrl": payload_url, "imageUrl": image_url}))
    except Exception as exc:  # shown on the page
        return HTMLResponse(views.qr_page(list(PRODUCTS), q, {"error": str(exc)}))


async def callbacks_page(request: Request) -> Response:
    return HTMLResponse(views.callbacks_page())


async def debug_page(request: Request) -> Response:
    return HTMLResponse(views.debug_page())


async def api_debug(request: Request) -> Response:
    return JSONResponse(debug.recent())


async def api_debug_clear(request: Request) -> Response:
    debug.clear()
    return JSONResponse({})


async def api_callbacks(request: Request) -> Response:
    payment_id = request.query_params.get("paymentId")
    return JSONResponse([c for c in callbacks if payment_id is None or c["payload"]["paymentId"] == payment_id])


async def api_create_payment(request: Request) -> Response:
    try:
        body = await request.json()
        product = PRODUCTS.get(str(body.get("product")))
        if product is None:
            return JSONResponse({"error": f"Unknown product '{body.get('product')}'."}, status_code=400)
        payments = await factory.payments(product)
        description = (body.get("description") or "").strip() or None
        reference = (body.get("reference") or "").strip() or None
        if product == BancontactProduct.STATIC_QR:
            created = await payments.create_static_qr_payment(
                CreateStaticQrPaymentRequest(
                    amount=int(body["amount"]),
                    pos_id=(body.get("posId") or "POS00001").strip(),
                    description=description,
                    reference=reference,
                    callback_url=callback_url(),
                )
            )
        else:
            created = await payments.create(CreatePaymentRequest(amount=int(body["amount"]), description=description, reference=reference, callback_url=callback_url()))
        return JSONResponse(payment_view(created), status_code=201)
    except Exception as exc:
        return error_response(exc)


async def api_payment(request: Request) -> Response:
    product = PRODUCTS.get(request.path_params["product"])
    if product is None:
        return JSONResponse({"error": f"Unknown product '{request.path_params['product']}'."}, status_code=404)
    payment_id = request.path_params["payment_id"]
    try:
        payments = await factory.payments(product)
        if request.method == "DELETE":
            await payments.cancel(payment_id)
            debug.info(f"Payment {payment_id} cancelled")
            return Response(status_code=204)
        return JSONResponse(payment_view(await payments.get(payment_id)))
    except Exception as exc:
        return error_response(exc)


async def bancontact_callback(request: Request) -> Response:
    """Bancontact calls this when a payment changes. Every call is logged, valid or not, with the Signature header and the exact body."""
    body = await request.body()
    text = body.decode("utf-8", errors="replace")
    received = dict(request.headers)
    try:
        # The exact bytes received: re-serialising a parsed body first would change them and break the signature.
        verified = await factory.callback_verifier().verify_and_parse(request.headers.get("signature", ""), body, request.url.path)
    except InvalidCallbackException as exc:
        debug.add("callback", "Callback rejected", method="POST", url=request.url.path, status=401, requestHeaders=received, requestBody=pretty(text), error=str(exc))
        return Response(status_code=401)

    payload = verified.payload
    callbacks.insert(
        0,
        {
            "receivedAt": datetime.now(UTC).isoformat(),
            "requestId": verified.request_id,
            "payload": {
                "paymentId": payload.payment_id,
                "status": payload.status.value,
                "amount": payload.amount,
                "currency": payload.currency,
                "debtor": {"name": payload.debtor.name, "iban": payload.debtor.iban},
            },
        },
    )
    del callbacks[100:]
    debug.add(
        "callback",
        f"Callback {payload.status.value} for {payload.payment_id}",
        method="POST",
        url=request.url.path,
        status=200,
        requestHeaders=received,
        requestBody=pretty(text),
        responseBody=f"Signature valid. Bancontact request ID: {verified.request_id}",
    )
    return Response(status_code=200)


routes = [
    Route("/", status),
    Route("/pay", pay),
    Route("/qr", qr_route),
    Route("/callbacks", callbacks_page),
    Route("/debug", debug_page),
    Route("/api/debug", api_debug),
    Route("/api/debug/clear", api_debug_clear, methods=["POST"]),
    Route("/api/callbacks", api_callbacks),
    Route("/api/payments", api_create_payment, methods=["POST"]),
    Route("/api/payments/{product}/{payment_id}", api_payment, methods=["GET", "DELETE"]),
    Route(CALLBACK_PATH, bancontact_callback, methods=["POST"]),
    Mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "public")),
]

app = Starlette(routes=routes)
