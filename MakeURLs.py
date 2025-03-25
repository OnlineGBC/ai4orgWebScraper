import requests
import urllib.parse

def get_random_wikipedia_urls(n=200):
    urls = []
    count = 0
    while count < n:
        params = {
            "action": "query",
            "list": "random",
            "rnnamespace": 0,  # Main article namespace
            "rnlimit": 10,     # 10 per request (limit for non-bot requests)
            "format": "json"
        }
        response = requests.get("https://en.wikipedia.org/w/api.php", params=params)
        response.raise_for_status()
        data = response.json()
        for page in data["query"]["random"]:
            title = page["title"]
            url_title = urllib.parse.quote(title.replace(" ", "_"))
            url = f"https://en.wikipedia.org/wiki/{url_title}"
            urls.append(url)
            count += 1
            if count >= n:
                break
    return urls

if __name__ == "__main__":
    random_urls = get_random_wikipedia_urls(200)
    for url in random_urls:
        print(url)
