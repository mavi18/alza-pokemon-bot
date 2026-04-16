import asyncio
import json
import logging
import os
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "alza_pokemon_bot_97422555")
# Base URL without the # filters to be less suspicious
ALZA_URL = "https://www.alza.sk/hracky/pokemon-karty/18879069.htm"
SEEN_FILE = "seen_products.json"

def load_seen_products():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                content = f.read()
                if not content: return set()
                return set(json.loads(content))
        except Exception as e:
            logger.error(f"Error loading seen products: {e}")
            return set()
    return set()

def save_seen_products(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.error(f"Error saving seen products: {e}")

def send_notification(message):
    try:
        url = f"https://ntfy.sh/{NTFY_TOPIC}"
        headers = {
            "Title": "Alza Pokémon Alert!",
            "Priority": "high",
            "Tags": "dragon,pokemon,shopping_cart"
        }
        response = requests.post(url, data=message.encode('utf-8'), headers=headers)
        response.raise_for_status()
        logger.info(f"Notification sent to topic: {NTFY_TOPIC}")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

async def check_alza(seen_products):
    async with async_playwright() as p:
        # Switching to Firefox as it often has different fingerprinting results
        logger.info("Launching Firefox...")
        browser = await p.firefox.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        # Note: playwright-stealth works best with Chromium, but we'll try a light version for Firefox
        # or just rely on Firefox's native behavior.
        
        logger.info(f"Navigating to Alza: {ALZA_URL}")
        try:
            # Using a slower, more patient navigation
            await page.goto(ALZA_URL, wait_until="domcontentloaded", timeout=90000)
            
            # Wait to see if we get challenged
            await asyncio.sleep(15) 
            
            content = await page.content()
            if "Verify you are human" in content or "PÍP PÍP TUTÚT" in content:
                logger.warning("Cloudflare challenge detected. Trying to wait it out...")
                await asyncio.sleep(20)
                # Take a screenshot to see if it cleared
                await page.screenshot(path="error.png")
                
            # Wait for any grid items to appear
            try:
                await page.wait_for_selector(".browsingitem", timeout=30000)
            except Exception:
                logger.warning("Still no products found. Possible block. Check error.png")
                await page.screenshot(path="error.png")
                await browser.close()
                return

            items = await page.query_selector_all(".browsingitem")
            logger.info(f"Found {len(items)} products in total. Filtering for available...")

            new_products = []
            for item in items:
                # Check for "Skladom" or "Kúpiť" button which indicates availability
                # If the item is "Tešíme sa" (upcoming) or "Vypredané" (sold out), we skip it.
                stock_elem = await item.query_selector(".browsingitem-stock, .btnk1")
                stock_text = await stock_elem.inner_text() if stock_elem else ""
                
                # Alza labels available items as "Skladom" or has a buy button
                if "Skladom" in stock_text or stock_elem:
                    title_elem = await item.query_selector("a.browsingitem-title")
                    price_elem = await item.query_selector(".price-box__price")
                    
                    if title_elem:
                        title = (await title_elem.inner_text()).strip()
                        href = await title_elem.get_attribute("href")
                        url = "https://www.alza.sk" + href if href.startswith("/") else href
                        price = (await price_elem.inner_text()).strip() if price_elem else "N/A"
                        
                        product_id = f"{title}_{price}"
                        if product_id not in seen_products:
                            new_products.append(f"📦 {title}\n💰 {price}\n🔗 {url}")
                            seen_products.add(product_id)

            if new_products:
                chunk_size = 5
                for i in range(0, len(new_products), chunk_size):
                    chunk = new_products[i:i + chunk_size]
                    message = "\n\n".join(chunk)
                    send_notification(message)
                
                save_seen_products(seen_products)
                logger.info(f"Notified about {len(new_products)} products.")
            else:
                logger.info("No available or new products found.")

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            await page.screenshot(path="error.png")
        
        await browser.close()

async def main():
    logger.info("Starting Alza Pokémon Bot (Firefox Run)...")
    seen_products = load_seen_products()
    try:
        await check_alza(seen_products)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    logger.info("Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
