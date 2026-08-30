from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import base64
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# --- 1. CONFIGURARE SERVER WEB PENTRU RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- 2. LOGICA DE GMAIL CU TOKEN SALVAT ---
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

# --- 3. TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salut, Adrian! Sunt Alex. Sunt conectat și pregătit să te ajut.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    
    if "verifică" in text or "verifica" in text:
        await update.message.reply_text("Verific e-mailurile acum...")
        rezultat_gmail = verifica_emailuri_gmail()
        await update.message.reply_text(rezultat_gmail)
    else:
        await update.message.reply_text(f"Am primit mesajul tău: {update.message.text}")

def main():
    TOKEN = "8093206443:AAFboufSo82UmUDMCB2e2gNSQWb2A8Jzef8"  # Pune tokenul tău aici
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Botul a pornit complet...")
    app.run_polling()

if __name__ == "__main__":
    main()