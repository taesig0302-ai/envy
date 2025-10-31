# crawler_core.py
import requests
from bs4 import BeautifulSoup

def crawl_product(url: str) -> dict:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("meta[property='og:title']")["content"]
        image = soup.select_one("meta[property='og:image']")["content"]
        price = None
        for tag in soup.select("span, em"):
            text = tag.get_text(strip=True)
            if text and text.replace(",", "").isdigit():
                price = text
                break
        return {"title": title, "image": image, "price": price}
    except Exception as e:
        return {}
