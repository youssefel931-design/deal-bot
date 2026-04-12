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

STATE_FILE = Path("/data/state.json")
REQUEST_TIMEOUT = 20
TELEGRAM_CAPTION_LIMIT = 1024


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


def clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def first_meta_content(soup: BeautifulSoup, attrs_list: list[dict[str, str]]) -> str | None:
    for attrs in attrs_list:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return None


def fetch_listing_details(url: str) -> dict[str, str]:
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = (
        first_meta_content(
            soup,
            [{"property": "og:title"}, {"name": "twitter:title"}],
        )
        or (clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else "")
        or clean_text(soup.title.get_text(" ", strip=True))
    )

    image_url = first_meta_content(
        soup,
        [{"property": "og:image"}, {"name": "twitter:image"}],
    )

    if not image_url:
        image = soup.find("img")
        if image and image.get("src"):
            image_url = urljoin(url, image["src"])

    return {
        "title": title or "Neue Anzeige",
        "image_url": image_url or "",
    }


def build_message(source_name: str, url: str, details: dict[str, str]) -> str:
    return f"Neue Anzeige auf {source_name}\n{details['title']}\n{url}"


def send_telegram_message(token: str, chat_id: str, message: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": "false"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def send_telegram_photo(token: str, chat_id: str, photo_url: str, caption: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption[:TELEGRAM_CAPTION_LIMIT],
        },
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
        try:
            details = fetch_listing_details(url)
            message = build_message(source_name, url, details)

            if details.get("image_url"):
                send_telegram_photo(token, chat_id, details["image_url"], message)
            else:
                send_telegram_message(token, chat_id, message)

            print(f"[{source_name}] Gesendet: {url}")
        except Exception as exc:
            fallback_message = f"Neue Anzeige auf {source_name}\n{url}"
            send_telegram_message(token, chat_id, fallback_message)
            print(f"[{source_name}] Detailfehler ({exc}). Fallback gesendet: {url}")

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
