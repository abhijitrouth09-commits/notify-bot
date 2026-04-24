import os
import json
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# ========================= CONFIG =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"
    }
    # Add more shows later here
}

DATA_FILE = "last_episodes.json"
# =======================================================

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

last_episodes = load_data()

def get_latest_episode(show_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(show_url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # IMPROVED: Matches current Zee5 structure (E288 22m 23 Apr)
        for h3 in soup.find_all('h3'):
            text = h3.get_text(strip=True)
            if text.startswith('E') and any(c.isdigit() for c in text[:6]):
                return text[:250]
        
        # Fallback
        for el in soup.find_all(['h3', 'div', 'p', 'span']):
            txt = el.get_text(strip=True)
            if any(f"E{num}" in txt for num in range(270, 400)):
                return txt[:250]
        return None
    except Exception as e:
        print("Fetch error:", e)
        return None

def check_for_new_episodes():
    global last_episodes
    print(f"[{time.strftime('%H:%M:%S')}] Checking Zee5...")
    for show_key, info in SHOWS.items():
        latest = get_latest_episode(info["url"])
        if not latest:
            continue
        old = last_episodes.get(show_key)
        if old != latest:
            last_episodes[show_key] = latest
            save_data(last_episodes)
            message = f"""🚨 **NEW EPISODE ALERT!**

**Show**: {info["name"]}
**Latest**: {latest}

🔗 {info["url"]}"""
            try:
                bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
                print(f"✅ Sent alert for {info['name']}")
            except Exception as e:
                print("Telegram error:", e)

# ====================== WEBHOOK ======================
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = request.get_json()
        bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Zee5 Bot is alive on Render!\n\n/check → manual check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking now...")
        check_for_new_episodes()
        bot.reply_to(message, "✅ Check done!")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

# ====================== SCHEDULER ======================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=25)
    scheduler.start()
    print("🚀 Scheduler started - checking every 25 minutes")

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
