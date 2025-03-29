import httpx
from bs4 import BeautifulSoup
import pandas as pd
import os
import time
import random
import web_scraper_js  # ✅ import JS fallback
from urllib.parse import urljoin, urlparse
from config import OPENAI_CLIENT as client
import pytesseract
from PIL import Image
from io import BytesIO
import re

###############################################################################
# Existing function for single-page extraction (kept for fallback if needed)
###############################################################################
def extract_article_content(url):
    """
    Extract full content from a URL.
    Try standard httpx + BS4 first, fallback to JS if 403.
    Rate limit: Random delay between 0.5 and 2 seconds.
    """
    if not hasattr(extract_article_content, "last_request_time"):
        extract_article_content.last_request_time = 0
    elapsed = time.time() - extract_article_content.last_request_time
    delay = random.uniform(0.5, 2.0)
    if elapsed < delay:
        time.sleep(delay - elapsed)
    extract_article_content.last_request_time = time.time()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
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
                if not full_content.strip():
                    full_content = soup.get_text(separator="\n", strip=True)
                
                image_text = extract_image_text(soup, client, url)
                if image_text:
                    full_content += "\n\n--- Text Extracted from Images ---\n" + image_text
                
                title_tag = soup.find("title")
                title = title_tag.get_text().strip() if title_tag else "No Title"
                headings = {}
                for level in ['h1', 'h2', 'h3']:
                    headings[level] = [tag.get_text().strip() for tag in soup.find_all(level)]
                return [{"URL": url, "Title": title, "FullContent": full_content, "Headings": headings}]
            elif response.status_code == 403:
                return web_scraper_js.extract_article_content_js(url)
            else:
                return [{"URL": url, "Error": f"Status code {response.status_code}"}]
    except Exception as e:
        return [{"URL": url, "Error": str(e)}]

def extract_image_text(soup, http_client, base_url):
    """Extract text from images using Tesseract OCR"""
    image_texts = []
    for img in soup.find_all('img', src=True):
        try:
            img_url = urljoin(base_url, img['src'])
            img_alt = img.get('alt', '')
            if 'icon' in img_url.lower() or 'logo' in img_url.lower():
                continue
            response = http_client.get(img_url)
            if response.status_code == 200:
                img_data = BytesIO(response.content)
                image = Image.open(img_data)
                if image.width < 100 or image.height < 100:
                    continue
                text = pytesseract.image_to_string(image)
                if text.strip():
                    if img_alt:
                        image_texts.append(f"Image ({img_alt}): {text.strip()}")
                    else:
                        image_texts.append(f"Image: {text.strip()}")
        except Exception as e:
            print(f"Error processing image {img.get('src')}: {e}")
            continue
    return "\n\n".join(image_texts)

def save_to_csv(result, filename):
    df = pd.DataFrame(result)
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", index=False, header=False)
    else:
        df.to_csv(filename, index=False)

