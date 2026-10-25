"""Describes what a callback's Signature header looks like, so a rejected callback can be understood without a debugger."""

from __future__ import annotations

import base64
import json


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def analyse_signature(signature_header: str, body: bytes) -> str:
    """How many dots the header has, what the JOSE header says, how big the body is. It verifies nothing."""
    if not signature_header.strip():
        return "No Signature header was sent."

    parts = signature_header.split(".")
    if len(parts) == 2:
        form = "header.signature (one dot)"
    elif len(parts) == 3 and parts[1] == "":
        form = "header..signature (two dots, empty payload segment)"
    elif len(parts) == 3:
        form = "header.payload.signature (a non-empty middle segment)"
    else:
        form = f"{len(parts) - 1} dots"
    lines = [f"Signature header: {len(signature_header)} characters, form {form}.", f"Body: {len(body)} bytes."]

    try:
        lines += ["JOSE header:", json.dumps(json.loads(_b64url_decode(parts[0])), indent=2)]
    except (ValueError, UnicodeDecodeError):
        lines.append("The first segment is not a base64url JSON header.")

    try:
        lines.append(f"Signature segment: {len(_b64url_decode(parts[-1]))} bytes (ES256 expects 64).")
    except ValueError:
        lines.append("The last segment is not valid base64url.")
    return "\n".join(lines)