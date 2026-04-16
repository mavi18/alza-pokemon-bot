import asyncio
import json
import logging
import os
import nodriver as uc
import requests
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "alza_pokemon_bot_97422555")
ALZA_URL = "https://www.alza.sk/hracky/pokemon-karty/18879069.htm#f&availabilityFilterValue=1&cud=0&pg=1&prod=3460&sc=890"
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
    logger.info("Starting nodriver browser...")
    # nodriver starts a real browser and connects via CDP
    browser = await uc.start(
        browser_args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    
    try:
        logger.info(f"Navigating to {ALZA_URL}...")
        page = await browser.get(ALZA_URL)
        
        # nodriver handles Turnstile/Managed Challenges naturally
        # We wait for the products to appear
        logger.info("Waiting for products to load (max 60s)...")
        
        # wait_for can accept a selector or a timeout
        try:
            # We give it plenty of time for Cloudflare to resolve
            await asyncio.sleep(15) 
            
            # Check for challenge page manually just in case
            content = await page.get_content()
            if "Verify you are human" in content or "PÍP PÍP TUTÚT" in content:
                logger.warning("Cloudflare challenge visible. Waiting another 20s...")
                await asyncio.sleep(20)
                await page.save_screenshot("error.png")

            # Try to find products
            items = await page.select_all(".browsingitem")
            
            if not items:
                logger.warning("No products found yet. Trying one last wait...")
                await asyncio.sleep(10)
                items = await page.select_all(".browsingitem")

            if not items:
                logger.error("Failed to find products. Possible block.")
                await page.save_screenshot("error.png")
                return

            logger.info(f"Found {len(items)} products.")

            new_products = []
            for item in items:
                # In nodriver, item is an Element object
                # We can use query_selector equivalents
                title_elem = await item.select("a.browsingitem-title")
                price_elem = await item.select(".price-box__price")
                
                if title_elem:
                    title = title_elem.text.strip()
                    href = title_elem.attributes.get("href")
                    url = "https://www.alza.sk" + href if href.startswith("/") else href
                    price = price_elem.text.strip() if price_elem else "N/A"
                    
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
                logger.info("No new available products found.")

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            await page.save_screenshot("error.png")
            
    finally:
        await browser.stop()

async def main():
    logger.info("Starting Alza Pokémon Bot (Nodriver Run)...")
    seen_products = load_seen_products()
    try:
        await check_alza(seen_products)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    logger.info("Run complete.")

if __name__ == "__main__":
    uc.loop().run_until_complete(main())
