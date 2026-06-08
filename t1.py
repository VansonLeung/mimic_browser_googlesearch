from curl_cffi import requests

def curl_google(query):
    # 1. Define the search URL
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    # 2. Mimic Browser Headers & Origin
    # Google uses 'Sec-Ch-Ua' headers for modern browser verification
    headers = {
        "Authority": "www.google.com",
        "Method": "GET",
        "Path": f"/search?q={query.replace(' ', '+')}",
        "Scheme": "https",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none", # 'none' mimics a user typing into the URL bar directly
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    # 3. Handle Valid Cookies
    # Visiting the base domain first drops standard tracking/consent cookies (like 1P_JAR, NID)
    session = requests.Session()
    
    # Send a request to the main page to populate the cookie jar naturally
    session.get("https://www.google.com", headers={"User-Agent": headers["User-Agent"]}, impersonate="chrome124")

    # 4. Execute the Search with Valid TLS
    # 'impersonate="chrome124"' forces curl_cffi to mimic Chrome's exact JA3/JA4 TLS fingerprint and HTTP/2 settings.
    response = session.get(url, headers=headers, impersonate="chrome124")
    
    if response.status_code == 200:
        print("Successfully bypassed Google TLS/Browser checks!")
        return response.text
    else:
        print(f"Failed with status code: {response.status_code}")
        return None

# Test the function
html_content = curl_google("python web scraping")

print(html_content)


