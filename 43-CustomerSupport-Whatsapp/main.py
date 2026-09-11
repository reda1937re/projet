import os
import json
import logging
from threading import Thread

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

from whatsapp_utils import process_whatsapp_message, is_valid_whatsapp_message

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="WhatsApp Customer Support Agent")


@app.get("/")
def read_root():
    return {"message": "Agent de support client WhatsApp — en ligne."}


async def verify(request: Request):
    """Vérification exigée par Meta lors de la configuration du webhook."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logging.info("WEBHOOK_VERIFIED")
            return PlainTextResponse(content=challenge, status_code=200)
        logging.warning("VERIFICATION_FAILED")
        raise HTTPException(status_code=403, detail="Verification failed")
    logging.warning("MISSING_PARAMETER")
    raise HTTPException(status_code=400, detail="Missing parameters")


async def handle_message(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid JSON provided"})

    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        # Accusé de livraison/lecture Meta, pas un message : rien à faire.
        return JSONResponse(content={"status": "ok"})

    if is_valid_whatsapp_message(body):
        # Traité dans un thread séparé pour renvoyer 200 à Meta immédiatement
        # (Meta retente l'envoi du webhook si la réponse tarde).
        try:
            Thread(target=process_whatsapp_message, args=(body,)).start()
        except Exception as e:
            logging.error(f"Error starting background message thread: {e}")
        return JSONResponse(content={"status": "ok"})

    return JSONResponse(status_code=404, content={"status": "error", "message": "Not a WhatsApp API event"})


@app.get("/webhook")
async def webhook_get(request: Request):
    return await verify(request)


@app.post("/webhook")
async def webhook_post(request: Request):
    return await handle_message(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
