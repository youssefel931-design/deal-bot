import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

URL = "https://www.mainz-tauschen-verschenken.de/"

TOKEN = "8704089663:AAGwNXYGJu20o2jQs-tGLyIxZqmPG2jxMx8"
CHAT_ID = "7520498009"

HEADERS = {"User-Agent": "Mozilla/5.0"}

SEEN_FILE = "seen.txt"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(line.strip() for line in f)


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        for item in seen:
            f.write(item + "\n")


def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def check(seen):
    r = requests.get(URL, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    ads = soup.select("article")

    new_seen = set(seen)

    for ad in ads:
        text = ad.get_text(strip=True)

        if text not in seen:
            new_seen.add(text)
            send("🆕 Neue Anzeige:\n" + text)

    return new_seen


seen = load_seen()

seen = check(seen)

save_seen(seen)

print("Check fertig")
