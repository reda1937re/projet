import os
import logging

import requests
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

from agent_service import get_response

load_dotenv()

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
VERSION = os.getenv("VERSION")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
    }
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        response.raise_for_status()
        log_http_response(response)
        return response
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return JSONResponse({"status": "error", "message": "Request timed out"}, status_code=408)
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return JSONResponse({"status": "error", "message": "Failed to send message"}, status_code=500)


def is_valid_whatsapp_message(body: dict):
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )


def process_whatsapp_message(body: dict):
    """Traite un message WhatsApp entrant et envoie la réponse de l'agent de support.

    Le numéro de l'expéditeur (`wa_id`) sert de session_id : chaque client garde
    ainsi sa propre conversation, indépendante des autres.
    """
    value = body["entry"][0]["changes"][0]["value"]
    wa_id = value["contacts"][0]["wa_id"]

    message = value["messages"][0]
    if message.get("type") != "text":
        # Seuls les messages texte sont gérés pour l'instant (pas les images,
        # documents, messages vocaux...).
        data = get_text_message_input(
            wa_id, "Je ne peux traiter que des messages texte pour le moment 🙏"
        )
        send_message(data)
        return

    message_body = message["text"]["body"]

    try:
        response_text = get_response(message_body, session_id=wa_id)
    except Exception as e:
        logging.error(f"Erreur lors de la génération de la réponse: {e}")
        response_text = (
            "Désolé, une erreur technique est survenue. "
            "Un membre de notre équipe reviendra vers vous rapidement 🙏"
        )

    data = get_text_message_input(wa_id, response_text)
    send_message(data)
