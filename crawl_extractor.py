import io
import re
import time
import random
import string
import os
from datetime import datetime
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract

# Optional Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# For multi-threading and port management
import concurrent.futures
import queue

# Define the FIFO port pool for remote debugging ports
PORT_RANGE_START = 9222
PORT_RANGE_END = 10222
port_queue = queue.Queue()
for p in range(PORT_RANGE_START, PORT_RANGE_END + 1):
    port_queue.put(p)


def extract_text_from_url(url: str) -> str:
    """
    Given a URL, extract its text content using httpx/BeautifulSoup,
    fallback to Selenium if necessary, and run OCR on images.
    Embedded resources (images) hosted on external domains are skipped.
    """
    extracted_text = ""
    soup = None
    original_domain = urlparse(url).netloc

    # Attempt extraction using httpx + BeautifulSoup
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else ""
                paragraphs = soup.find_all("p")
                page_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
                extracted_text = title + "\n" + page_text
    except Exception as e:
        extracted_text = f"Error fetching {url}: {str(e)}"

    # Fallback to Selenium if extraction is too short
    if len(extracted_text) < 100:
        try:
            from selenium.webdriver.chrome.options import Options
            import tempfile

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            # Allocate a remote debugging port from the FIFO pool
            remote_port = port_queue.get()
            options.add_argument(f"--remote-debugging-port={remote_port}")

            # Create a unique temporary user data directory (leave as is)
            user_data_dir = tempfile.mkdtemp()
            options.add_argument(f"--user-data-dir={user_data_dir}")

            # print("DEBUG: Using temporary user data directory:", user_data_dir)
            try:
                contents = os.listdir(user_data_dir)
            except Exception as list_err:
                contents = f"Error listing directory: {str(list_err)}"
            # print("DEBUG: Contents of temporary user data directory:", contents)
            # print("DEBUG: Using remote debugging port:", remote_port)

            driver = webdriver.Chrome(options=options)
            driver.get(url)
            time.sleep(5)  # Allow page to load
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            paragraphs = soup.find_all("p")
            selenium_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
            extracted_text = title + "\n" + selenium_text
            driver.quit()
            # Return the port back to the pool
            port_queue.put(remote_port)
        except Exception as e:
            extracted_text += f"\nSelenium fallback error: {str(e)}"

    # PDF extraction (if URL ends with .pdf) using dedicated module
    if url.lower().endswith(".pdf"):
        try:
            from pdf_extractor import extract_text_from_pdf_url
            pdf_text = extract_text_from_pdf_url(url, languages=['eng', 'jpn', 'chi_sim', 'kor'])
            extracted_text += "\nPDF Extracted Text:\n" + pdf_text
        except Exception as e:
            extracted_text += f"\nPDF extraction error: {str(e)}"
        return extracted_text

    # OCR extraction on images (skip external images)
    try:
        if not soup:
            headers = {"User-Agent": "Mozilla/5.0"}
            with httpx.Client(timeout=15) as client:
                response = client.get(url, headers=headers)
                soup = BeautifulSoup(response.text, "html.parser")
        images = soup.find_all("img")
        ocr_text = ""
        for img in images:
            src = img.get("src")
            if src:
                img_url = urljoin(url, src)
                # Skip if the image is hosted on an external domain
                if urlparse(img_url).netloc != original_domain:
                    continue
                try:
                    img_resp = httpx.get(img_url, timeout=10)
                    if img_resp.status_code == 200:
                        image = Image.open(io.BytesIO(img_resp.content))
                        text_from_img = pytesseract.image_to_string(image)
                        ocr_text += "\n" + text_from_img
                except Exception as e:
                    ocr_text += f"\nOCR error on {img_url}: {str(e)}"
        if ocr_text:
            extracted_text += "\nOCR Extracted Text:\n" + ocr_text
    except Exception as e:
        extracted_text += f"\nOCR extraction error: {str(e)}"
    return extracted_text


def process_url(url):
    """
    Given a URL, attempt to extract text content.
    Returns a tuple: (domain, extracted_text, error_message)
    """
    # Normalize URL (assume HTTPS if scheme missing)
    if not urlparse(url).scheme:
        url = "https://" + url
    try:
        domain = urlparse(url).netloc
        page_text = extract_text_from_url(url)
        entry = f"URL: {url}\n{page_text}\n"
        return domain, entry, None
    except Exception as e:
        domain = urlparse(url).netloc
        error_msg = f"Error processing {url}: {str(e)}"
        return domain, "", error_msg


def crawl_extract_text_from_log(input_text: str) -> tuple:
    """
    Accepts an input text variable containing one URL per line,
    crawls each URL using traditional methods (multi-threaded),
    aggregates the extracted text, and for each domain, assigns the aggregated text to a global variable.
    Returns a tuple: (domain_successes, domain_errors)
      - domain_successes is a dict mapping domain to aggregated successful extraction text.
      - domain_errors is a dict mapping domain to aggregated error messages.
    """
    # Parse input text to get the list of URLs
    url_list = [line.strip() for line in input_text.splitlines() if line.strip()]
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_url, url): url for url in url_list}
        for future in concurrent.futures.as_completed(futures):
            domain, entry, error = future.result()
            results.append((domain, entry, error))

    domain_successes = {}
    domain_errors = {}
    for domain, entry, error in results:
        if error:
            if domain in domain_errors:
                domain_errors[domain] += "\n" + error
            else:
                domain_errors[domain] = error
        else:
            if domain in domain_successes:
                domain_successes[domain] += "\n" + entry
            else:
                domain_successes[domain] = entry

    # For each domain in successes, assign the aggregated text to a dynamically named global variable.
    for domain, content in domain_successes.items():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        var_name = f"{domain.replace('.', '_')}_crawl_extract_{timestamp}"
        globals()[var_name] = content

    return domain_successes, domain_errors


def crawl_extract_text_from_log_wrapper(input_text: str) -> dict:
    """
    A wrapper function to call crawl_extract_text_from_log and return only the successes.
    This can be used by UI code that only needs successful extraction.
    """
    successes, errors = crawl_extract_text_from_log(input_text)
    # Optionally, errors can be logged or handled separately.
    return successes

# Example usage for testing (remove or comment out when integrating into the UI)
if __name__ == "__main__":
    sample_input = """https://imgflip.com/about
https://imgflip.com/
https://imgflip.com/memegenerator
"""
    successes, errors = crawl_extract_text_from_log(sample_input)
    for domain, text in successes.items():
        print(f"--- Extracted content for {domain} (first 500 characters) ---")
        print(text[:500])
    for domain, err in errors.items():
        print(f"--- Errors for {domain} ---")
        print(err)
