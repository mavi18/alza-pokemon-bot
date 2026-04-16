import json
import logging
import os
import time
import requests
from dotenv import load_dotenv
from seleniumbase import SB

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

def check_alza(seen_products):
    logger.info("Starting SeleniumBase UC Mode...")
    
    # We use xvfb=True for GitHub Actions to run in a virtual headed mode
    with SB(uc=True, xvfb=True, headless=False) as sb:
        logger.info(f"Navigating to {ALZA_URL}...")
        
        try:
            # Open with reconnect to bypass initial JS challenge
            sb.uc_open_with_reconnect(ALZA_URL, reconnect_time=5)
            
            # Check for Cloudflare challenge and try to click it if visible
            sb.uc_gui_click_captcha()
            
            # Wait for products to load
            logger.info("Waiting for products...")
            time.sleep(10) # Initial wait for JS
            
            if not sb.is_element_visible(".browsingitem"):
                logger.warning("Products not visible. Trying one more reconnect...")
                sb.uc_open_with_reconnect(ALZA_URL, reconnect_time=10)
                sb.uc_gui_click_captcha()
                time.sleep(10)

            if not sb.is_element_visible(".browsingitem"):
                logger.error("Failed to find products. Taking screenshot...")
                sb.save_screenshot("error.png")
                return

            items = sb.find_elements(".browsingitem")
            logger.info(f"Found {len(items)} products.")

            new_products = []
            for item in items:
                try:
                    title_elem = item.find_element("css selector", "a.browsingitem-title")
                    price_elem = item.find_element("css selector", ".price-box__price")
                    
                    title = title_elem.text.strip()
                    href = title_elem.get_attribute("href")
                    url = href # Selenium returns full URL
                    price = price_elem.text.strip() if price_elem else "N/A"
                    
                    product_id = f"{title}_{price}"
                    if product_id not in seen_products:
                        new_products.append(f"📦 {title}\n💰 {price}\n🔗 {url}")
                        seen_products.add(product_id)
                except Exception as e:
                    continue

            if new_products:
                chunk_size = 5
                for i in range(0, len(new_products), chunk_size):
                    chunk = new_products[i:i + chunk_size]
                    message = "\n\n".join(chunk)
                    send_notification(message)
                
                save_seen_products(seen_products)
                logger.info(f"Notified about {len(new_products)} products.")
            else:
                logger.info("No new products found.")

        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            sb.save_screenshot("error.png")

def main():
    logger.info("Starting Alza Pokémon Bot (SeleniumBase Run)...")
    seen_products = load_seen_products()
    try:
        check_alza(seen_products)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    logger.info("Run complete.")

if __name__ == "__main__":
    main()
