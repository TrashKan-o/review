from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re

USERNAME = "RymKan"
URL = f"https://rateyourmusic.com/~{USERNAME}"

# Use Chrome browser impersonation to bypass Cloudflare
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

try:
    # curl_cffi matches browser TLS fingerprints so Cloudflare lets it through
    response = requests.get(URL, headers=headers, impersonate="chrome120")
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Look for the ratings count in the page HTML
    match = re.search(r'([\d,]+)\s+ratings', response.text, re.IGNORECASE)
    
    if match:
        ratings_count = match.group(1)
    else:
        ratings_count = "N/A"
except Exception as e:
    print(f"Error fetching RYM: {e}")
    ratings_count = "N/A"

# Save the extracted count into stats.json
data = {"rym_ratings": ratings_count}
with open("stats.json", "w") as f:
    json.dump(data, f)

print(f"Successfully updated stats.json with {ratings_count} ratings!")
