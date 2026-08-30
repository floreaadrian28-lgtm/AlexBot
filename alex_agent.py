import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import urllib.request
import urllib.parse

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN = "TOKENUL_TAU_DE_TELEGRAM"  # Pune aici tokenul tău real de la BotFather
RENDER_URL = "https://alex-bot-tcsc.onrender.com"  # Link-ul tău de pe Render

# --- 1. LOGICA DE GMAIL ---
def decodeaza(data):
    if not data:
        return b""
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)

def gaseste_atasamente(payload, lista):
    filename = payload.get("filename")
    body = payload.get("body", {})
    attachment_id = body.get("attachmentId")

    if filename and attachment_id:
        lista.append({
            "filename": filename,
            "attachment_id": attachment_id
        })

    for parte in payload.get("parts", []):
        gaseste_atasamente(parte, lista)

def verifica_emailuri_gmail():
    try:
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        serviciu = build("gmail", "v1", credentials=creds)

        cautare = 'from:ciprianursulescu@yahoo.com subject:"SORIN 17.08.2026"'
        rezultate = serviciu.users().messages().list(userId="me", q=cautare, maxResults=1).execute()
        mesaje = rezultate.get("messages", [])

        if not mesaje:
            return "Nu am găsit mesajul de la Ciprian."

        mesaj_id = mesaje[0]["id"]
        mesaj = serviciu.users().messages().get(userId="me", id=mesaj_id, format="full").execute()

        atasamente = []
        gaseste_atasamente(mesaj.get("payload", {}), atasamente)

        if not atasamente:
            return "Am găsit mesajul, dar nu are atașamente."

        folder = "atasamente"
        os.makedirs(folder, exist_ok=True)
        nume_fisiere = []

        for atasament in atasamente:
            nume = atasament["filename"]
            attachment_id = atasament["attachment_id"]
            rezultat = serviciu.users().messages().attachments().get(userId="me", messageId=mesaj_id, id=attachment_id).execute()
            continut = decodeaza(rezultat.get("data", ""))
            cale = os.path.join(folder, nume)
            with open(cale, "wb") as fisier:
                fisier.write(continut)
            nume_fisiere.append(nume)

        return f"Am găsit {len(nume_fisiere)} atașamente descărcate:\n" + "\n".join([f"- {n}" for n in nume_fisiere])
    except Exception as e:
        return f"Erore la conectarea cu Gmail: {str(e)}"

def trimite_mesaj_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    try:
        urllib.request.urlopen(url, data=data)
    except Exception as e:
        print("Erore la trimiterea mesajului pe Telegram:", e)

# --- 2. SERVERUL HTTP CARE ASCULTĂ TELEGRAMUL ---
class TelegramWebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running via Webhook!")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "").lower()

                if "verifică" in text or "verifica" in text:
                    trimite_mesaj_telegram(chat_id, "Verific e-mailurile acum...")
                    rezultat = verifica_emailuri_gmail()
                    trimite_mesaj_telegram(chat_id, rezultat)
                else:
                    trimite_mesaj_telegram(chat_id, f"Am primit mesajul tău: {update['message'].get('text')}")
        except Exception as e:
            print("Erore în procesarea mesajului:", e)

        self.send_response(200)
        self.end_headers()

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), TelegramWebhookHandler)
    print("Serverul pornește pe portul 10000...")
    server.serve_forever()

def seteaza_webhook():
    import time
    time.sleep(3) # Așteaptă pornirea serverului
     webhook_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={RENDER_URL}"
    try:
        urllib.request.urlopen(webhook_url)
        print("Webhook setat cu succes pe Telegram!")
    except Exception as e:
        print("Erore la setarea webhook-ului:", e)

if __name__ == "__main__":
    # Setează webhook-ul automat într-un fir separat
    threading.Thread(target=seteaza_webhook, daemon=True).start()
    # Pornește serverul web principal
    run_server()