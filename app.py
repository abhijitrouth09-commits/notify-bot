import os
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"
    }
}

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

last_episodes = {}

# ====================== FETCH FUNCTION ======================
def get_latest_episode(show_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(show_url, headers=headers, timeout=15)

        if r.status_code != 200:
            return None, "❌ Failed to load page"

        soup = BeautifulSoup(r.text, "html.parser")

        # 🔥 Extract latest episode link
        latest = soup.find("a", class_="iconsWrap latest")

        if latest and latest.get("href"):
            episode_url = "https://www.zee5.com" + latest.get("href")
            return episode_url, "✅ Latest episode found"

        return None, "❌ Latest episode not found"

    except Exception as e:
        return None, f"❌ Error: {e}"

# ====================== MAIN CHECK ======================
def check_for_new_episodes(debug_chat=None):
    chat_id = debug_chat if debug_chat else ADMIN_CHAT_ID

    bot.send_message(chat_id, "🔥 FUNCTION STARTED")

    for show_key, info in SHOWS.items():
        bot.send_message(chat_id, f"📺 Checking: {info['name']}")

        latest, status = get_latest_episode(info["url"])

        bot.send_message(chat_id, f"🧾 Status: {status}")

        if latest:
            bot.send_message(chat_id, f"🎬 Latest URL:\n{latest}")

            old = last_episodes.get(show_key)

            if old != latest:
                last_episodes[show_key] = latest

                message = f"""🚨 *NEW EPISODE ALERT!* 🎉

📺 *Show:* {info["name"]}

🔥 [Watch Now]({latest})
"""

                bot.send_message(ADMIN_CHAT_ID, message, parse_mode='Markdown')
                bot.send_message(chat_id, "✅ Alert sent!")

            else:
                bot.send_message(chat_id, "ℹ️ No new episode")

        else:
            bot.send_message(chat_id, "⚠️ No result returned")

    bot.send_message(chat_id, "✅ CHECK DONE")

# ====================== ROUTES ======================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

# ====================== COMMANDS ======================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot is alive!\n\nUse /check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes(debug_chat=message.chat.id)
    else:
        bot.reply_to(message, "❌ Owner only")

# ====================== SCHEDULER ======================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()

# ====================== MAIN ======================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
