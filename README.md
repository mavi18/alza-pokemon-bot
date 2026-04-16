# Alza Pokémon TCG Availability Bot

A Python bot that monitors Alza.sk for available Pokémon TCG products and sends notifications via [ntfy.sh](https://ntfy.sh).

## Features
- **Cloudflare Bypass**: Uses Playwright and `playwright-stealth` to mimic real browser behavior.
- **Smart Notifications**: Only notifies you when *new* products appear or when prices change.
- **iPhone Alerts**: Integrated with `ntfy` for instant push notifications on your phone.
- **Configurable**: Easily change the check interval and URL.

## Setup

### 1. Prerequisites
- Python 3.8+
- [ntfy app](https://apps.apple.com/us/app/ntfy/id1625396347) installed on your iPhone.

### 2. Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Configuration
1. Open the `ntfy` app on your iPhone.
2. Subscribe to the topic: `alza_pokemon_bot_97422555` (or whatever is in your `.env` file).
3. (Optional) Customize the `.env` file if you want to change the URL or interval.

### 4. Usage
```bash
python main.py
```

## How it works
- The bot runs in a loop (default: every 5 minutes).
- It opens a headless browser, navigates to the specified Alza URL, and waits for products to load.
- It compares found products against `seen_products.json`.
- If new products are found, it sends a notification with the product name, price, and a direct link.
