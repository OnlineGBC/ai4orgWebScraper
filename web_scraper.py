import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import web_scraper_js  # ✅ import JS fallback

def extract_article_content(url):
    """
    Extract full content from a URL.
    Try standard request + BS4 first, fallback to JS if 403.
    Rate limit: 3 requests per second.
    """
    # Rate limit
    if not hasattr(extract_article_content, "last_request_time"):
        extract_article_content.last_request_time = 0
    elapsed = time.time() - extract_article_content.last_request_time
    if elapsed < 1 / 3:
        time.sleep((1 / 3) - elapsed)
    extract_article_content.last_request_time = time.time()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            article = soup.find("article")
            if article:
                paragraphs = article.find_all("p")
            else:
                body = soup.find("body")
                paragraphs = body.find_all("p") if body else soup.find_all("p")

            full_content = "\n".join(
                p.get_text().strip() for p in paragraphs if p.get_text().strip()
            )
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else "No Title"
            return [{"URL": url, "Title": title, "FullContent": full_content}]

        elif response.status_code == 403:
            # Fallback to JavaScript-enabled scraping
            return web_scraper_js.extract_article_content_js(url)

        else:
            return [{"URL": url, "Error": f"Status code {response.status_code}"}]

    except Exception as e:
        return [{"URL": url, "Error": str(e)}]


def save_to_csv(result, filename):
    df = pd.DataFrame(result)
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", index=False, header=False)
    else:
        df.to_csv(filename, index=False)
