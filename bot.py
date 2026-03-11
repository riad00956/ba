import os, asyncio, sqlite3, zipfile
from flask import Flask
from threading import Thread
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telethon import TelegramClient, errors, events, functions, types
from telethon.sessions import StringSession

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_NAME = 'database.db'
ADMIN_ID = 8373846582
CREDIT = "「 Prime Xyron 」👨‍💻"

bot = AsyncTeleBot(BOT_TOKEN)
user_states = {}
active_clients = {}

# --- Flask Server ---
app = Flask('')
@app.route('/')
def home(): return "Phantom Ghost System is Online"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- Database Helper ---
def db_query(sql, params=(), fetch=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            res = cur.fetchall() if fetch else None
            conn.commit()
            return res
        except sqlite3.OperationalError:
            return None

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, api_id INTEGER, api_hash TEXT, 
            string_session TEXT, custom_reply TEXT DEFAULT "I'm currently offline.", 
            is_active INTEGER DEFAULT 0, is_enabled INTEGER DEFAULT 1)''')

# --- Ghost Listener Function ---
async def start_user_listener(uid, api_id, api_hash, string_session):
    if uid in active_clients:
        try: await active_clients[uid].disconnect()
        except: pass

    client = TelegramClient(StringSession(string_session), int(api_id), api_hash, auto_reconnect=True)
    active_clients[uid] = client
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            db_query('UPDATE users SET is_active=0 WHERE user_id=?', (uid,))
            return

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handler(event):
            # রিয়েল টাইমে ডাটাবেস থেকে সেটিংস চেক
            row = db_query('SELECT custom_reply, is_enabled FROM users WHERE user_id=?', (uid,), True)
            if not row or row[0][1] == 0: return

            try:
                # নিজের স্ট্যাটাস চেক
                me = await client(functions.users.GetUsersRequest(id=['me']))
                if isinstance(me[0].status, types.UserStatusOnline): return

                # অটোরিপ্লাই পাঠানো
                await asyncio.sleep(1)
                await event.reply(row[0][0])
                
                # --- Ghost Mode: অফলাইন স্ট্যাটাস মেইনটেইন করা ---
                await client(functions.account.UpdateStatusRequest(offline=True))
                
            except Exception as e:
                print(f"Reply Error: {e}")

        print(f"✅ Ghost Listener Active: {uid}")
        await client.run_until_disconnected()
    except Exception as e:
        print(f"❌ Client Error {uid}: {e}")
    finally:
        active_clients.pop(uid, None)

# --- Bot Commands ---
@bot.message_handler(commands=['start'])
async def welcome(m):
    db_query('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (m.from_user.id,))
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⚙️ Settings", "✏️ Set Reply", "📊 Status")
    
    text = (
        "👻 𝙿𝚑𝚊𝚗𝚝𝚘𝚖 𝚁𝚎𝚙𝚕𝚢\n\n"
        "Welcome to your Telegram shadow.\n"
        "যখন আপনি অফলাইনে থাকবেন, আমি অটো রিপ্লাই দেব এবং আপনাকে অনলাইনে আনব না।\n\n"
        "⚡ Ghost Presence Detection\n"
        "💬 Custom Auto Reply\n"
        "🔐 Secure Login System\n\n"
        f"Powered by {CREDIT}"
    )
    await bot.send_message(m.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
async def settings(m):
    uid = m.from_user.id
    data = db_query('SELECT string_session, is_enabled FROM users WHERE user_id=?', (uid,), True)
    
    status_text = "Connected" if data and data[0][0] else "Not Connected"
    markup = InlineKeyboardMarkup()
    
    if status_text == "Not Connected":
        markup.add(InlineKeyboardButton("➕ Login Account", callback_data="login"))
    else:
        toggle = "🟢 Bot Enabled" if data[0][1] == 1 else "🔴 Bot Disabled"
        markup.add(InlineKeyboardButton(toggle, callback_data="toggle"))
        markup.add(InlineKeyboardButton("❌ Logout", callback_data="logout"))

    text = f"⚙️ 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜 𝙿𝚊𝚗𝚎𝚕\n\nAccount Status : {status_text}\n\nবট চালু থাকলে আপনি অফলাইনে থাকলেও রিপ্লাই যাবে।"
    await bot.send_message(uid, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: True)
async def callbacks(c):
    uid = c.from_user.id
    if c.data == "login":
        user_states[uid] = {'step': 'api'}
        await bot.send_message(uid, "🔑 Send your credentials as `API_ID:API_HASH`:")
    elif c.data == "toggle":
        db_query('UPDATE users SET is_enabled = 1 - is_enabled WHERE user_id=?', (uid,))
        await settings(c.message)
    elif c.data == "logout":
        db_query('UPDATE users SET string_session=NULL, is_active=0 WHERE user_id=?', (uid,))
        if uid in active_clients: await active_clients[uid].disconnect()
        await bot.send_message(uid, "🔴 Logout Successful. Session Cleared.")

@bot.message_handler(func=lambda m: (m.from_user.id in user_states))
async def login_flow(m):
    uid = m.from_user.id
    state = user_states[uid].get('step')

    if state == 'api' and ':' in m.text:
        try:
            aid, ahash = m.text.split(':', 1)
            user_states[uid].update({'api_id': aid.strip(), 'api_hash': ahash.strip(), 'step': 'phone'})
            await bot.send_message(uid, "📱 Send Phone Number (+880...):")
        except: await bot.send_message(uid, "❌ Format error. Use `API_ID:API_HASH`")
    
    elif state == 'phone':
        user_states[uid]['phone'] = m.text.strip()
        client = TelegramClient(StringSession(), int(user_states[uid]['api_id']), user_states[uid]['api_hash'])
        await client.connect()
        try:
            sent = await client.send_code_request(user_states[uid]['phone'])
            user_states[uid].update({'hash': sent.phone_code_hash, 'step': 'otp', 'client': client})
            await bot.send_message(uid, "📩 Enter OTP Code (Example: 1 2 3 4 5):")
        except Exception as e:
            await bot.send_message(uid, f"❌ Error: {e}")
            user_states.pop(uid)

    elif state == 'otp':
        try:
            client = user_states[uid]['client']
            otp = m.text.replace(' ','')
            await client.sign_in(user_states[uid]['phone'], otp, phone_code_hash=user_states[uid]['hash'])
            ss = client.session.save()
            db_query('UPDATE users SET api_id=?, api_hash=?, string_session=?, is_active=1 WHERE user_id=?', 
                      (user_states[uid]['api_id'], user_states[uid]['api_hash'], ss, uid))
            await bot.send_message(uid, "✅ 𝙻𝚘𝚐𝚒𝚗 𝚂𝚞𝚌𝚌𝚎𝚜𝚜! Ghost Mode Active.")
            asyncio.create_task(start_user_listener(uid, user_states[uid]['api_id'], user_states[uid]['api_hash'], ss))
            user_states.pop(uid)
        except errors.SessionPasswordNeededError:
            user_states[uid]['step'] = '2fa'
            await bot.send_message(uid, "🔐 Enter 2FA Password:")
        except Exception as e: await bot.send_message(uid, f"❌ OTP Error: {e}")

    elif state == '2fa':
        try:
            client = user_states[uid]['client']
            await client.sign_in(password=m.text.strip())
            ss = client.session.save()
            db_query('UPDATE users SET string_session=?, is_active=1 WHERE user_id=?', (ss, uid))
            await bot.send_message(uid, "✅ Login Success with 2FA.")
            data = user_states[uid]
            asyncio.create_task(start_user_listener(uid, data['api_id'], data['api_hash'], ss))
            user_states.pop(uid)
        except Exception as e: await bot.send_message(uid, f"❌ 2FA Error: {e}")

    elif state == 'wait_reply':
        db_query('UPDATE users SET custom_reply=? WHERE user_id=?', (m.text, uid))
        await bot.send_message(uid, "✅ 𝚁𝚎𝚙𝚕𝚢 𝚂𝚊𝚟𝚎𝚍. People will receive this message when you are offline.")
        user_states.pop(uid)

@bot.message_handler(func=lambda m: m.text == "✏️ Set Reply")
async def set_rep(m):
    user_states[m.from_user.id] = {'step': 'wait_reply'}
    await bot.send_message(m.chat.id, "✏️ 𝙲𝚞𝚜𝚝𝚘𝚖 𝙰𝚞𝚝𝚘 𝚁𝚎𝚙𝚕𝚢\n\nঅফলাইনে থাকাকালীন যে মেসেজটি দিতে চান তা লিখে পাঠান।")

@bot.message_handler(func=lambda m: m.text == "📊 Status")
async def status_check(m):
    uid = m.from_user.id
    row = db_query('SELECT custom_reply, is_active, is_enabled FROM users WHERE user_id=?', (uid,), True)
    if row and row[0][1] == 1:
        s = "🟢 Active" if row[0][2] == 1 else "🔴 Disabled"
        await bot.send_message(uid, f"📊 𝚂𝚝𝚊𝚝𝚞𝚜\n\nReply: `{row[0][0]}`\nBot: {s}\nMode: Ghost (Auto-Offline)")
    else:
        await bot.send_message(uid, "❌ Your account is not connected.")

@bot.message_handler(commands=['admin'])
async def admin_cmd(m):
    if m.from_user.id != ADMIN_ID: return
    zip_p = "backup.zip"
    with zipfile.ZipFile(zip_p, 'w') as z:
        if os.path.exists(DB_NAME): z.write(DB_NAME)
    with open(zip_p, 'rb') as f:
        await bot.send_document(m.chat.id, f, caption="📂 Phantom DB Backup")
    os.remove(zip_p)

# --- Startup ---
async def start_all():
    init_db()
    users = db_query('SELECT user_id, api_id, api_hash, string_session FROM users WHERE is_active=1', fetch=True)
    if users:
        for u in users:
            if all(u): asyncio.create_task(start_user_listener(u[0], u[1], u[2], u[3]))

async def main():
    await start_all()
    print(f"Phantom Ghost System Running | {CREDIT}")
    await bot.polling(non_stop=True)

if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
