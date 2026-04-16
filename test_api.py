import requests
import json

def test_alza_api():
    # Trying the v2 endpoint found in research
    url = "https://www.alza.sk/Services/RestService.svc/v2/getProducts"
    
    # Payload matching the 2024/2025 structure
    payload = {
        "id": 18879069, # Pokémon category
        "page": 1,
        "count": 24,
        "sort": 0,
        "filter": ["3460"], # Producer: Pokémon
        "params": {
            "isListing": True,
            "isSearch": False,
            "availability": 1 # Often used in params
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.alza.sk",
        "Referer": "https://www.alza.sk/hracky/pokemon-karty/18879069.htm"
    }

    print(f"Testing Alza API: {url}")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                # Check for various common return structures
                products = data.get('d', {}).get('Products', []) or data.get('products', [])
                print(f"Successfully found {len(products)} products via API.")
                if products:
                    print("First product sample:")
                    p = products[0]
                    print(f" - Name: {p.get('name') or p.get('Name')}")
                    print(f" - Price: {p.get('price') or p.get('Price')}")
                else:
                    print("No products found in the response. Raw response snippet:")
                    print(json.dumps(data)[:500])
            except Exception as e:
                print(f"Failed to parse JSON: {e}")
                print("Raw response:", response.text[:500])
        else:
            print("Response text:", response.text[:500])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_alza_api()
