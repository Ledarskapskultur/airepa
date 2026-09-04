"""Tar emot Vapis webhookar: verktygsanrop och slutrapport."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.tools import CallContext, Tools

logger = logging.getLogger(__name__)

router = APIRouter()
_tools: Tools | None = None


def get_tools() -> Tools:
    global _tools
    if _tools is None:
        _tools = Tools()
    return _tools


# -- Signaturkontroll -------------------------------------------------------

def verifiera_signatur(rakropp: bytes, secret_header: str | None, signature_header: str | None):
    """Vapi skickar antingen en delad hemlighet eller en HMAC-signatur."""
    hemlighet = get_settings().vapi_webhook_secret
    if not hemlighet:
        logger.warning("VAPI_WEBHOOK_SECRET är inte satt – webhooken är oskyddad")
        return
    if secret_header and hmac.compare_digest(secret_header, hemlighet):
        return
    if signature_header:
        vantad = hmac.new(hemlighet.encode(), rakropp, hashlib.sha256).hexdigest()
        mottagen = signature_header.split("=")[-1].strip()
        if hmac.compare_digest(mottagen, vantad):
            return
    raise HTTPException(status_code=401, detail="Ogiltig signatur")


# -- Hjälpare ---------------------------------------------------------------

def _as_dict(varde: Any) -> dict:
    if isinstance(varde, dict):
        return varde
    if isinstance(varde, str) and varde.strip():
        try:
            tolkat = json.loads(varde)
            return tolkat if isinstance(tolkat, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def extrahera_verktygsanrop(message: dict) -> list[tuple[str, str, dict]]:
    """Plockar ut (toolCallId, namn, argument) oavsett vilken form Vapi använder."""
    anrop: list[tuple[str, str, dict]] = []
    for post in message.get("toolCallList") or message.get("toolCalls") or []:
        funktion = post.get("function") or {}
        namn = post.get("name") or funktion.get("name") or ""
        argument = _as_dict(
            post.get("arguments")
            if post.get("arguments") is not None
            else funktion.get("arguments")
        )
        if namn:
            anrop.append((post.get("id", ""), namn, argument))
    if not anrop and message.get("functionCall"):
        fc = message["functionCall"]
        namn = fc.get("name", "")
        if namn:
            anrop.append(("", namn, _as_dict(fc.get("parameters") or fc.get("arguments"))))
    return anrop


def call_context(message: dict) -> CallContext:
    call = message.get("call") or {}
    kund = message.get("customer") or call.get("customer") or {}
    return CallContext(
        vapi_call_id=call.get("id", "") or message.get("callId", ""),
        fran_nummer=kund.get("number", "") or call.get("from", ""),
    )


# -- Endpoint ---------------------------------------------------------------

@router.post("/vapi/webhook")
async def vapi_webhook(
    request: Request,
    x_vapi_secret: str | None = Header(default=None),
    x_vapi_signature: str | None = Header(default=None),
):
    rakropp = await request.body()
    verifiera_signatur(rakropp, x_vapi_secret, x_vapi_signature)

    try:
        payload = json.loads(rakropp or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ogiltig JSON") from None

    message = payload.get("message") or payload
    typ = message.get("type", "")
    logger.info("Vapi-webhook: %s", typ)

    if typ in ("tool-calls", "function-call", "tool_calls"):
        return await _hantera_verktygsanrop(message)
    if typ == "end-of-call-report":
        await _hantera_slutrapport(message)
        return {"status": "ok"}

    # status-update, speech-update, hang med flera – kvitteras men gör inget.
    return {"status": "ok"}


async def _hantera_verktygsanrop(message: dict) -> dict:
    tools = get_tools()
    ctx = call_context(message)
    anrop = extrahera_verktygsanrop(message)
    if not anrop:
        return {"results": []}

    resultat = []
    for tool_call_id, namn, argument in anrop:
        svar = await tools.dispatch(namn, argument, ctx)
        resultat.append(
            {
                "toolCallId": tool_call_id,
                "name": namn,
                "result": json.dumps(svar, ensure_ascii=False),
            }
        )
    # "result" i singular finns med för Vapis äldre function-call-format.
    return {"results": resultat, "result": resultat[0]["result"]}


async def _hantera_slutrapport(message: dict) -> None:
    tools = get_tools()
    ctx = call_context(message)
    if not ctx.vapi_call_id:
        return

    artefakt = message.get("artifact") or {}
    transkript = message.get("transcript") or artefakt.get("transcript")
    analys = message.get("analysis") or {}
    sammanfattning = message.get("summary") or analys.get("summary")
    varaktighet = message.get("durationSeconds")

    await tools.db.avsluta_samtal(
        ctx.vapi_call_id,
        fran_nummer=ctx.fran_nummer or None,
        startad_at=message.get("startedAt"),
        avslutad_at=message.get("endedAt"),
        varaktighet_sek=int(varaktighet) if varaktighet is not None else None,
        transkript=transkript,
        sammanfattning=sammanfattning,
        avbrutet=True,
    )
