import os
import time
import json
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

SHOWS = {
    "tumm-se-tumm-tak": {
        "name": "Tumm Se Tum Tak",
        "url": "https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/0-6-4z5727104"
    }
}

DATA_FILE = "last_episodes.json"

# ================= INIT =================
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ================= LOAD DATA =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        last_episodes = json.load(f)
else:
    last_episodes = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(last_episodes, f)

# ================= FETCH + PARSE =================
def get_latest_episode(show_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

        r = requests.get(show_url, headers=headers, timeout=15)

        if r.status_code != 200:
            return None, f"❌ Status {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")

        images = soup.find_all("img")

        episodes = []

        for img in images:
            title = img.get("title") or img.get("alt")

            if title and "Episode" in title:
                match = re.search(r"Episode\s*(\d+)", title)
                if match:
                    ep_num = int(match.group(1))
                    src = img.get("src", "")

                    id_match = re.search(r"/resources/([^/]+)/", src)
                    ep_id = id_match.group(1) if id_match else None

                    if ep_id:
                        episodes.append({
                            "num": ep_num,
                            "id": ep_id,
                            "title": title
                        })

        if not episodes:
            return None, "❌ No episodes found"

        latest = max(episodes, key=lambda x: x["num"])

        ep_url = f"https://www.zee5.com/tv-shows/details/tumm-se-tumm-tak/{latest['id']}"

        return {
            "url": ep_url,
            "num": latest["num"],
            "title": latest["title"]
        }, "✅ Found"

    except Exception as e:
        return None, f"❌ Error: {e}"

# ================= CHECK =================
def check_for_new_episodes(debug_chat=None):
    chat_id = debug_chat if debug_chat else ADMIN_CHAT_ID

    bot.send_message(chat_id, "🔥 FUNCTION STARTED")

    for key, info in SHOWS.items():
        bot.send_message(chat_id, f"📺 Checking: {info['name']}")

        result, status = get_latest_episode(info["url"])

        bot.send_message(chat_id, f"🧾 Status: {status}")

        if result:
            bot.send_message(chat_id, f"🎬 Episode {result['num']}")
            bot.send_message(chat_id, f"🔗 {result['url']}")

            old = last_episodes.get(key)

            if old != result["url"]:
                last_episodes[key] = result["url"]
                save_data()

                msg = f"""🚨 *NEW EPISODE*

📺 {info["name"]}
🎬 Episode {result["num"]}

🔥 [Watch Now]({result["url"]})
"""
                bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
                bot.send_message(chat_id, "✅ Alert sent")
            else:
                bot.send_message(chat_id, "ℹ️ No new episode")
        else:
            bot.send_message(chat_id, "⚠️ No result returned")

    bot.send_message(chat_id, "✅ CHECK DONE")

# ================= FLASK =================
@app.route('/', methods=['GET'])
def home():
    return "Bot Running ✅", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = request.get_json()
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return '', 200

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ Bot running\nUse /check")

@bot.message_handler(commands=['check'])
def manual_check(message):
    if message.chat.id == ADMIN_CHAT_ID:
        bot.reply_to(message, "🔄 Checking...")
        check_for_new_episodes(debug_chat=message.chat.id)
    else:
        bot.reply_to(message, "❌ Owner only")

# ================= SCHEDULER =================
def run_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_new_episodes, 'interval', minutes=5)
    scheduler.start()

# ================= MAIN =================
if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)

    bot.set_webhook(
        url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
