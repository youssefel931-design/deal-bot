import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime
import hashlib

URL = "https://www.mainz-tauschen-verschenken.de/"

TOKEN = "8704089663:AAGwNXYGJu20o2jQs-tGLyIxZqmPG2jxMx8"
CHAT_ID = "7520498009"

HEADERS = {"User-Agent": "Mozilla/5.0"}

SEEN_FILE = "seen.txt"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        print("⚠️ seen.txt nicht gefunden → starte leer")
        return set()
    with open(SEEN_FILE, "r") as f:
        data = set(line.strip() for line in f)
        print(f"📂 {len(data)} gespeicherte Anzeigen geladen")
        return data


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        for item in seen:
            f.write(item + "\n")
    print(f"💾 {len(seen)} Anzeigen gespeichert")


def make_id(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def send(msg):
    print("📲 Sende Nachricht...")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def check(seen):
    print("🔄 Neuer Check startet...")

    r = requests.get(URL, headers=HEADERS, timeout=10)
    print("🌐 Status:", r.status_code)

    soup = BeautifulSoup(r.text, "html.parser")

    ads = soup.select("article")
    print(f"📦 {len(ads)} Anzeigen gefunden")

    new_seen = set(seen)

    new_count = 0

    for ad in ads:
        text = ad.get_text(strip=True)
        ad_id = make_id(text)

        if ad_id in seen:
            print("⏭️ Schon gesehen")
            continue

        print("🆕 Neue Anzeige entdeckt!")
        new_seen.add(ad_id)
        new_count += 1

        send("🆕 Neue Anzeige:\n" + text)

    print(f"✅ {new_count} neue Anzeigen in diesem Durchlauf")

    return new_seen


def get_sleep_time():
    hour = datetime.now().hour
    if hour >= 23 or hour < 6:
        return 1800
    else:
        return 180


print("🚀 Bot gestartet")

seen = load_seen()

while True:
    try:
        seen = check(seen)
        save_seen(seen)
        print("⏰ Check fertig:", datetime.now())

    except Exception as e:
        print("❌ Fehler:", e)

    sleep_time = get_sleep_time()
    print(f"😴 Schlafe {sleep_time} Sekunden...\n")
    time.sleep(sleep_time)

  
