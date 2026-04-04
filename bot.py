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
    try:
        print("Bot läuft...")

        r = requests.get(URL, headers=HEADERS, timeout=10)
        print("Seite geladen:", r.status_code)

        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a", href=True)

        new_seen = set(seen)
        current_links = set()  # 👈 NEU (gegen doppelte Links)
        found = 0

        for link in links:
            href = link["href"]

            if "_i" in href:
                # fix für // links
                if href.startswith("//"):
                    href = "https:" + href

                # 👇 verhindert doppelte auf EINER Seite
                if href in current_links:
                    continue

                current_links.add(href)

                # 👇 verhindert doppelte über mehrere Runs
                if href not in seen:
                    found += 1
                    new_seen.add(href)

                    print("Neue Anzeige:", href)
                    send("🆕 Neue Anzeige:\n" + href)

        print("Neue gefunden:", found)

        return new_seen

    except Exception as e:
        print("Fehler:", e)
        return seen

seen = load_seen()

seen = check(seen)

save_seen(seen)

print("Check fertig")
