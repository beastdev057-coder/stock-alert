"""
GitHub Actions ke liye: products ko EK baar check karta hai aur band ho jata hai.
GitHub har 10 minute baad isay dobara chalata hai.

Token aur chat ids code mein NAHI hain. Wo GitHub Secrets se aate hain:
    TELEGRAM_TOKEN      = bot token
    TELEGRAM_CHAT_IDS   = 7308895513,5885959057   (comma se alag)
"""

import json
import os
import random
import sys
import time

import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_IDS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]

WARN_AFTER_FAILS = 4  # itni baar lagatar fail ho (10 min x 4 = ~40 min) to warning bhejein
STATE_FILE = "state.json"
BLOCK_HINTS = ["access denied", "captcha", "are you a human", "unusual traffic", "403 forbidden"]

OUT_WORDS = ["currently unavailable", "sold out", "out of stock", "notify me", "coming soon", "not available for purchase", "item not available", "temporarily unavailable"]
IN_WORDS = ["buy now", "add to cart"]

PRODUCTS = [
    {
        "name": "PSN Gift Card Rs 3000 (Flipkart)",
        "url": (
            "https://www.flipkart.com/sony-interactive-entertainment-europe-rs-3000-"
            "playstation-store-gift-card-digital-voucher-delivery-email/p/itma3cec289dd512"
            "?pid=DGVHGEX6BGYDMJGZ"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "PSN Gift Card Rs 5000 (Flipkart)",
        "url": (
            "https://www.flipkart.com/sony-interactive-entertainment-rs-5000-"
            "playstation-store-gift-card/p/itm5b2422845fb13?pid=DGVHBGFX4BNWKEWB"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "PSN Gift Card Rs 2000 (Flipkart)",
        "url": (
            "https://www.flipkart.com/playstation-rs-2000-inr-gift-card/p/"
            "itmd41e56cc4ca04?pid=DGVH9SWYHVTXSFNX"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "GamesTheShop Product 1",
        "url": (
            "https://www.gamestheshop.com/product/2153a461-7203-4802-aac4-283be4c775d3"
            "?variant=09df672e-b598-4b2d-9b3e-e1ca1dd9d205"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "GamesTheShop Product 2",
        "url": (
            "https://www.gamestheshop.com/product/d117bc23-1c4b-4330-b7f3-f90c71d9a5b3"
            "?variant=cb05d659-beac-47d7-85ff-8bfed95f47cf"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "GamesTheShop Product 3",
        "url": (
            "https://www.gamestheshop.com/product/f528de33-a760-4fea-9b04-3d150b24a116"
            "?variant=7e6631a0-0d65-4907-89b7-4ab5e24397cc"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
    {
        "name": "GamesTheShop Product 4",
        "url": (
            "https://www.gamestheshop.com/product/57ffc696-2241-45b1-af43-736209293710"
            "?variant=9d31fdcf-28e8-451c-b3f7-a89a88b86a6f"
        ),
        "selector": None,
        "out_of_stock_text": OUT_WORDS,
        "in_stock_text": IN_WORDS,
    },
]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def notify(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            r = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=15)
            if not r.ok:
                print(f"[!] {chat_id} ko message nahi gaya: {r.text}")
        except requests.RequestException as e:
            print(f"[!] {chat_id} ko Telegram notification fail hui: {e}")


def get_status(context, product, index):
    """Returns 'in', 'out', 'unknown' ya 'blocked'."""
    page = context.new_page()
    try:
        page.goto(product["url"], wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)  # JS ko page banane ka waqt dein

        text = page.inner_text(product.get("selector") or "body").lower()

        if any(h in text for h in BLOCK_HINTS):
            status = "blocked"
        elif any(t.lower() in text for t in product["out_of_stock_text"]):
            status = "out"
        elif any(t.lower() in text for t in product["in_stock_text"]):
            status = "in"
        else:
            status = "unknown"

        if status in ("unknown", "blocked"):
            page.screenshot(path=f"debug_{index}.png")
        return status
    finally:
        page.close()


def main():
    if not TELEGRAM_TOKEN or not CHAT_IDS:
        print("TELEGRAM_TOKEN ya TELEGRAM_CHAT_IDS secret set nahi hai.")
        sys.exit(1)

    state = load_state()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            locale="en-IN",
            viewport={"width": 1366, "height": 768},
        )

        for i, p in enumerate(PRODUCTS):
            url = p["url"]
            entry = state.setdefault(url, {"status": None, "fails": 0, "warned": False})

            try:
                status = get_status(context, p, i)
            except Exception as e:  # network/timeout/page error
                print(f"[!] {p['name']}: error ({e})")
                status = "error"

            print(f"{p['name']}: {status}")

            if status in ("in", "out"):
                if status == "in" and entry["status"] != "in":
                    notify(f"✅ {p['name']} ab STOCK mein hai!\n{url}")
                entry["status"] = status
                entry["fails"] = 0
                entry["warned"] = False
            else:
                entry["fails"] += 1
                if entry["fails"] >= WARN_AFTER_FAILS and not entry["warned"]:
                    entry["warned"] = True
                    notify(
                        f"⚠️ {p['name']}: {entry['fails']} baar status samajh nahi aaya "
                        f"({status}). Ho sakta hai site ne GitHub ko block kiya ya layout badal gaya."
                    )

            time.sleep(random.uniform(3, 8))

        browser.close()

    save_state(state)


if __name__ == "__main__":
    main()
