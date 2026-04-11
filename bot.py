import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


SOURCES = [
    {"name": "Mainz", "url": "https://www.mainz-tauschen-verschenken.de/"},
    {"name": "ELW", "url": "https://www.elw-verschenkmarkt.de/"},
    {"name": "Hanau", "url": "https://hanau.verschenkmarkt.info/"},
    {"name": "Offenbach", "url": "https://region-offenbach.verschenkmarkt.info/"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

STATE_FILE = Path("state.json")
REQUEST_TIMEOUT = 20


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Umgebungsvariable fehlt: {name}")
    return value


def load_state() -> dict[str, list[str]]:
    if not STATE_FILE.exists():
        return {}

    with STATE_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        return {}

    clean_state: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, list):
            clean_state[key] = [item for item in value if isinstance(item, str)]
    return clean_state


def save_state(state: dict[str, list[str]]) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def normalize_listing_url(base_url: str, href: str) -> str | None:
    href = href.strip()
    if not href:
        return None

    full_url = urljoin(base_url, href)

    if "_i" not in full_url:
        return None

    return full_url


def extract_listing_urls(source_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found_urls: list[str] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        full_url = normalize_listing_url(source_url, link["href"])
        if not full_url or full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        found_urls.append(full_url)

    return found_urls


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def fetch_source(source: dict[str, str]) -> list[str]:
    response = requests.get(
        source["url"],
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return extract_listing_urls(source["url"], response.text)


def get_sleep_seconds() -> int:
    hour = datetime.now().hour
    if hour >= 23 or hour < 6:
        return 1800
    return 180


def bootstrap_source(state: dict[str, list[str]], source_name: str, listings: list[str]) -> None:
    if source_name not in state:
        state[source_name] = listings
        print(f"[{source_name}] Erster Start: {len(listings)} Anzeigen gespeichert, nichts gesendet.")


def process_source(
    token: str,
    chat_id: str,
    state: dict[str, list[str]],
    source: dict[str, str],
) -> None:
    source_name = source["name"]
    listings = fetch_source(source)
    print(f"[{source_name}] {len(listings)} Anzeigen gefunden.")

    bootstrap_source(state, source_name, listings)
    previous = set(state.get(source_name, []))

    new_listings = [url for url in listings if url not in previous]

    for url in new_listings:
        message = f"Neue Anzeige auf {source_name}:\n{url}"
        send_telegram_message(token, chat_id, message)
        print(f"[{source_name}] Gesendet: {url}")

    state[source_name] = listings


def main() -> None:
    token = require_env("TELEGRAM_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")
    state = load_state()

    print("Bot gestartet.")

    while True:
        cycle_started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Neuer Durchlauf: {cycle_started}")

        for source in SOURCES:
            try:
                process_source(token, chat_id, state, source)
            except Exception as exc:
                print(f"[{source['name']}] Fehler: {exc}")

        save_state(state)
        sleep_seconds = get_sleep_seconds()
        print(f"Durchlauf beendet. Warte {sleep_seconds} Sekunden.")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
