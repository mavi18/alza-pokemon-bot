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
ALZA_URL = os.getenv("ALZA_URL")
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
    if not ALZA_URL:
        logger.error("ALZA_URL is not set!")
        return

    async with async_playwright() as p:
        # Launch chromium with some additional args to look less like a bot
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False
        )
        
        page = await context.new_page()
        
        # Apply more aggressive stealth
        stealth = Stealth(
            navigator_vendor_override='Google Inc.',
            webgl_vendor_override='Intel Inc.',
            webgl_renderer_override='Intel Iris OpenGL Engine',
            navigator_user_agent_override='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            navigator_platform_override='Win32'
        )
        await stealth.apply_stealth_async(page)

        logger.info(f"Navigating to Alza...")
        try:
            # First attempt
            await page.goto(ALZA_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Check for Cloudflare Challenge
            for attempt in range(3):
                content = await page.content()
                if "Verify you are human" in content or "cf-challenge" in content or "cf-wrapper" in content:
                    logger.info(f"Cloudflare challenge detected. Waiting... (Attempt {attempt+1}/3)")
                    # Move mouse randomly to look human
                    await page.mouse.move(100, 100)
                    await asyncio.sleep(1)
                    await page.mouse.move(200, 300)
                    await asyncio.sleep(15) # Wait for auto-solve
                else:
                    break

            # Check if still on challenge page
            if "Verify you are human" in await page.content():
                logger.warning("Still blocked by Cloudflare after waiting. Taking screenshot...")
                await page.screenshot(path="error.png")
                await browser.close()
                return

            # Wait for products
            logger.info("Waiting for products to load...")
            await asyncio.sleep(5) 
            
            try:
                await page.wait_for_selector(".browsingitem", timeout=30000)
            except Exception:
                logger.warning("Product grid not found. Page might be empty or blocked. Taking screenshot...")
                await page.screenshot(path="error.png")
                await browser.close()
                return

            items = await page.query_selector_all(".browsingitem")
            logger.info(f"Found {len(items)} products.")

            new_products = []
            for item in items:
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
                logger.info(f"Notified about {len(new_products)} new products.")
            else:
                logger.info("No new products found.")

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            await page.screenshot(path="error.png")
        
        await browser.close()

async def main():
    logger.info("Starting Alza Pokémon Bot (Single Run)...")
    seen_products = load_seen_products()
    try:
        await check_alza(seen_products)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    logger.info("Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