###############################################################################
# NEW: Initial site crawling to discover actual structure
###############################################################################
def discover_site_structure(url, user_prompt):
    """
    Perform an initial crawl of the site to discover its actual structure
    before making AI suggestions.
    """
    print(f"Discovering site structure for {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    discovered_paths = set()
    leadership_related_paths = []
    try:
        time.sleep(random.uniform(0.5, 2.0))
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    path = urljoin(base_url, href)
                    if base_url in path:
                        path_only = urlparse(path).path
                        if path_only and path_only != '/':
                            discovered_paths.add(path_only)
                            link_text = link.get_text().lower()
                            path_lower = path_only.lower()
                            leadership_terms = ['about', 'team', 'leadership', 'management', 
                                                  'board', 'director', 'executive', 'contact', 
                                                  'people', 'who we are']
                            if any(term in path_lower or term in link_text for term in leadership_terms):
                                leadership_related_paths.append(path_only)
    except Exception as e:
        print(f"Error discovering site structure: {e}")
    return list(discovered_paths), leadership_related_paths

###############################################################################
# ENHANCED: AI-Assisted Path Analysis with actual site structure
###############################################################################
def ai_assisted_robots_analysis(url_list, user_prompt):
    """
    For each URL in the list:
      1) Discover actual site structure through initial crawling
      2) Use OpenAI to suggest which paths might have the requested info
      3) Return a deduplicated list of up to 20 priority URLs per site and analysis text
    """
    prioritized_urls = []
    ai_analysis_text = []
    for url in url_list:
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        all_paths, leadership_paths = discover_site_structure(url, user_prompt)
        analysis_prompt = (
            f"For the website {base_url}\n\n"
            f"I've discovered these paths on the site:\n{', '.join(all_paths[:50] if len(all_paths) > 50 else all_paths)}\n\n"
            f"These paths seem particularly relevant to leadership information:\n{', '.join(leadership_paths)}\n\n"
            f"Given the user's request:\n{user_prompt}\n\n"
            f"Provide a brief analysis of which paths are most likely to contain the requested information. "
            f"Format your response as a clear explanation without repeating the full URLs."
        )
        already_added_urls = set()
        site_nodes = []
        for path in leadership_paths[:10]:
            full_path = urljoin(base_url, path)
            if full_path not in already_added_urls:
                site_nodes.append(full_path)
                already_added_urls.add(full_path)
        try:
            # Use openai.chat.completions.create directly (do not use client.ChatCompletion.create)
            import openai
            analysis_response = openai.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant that analyzes website structure and suggests the most relevant paths for finding specific information."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            analysis = analysis_response.choices[0].message.content.strip()
            ai_analysis_text.append(analysis)
            url_prompt = (
                f"For the website {base_url}\n\n"
                f"I've discovered these paths on the site:\n{', '.join(all_paths[:50] if len(all_paths) > 50 else all_paths)}\n\n"
                f"These paths seem particularly relevant to leadership information:\n{', '.join(leadership_paths)}\n\n"
                f"Given the user's request:\n{user_prompt}\n\n"
                f"List ONLY the specific path components (e.g., '/about-us', '/contact') that are most likely to contain the requested information. "
                f"One path per line. No explanations or full URLs."
            )
            url_response = openai.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=[
                    {
                        "role": "system",
                        "content": "You provide only path components, one per line, with no explanations or full URLs."
                    },
                    {
                        "role": "user",
                        "content": url_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=200
            )
            suggested_paths = url_response.choices[0].message.content.strip().splitlines()
            for path in suggested_paths:
                path = path.strip()
                if not path or len(path.split()) > 3 or path.startswith('http'):
                    continue
                if ' - ' in path:
                    path = path.split(' - ')[0].strip()
                path = re.sub(r'^[\d\.\)\-\*]+\s*', '', path)
                if not path.startswith('/'):
                    path = '/' + path
                full_path = urljoin(base_url, path)
                if full_path not in already_added_urls and len(site_nodes) < 20:
                    site_nodes.append(full_path)
                    already_added_urls.add(full_path)
            prioritized_urls.extend(site_nodes)
        except Exception as e:
            print(f"AI analysis error for {url}: {e}")
            if url not in already_added_urls:
                prioritized_urls.append(url)
                already_added_urls.add(url)
            for path in leadership_paths[:5]:
                full_path = urljoin(base_url, path)
                if full_path not in already_added_urls:
                    prioritized_urls.append(full_path)
                    already_added_urls.add(full_path)
    return prioritized_urls, ai_analysis_text

###############################################################################
# NEW: Recursive Extraction of Node Contents (with depth = 3)
###############################################################################
def get_soup(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return BeautifulSoup(response.text, "html.parser")
            else:
                return None
    except Exception as e:
        print(f"Error fetching soup for {url}: {e}")
        return None

def recursive_extract(url, current_depth=0, max_depth=3, visited=None):
    if visited is None:
        visited = set()
    if url in visited:
        return None
    visited.add(url)
    
    extraction = extract_article_content(url)
    if extraction and isinstance(extraction, list):
        page_data = extraction[0]
    else:
        page_data = {"URL": url, "Title": "", "FullContent": "", "Headings": {}}
    
    if current_depth < max_depth:
        soup = get_soup(url)
        if soup:
            sub_pages = []
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                full_url = urljoin(url, href)
                if urlparse(full_url).netloc == urlparse(url).netloc:
                    if full_url not in visited:
                        sub_result = recursive_extract(full_url, current_depth + 1, max_depth, visited)
                        if sub_result:
                            sub_pages.append(sub_result)
            if sub_pages:
                page_data['sub_pages'] = sub_pages
    return page_data
