import time
import random
from bs4 import BeautifulSoup
from curl_cffi import requests

def fetch_google_hardened(query):
    # 1. Use an updated User-Agent and strictly match client hints
    headers = {
        "Host": "www.google.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    }

    # Initialize session
    session = requests.Session()
    
    # 2. STEP 1: Visit the main homepage first to look like a user opening a tab
    print("Visiting Google Home to collect valid cookies...")
    home_response = session.get(
        "https://www.google.com/", 
        headers=headers, 
        impersonate="chrome124"
    )
    
    # Pause for 1.5 to 3 seconds to mimic human typing speed
    delay = random.uniform(1.5, 3.0)
    print(f"Simulating human typing delay... waiting {delay:.2f} seconds.")
    time.time()
    time.sleep(delay)

    # 3. STEP 2: Execute the search query
    formatted_query = query.replace(' ', '+')
    search_url = f"https://www.google.com/search?q={formatted_query}"
    
    # Update navigation state (now we are coming from the home page)
    headers["Sec-Fetch-Site"] = "same-origin"
    headers["Referer"] = "https://www.google.com/"

    print(f"Sending search request for: '{query}'...")
    response = session.get(
        search_url, 
        headers=headers, 
        impersonate="chrome124"
    )
    
    # 4. Verify if we got the real page or the bot page
    raw_html = response.text
    if "yvlrue" in raw_html or "captcha" in raw_html.lower():
        print("❌ Result: Still blocked. Google triggered a bot challenge page.")
        return False
        
    print("✅ Success! Obtained authentic Google Search HTML layout.")
    
    # Save the real layout
    with open("real_google_results.html", "w", encoding="utf-8") as f:
        f.write(raw_html)
        
    # Attempt extraction
    soup = BeautifulSoup(raw_html, "html.parser")
    search_rows = soup.find_all("div", class_="g")
    print(f"Extracted rows: {len(search_rows)}")
    return True

# Run the hardened request
fetch_google_hardened("python programming language")


