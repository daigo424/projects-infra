import os
import json
import hmac
import hashlib
import urllib.request
import urllib.error

VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
PHONE_NUMBER_ID = os.environ["PHONE_NUMBER_ID"]
APP_SECRET = os.environ.get("APP_SECRET", "")

GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v23.0")


def build_response(status_code: int, body: str | dict):
    if isinstance(body, dict):
        body = json.dumps(body, ensure_ascii=False)
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": body
    }


def verify_signature(headers: dict, raw_body: str) -> bool:
    """
    Verify X-Hub-Signature-256 from Meta webhook
    """
    if not APP_SECRET:
        # Allow skipping verification in development,
        # but strongly recommended to enable in production
        return True

    signature = (
        headers.get("x-hub-signature-256")
        or headers.get("X-Hub-Signature-256")
        or ""
    )

    if not signature.startswith("sha256="):
        return False

    expected = hmac.new(
        APP_SECRET.encode("utf-8"),
        msg=raw_body.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    actual = signature.split("=", 1)[1]
    return hmac.compare_digest(expected, actual)


def send_whatsapp_text(to_number: str, text: str):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": text
        }
    }

    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def extract_incoming_messages(body: dict) -> list[dict]:
    """
    Extract messages from WhatsApp webhook payload
    """
    results = []

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                results.append(msg)

    return results


def lambda_handler(event, context):
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
        or event.get("httpMethod")
        or ""
    ).upper()

    headers = event.get("headers") or {}
    raw_body = event.get("body") or ""

    # In Lambda Function URL, query parameters are here
    query = event.get("queryStringParameters") or {}

    # 1) Webhook verification
    if method == "GET":
        mode = query.get("hub.mode")
        token = query.get("hub.verify_token")
        challenge = query.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/plain; charset=utf-8"},
                "body": challenge or ""
            }
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "text/plain; charset=utf-8"},
            "body": "Forbidden"
        }

    # 2) Incoming webhook handling
    if method == "POST":
        if not verify_signature(headers, raw_body):
            return {
                "statusCode": 403,
                "headers": {"Content-Type": "text/plain; charset=utf-8"},
                "body": "Invalid signature"
            }

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return build_response(400, {"message": "Invalid JSON"})

        messages = extract_incoming_messages(body)

        for msg in messages:
            from_number = msg.get("from")
            msg_type = msg.get("type")

            if not from_number:
                continue

            # Example: reply with a fixed message for incoming text
            if msg_type == "text":
                received_text = msg.get("text", {}).get("body", "")
                reply_text = f"Received: {received_text}"
            else:
                reply_text = "Message received."

            try:
                send_whatsapp_text(from_number, reply_text)
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                print("Meta API error:", e.code, error_body)
            except Exception as e:
                print("Unexpected error:", str(e))

        # Return 200 to Meta
        return build_response(200, {"ok": True})

    return build_response(405, {"message": "Method not allowed"})