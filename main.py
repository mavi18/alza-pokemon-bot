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
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))
SEEN_FILE = "seen_products.json"

def load_seen_products():
    """Load previously seen products from a JSON file."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                content = f.read()
                if not content:
                    return set()
                return set(json.loads(content))
        except Exception as e:
            logger.error(f"Error loading seen products: {e}")
            return set()
    return set()

def save_seen_products(seen):
    """Save seen products to a JSON file."""
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.error(f"Error saving seen products: {e}")

def send_notification(message):
    """Send a notification to the ntfy topic."""
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
    """Scrape Alza for products and notify if new ones are found."""
    if not ALZA_URL:
        logger.error("ALZA_URL is not set! Please add it to GitHub Secrets.")
        return

    async with async_playwright() as p:
        # Launch chromium
        browser = await p.chromium.launch(headless=True)
        
        # Use a realistic user agent and stealth
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # Apply stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(page)

        logger.info(f"Checking Alza URL: {ALZA_URL}")
        try:
            # Navigate to URL - using domcontentloaded is more reliable for sites with heavy tracking
            await page.goto(ALZA_URL, wait_until="domcontentloaded", timeout=90000)
            
            # Wait for the specific filtering to be reflected in the URL or page state
            # Alza often applies filters after load. We wait for the grid to stabilize.
            await page.wait_for_timeout(10000) # Increased to 10 seconds for GitHub Actions latency
            
            # Wait for the product grid to be visible
            try:
                await page.wait_for_selector(".browsingitem", timeout=30000)
            except Exception:
                logger.warning("Product selector '.browsingitem' not found within timeout. Page might be empty or blocked. Taking screenshot...")
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
                    
                    # Create a unique ID for the product (title + price to catch price drops too)
                    product_id = f"{title}_{price}"
                    
                    if product_id not in seen_products:
                        new_products.append(f"📦 {title}\n💰 {price}\n🔗 {url}")
                        seen_products.add(product_id)

            if new_products:
                # Send notifications in chunks
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
