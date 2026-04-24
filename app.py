import os
import json
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import re

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {"name": "Tumm Se Tum Tak", "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"},
    "saru": {"name": "Saru", "url": "https://www.zee5.com/tv-shows/details/saru/0-6-4z5727070"},
    "vasudha": {"name": "Vasudha", "url": "https://www.zee5.com/tv-shows/details/vasudha/0-6-4z5612471"},
    "jagadhatri": {"name": "Jagadhatri", "url": "https://www.zee5.com/tv-shows/details/jagadhatri/0-6-4z5853175"},
    "lakshmi-nivas": {"name": "Lakshmi Nivas", "url": "https://www.zee5.com/tv-shows/details/lakshmi-nivas/0-6-4z5891598"},
    "ganga-mai-ki-betiyan": {"name": "Ganga Mai Ki Betiyan", "url": "https://www.zee5.com/tv-shows/details/ganga-mai-ki-betiyan/0-6-4z5793364"},
    "jaane-anjaane-hum-mile": {"name": "Jaane Anjaane Hum Mile", "url": "https://www.zee5.com/tv-shows/details/jaane-anjaane-hum-mile/0-6-4z5646159"}
}

DATA_FILE = "last_episodes.json"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

last_episodes = {}

def get_latest_episode(show_url, show_name):
    debug_lines = [f"🔍 Checking: {show_name}"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        r = requests.get(show_url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator=" | ")

        debug_lines.append(f"Page length: {len(text)} characters")

        # Strong patterns
        match = re.search(r'E\d+\s+\d+m?\s+\d+\s+[A-Za-z]+', text)
        if match:
            episode = match.group(0)
            debug_lines.append(f"✅ STRONG MATCH FOUND: {episode}")
            return episode, "\n".join(debug_lines)

        match = re.search(r'E\d+', text)
        if match:
            episode = match.group(0)
            debug_lines.append(f"✅ BASIC MATCH FOUND: {episode}")
            return episode, "\n".join(debug_lines)

        debug_lines.append("❌ No episode pattern found")
        return None, "\n".join(debug_lines)

    except Exception as e:
        debug_lines.append(f"❌ Error: {e}")
        return None, "\n".join(debug_lines)

def check_for_new_episodes():
    global last_episodes
    full_debug = ["🔄 **CHECK STARTED**"]

    for show_key, info in SHOWS.items():
        latest, debug_text = get_latest_episode(info["url"], info["name"])
        full_debug.append(debug_text)

        if latest:
            old = last_episodes.get(show_key)
            if old != latest:
                last_episodes[show_key] = latest
                message = f"""🚨 **NEW EPISODE ALERT!** 🎉

📺 Show: {info["name"]}
🎬 Latest: {latest}

🔥 [Watch Now]({info["url"]})"""
                bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')

    full_debug.append("✅ **CHECK FINISHED**")
    bot.send_message(ADMIN_CHAT_ID, "\n\n".join(full_debug), parse_mode='Markdown')

# ====================== BASIC SETUP ======================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot is alive!\n\n/check → test with debug\n/reset → clear data")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Running full check with debug...")
        check_for_new_episodes()
    else:
        bot.reply_to(message, "❌ Only owner can use.")

@bot.message_handler(commands=['reset'])
def reset(message):
    if message.chat.id == ADMIN_CHAT_ID:
        global last_episodes
        last_episodes = {}
        bot.reply_to(message, "✅ All saved episodes cleared.")
    else:
        bot.reply_to(message, "❌ Only owner can use.")

# ====================== SCHEDULER ======================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}")
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
