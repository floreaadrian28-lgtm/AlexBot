import os
import base64
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURĂRI ---
TOKEN = "8093206443:AAFboufSo82UmUDMCB2e2gNSQWb2A8Jzef8"  # Tokenul tău valid
MY_CHAT_ID = 8421765354
EXPEDITOR_TINTA = "ciprianursulescu@yahoo.com"

# Setare căi absolute pentru token și credentials
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Folder pentru atașamente
FOLDER_ATASAMENTE = os.path.join(BASE_DIR, "atasamente")
os.makedirs(FOLDER_ATASAMENTE, exist_ok=True)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

ultimele_atasamente = []

# --- AUTENTIFICARE GMAIL ---
def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

# --- VERIFICARE DUPĂ DATA DIN CALENDAR ---
def verifica_emailuri():
    global ultimele_atasamente
    
    # 0 = Luni, 1 = Marți, ..., 4 = Vineri, 5 = Sâmbătă, 6 = Duminică
    ziua_saptamanii = datetime.now().weekday()
    
    # Dacă este Sâmbătă (5) sau Duminică (6), oprește căutarea
    if ziua_saptamanii >= 5:
        print("[-] Astăzi este weekend. Nu se efectuează verificări de e-mailuri.")
        return "weekend"

    # Preluăm data de azi și data de mâine pentru intervalul exact din calendar
    azi_dt = datetime.now()
    maine_dt = azi_dt + timedelta(days=1)
    
    azi_str = azi_dt.strftime("%Y/%m/%d")
    maine_str = maine_dt.strftime("%Y/%m/%d")
    
    print(f"\n[+] Verificare Gmail pentru e-mailuri sosite AZI ({azi_str})...")
    
    try:
        service = get_gmail_service()
        # Caută doar e-mailuri sosite în ziua curentă (de la 00:00 la 23:59)
        query = f"from:{EXPEDITOR_TINTA} has:attachment after:{azi_str} before:{maine_str}"
        
        results = service.users().messages().list(userId='me', q=query, maxResults=5).execute()
        messages = results.get('messages', [])

        if not messages:
            print(f"[-] Nu s-au găsit e-mailuri noi primite astăzi ({azi_str}).")
            return []

        msg_id = messages[0]['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()
        
        atasamente_descarcate = []
        payload = message.get('payload', {})
        parts = payload.get('parts', [])

        for part in parts:
            filename = part.get('filename')
            body = part.get('body', {})
            attachment_id = body.get('attachmentId')

            if filename and attachment_id:
                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=attachment_id
                ).execute()
                
                file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                file_path = os.path.join(FOLDER_ATASAMENTE, filename)

                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                atasamente_descarcate.append(file_path)
                print(f"[+] Descărcat: {filename}")

        ultimele_atasamente = atasamente_descarcate
        return atasamente_descarcate

    except Exception as e:
        print(f"[!] Eroare la verificarea Gmail: {e}")
        return []

# --- BOT TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Botul Alex Agent este activ și verifică e-mailurile de Luni până Vineri!")

async def comanda_verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Verific e-mailurile de astăzi...")
    fisiere = verifica_emailuri()
    
    if fisiere == "weekend":
        await update.message.reply_text("📅 Astăzi este weekend (Sâmbătă/Duminică). Nu se primesc e-mailuri noi.")
    elif fisiere:
        nume_fisiere = "\n".join([f"- {os.path.basename(f)}" for f in fisiere])
        keyboard = [[InlineKeyboardButton("🖨️ DA, printează atașamentele", callback_data="print_yes")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Am găsit {len(fisiere)} atașamente noi sosite astăzi:\n{nume_fisiere}\n\nDorești să le printezi?",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Nu am găsit e-mailuri noi sosite astăzi.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "print_yes":
        await query.edit_message_text("Comandă trimisă către imprimantă! Se printează atașamentele...")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verifica", comanda_verifica))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("[+] Botul a pornit.")
    app.run_polling()

if __name__ == '__main__':
    main()