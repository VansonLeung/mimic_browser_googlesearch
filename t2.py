import os
from bs4 import BeautifulSoup
from curl_cffi import requests

def fetch_and_extract_google(query):
    # 1. Prepare search URL and mock identical browser context
    formatted_query = query.replace(' ', '+')
    url = f"https://www.google.com/search?q={formatted_query}"
    
    headers = {
        "Authority": "www.google.com",
        "Method": "GET",
        "Path": f"/search?q={formatted_query}",
        "Scheme": "https",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    session = requests.Session()
    # Establish valid cookies first
    session.get("https://www.google.com", headers={"User-Agent": headers["User-Agent"]}, impersonate="chrome124")
    
    # Execute the actual search request utilizing verified modern TLS emulation
    response = session.get(url, headers=headers, impersonate="chrome124")
    
    if response.status_code != 200:
        print(f"Error fetching page: Status code {response.status_code}")
        return

    raw_html = response.text

    # 2. Requirement 1: Generate the full output HTML file
    filename = "google_search_results.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(raw_html)
    print(f"Saved complete raw layout locally to: {os.path.abspath(filename)}")

    # 3. Requirement 2: Attempt to extract the target search rows
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Modern Google search organic cards use a 'div' element with the specific class "g"
    search_rows = soup.find_all("div", class_="g")
    
    print(f"\n--- Extracted Search Rows Context ({len(search_rows)} results found) ---")
    
    for index, row in enumerate(search_rows, start=1):
        print(f"\n[Result Row #{index}]")
        
        # Isolate the exact inner HTML content block where the search result row resides
        row_html_content = str(row)
        
        # Displaying a small snippet of the raw HTML block
        print("Raw Content Sample:")
        print(row_html_content[:300] + "... [truncated]")
        
        # Parse elements inside the extracted container block to confirm validity
        title_element = row.find("h3")
        link_element = row.find("a")
        
        if title_element and link_element:
            title = title_element.get_text()
            link = link_element.get("href")
            print(f"Verified Title: {title}")
            print(f"Verified URL:   {link}")

# Execute query sample
fetch_and_extract_google("python programming language")



