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

def extract_text_from_url(url: str) -> str:
    """
    Given a URL, extract its text content using httpx/BeautifulSoup,
    fallback to Selenium if necessary, and run OCR on images.
    """
    extracted_text = ""
    soup = None

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
    # If extraction is too short, fallback to Selenium
    if len(extracted_text) < 100:
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--remote-debugging-port=9222")
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
        except Exception as e:
            extracted_text += f"\nSelenium fallback error: {str(e)}"

    # If the URL is a PDF, perform PDF OCR extraction using pdf2image
    if url.lower().endswith(".pdf"):
        try:
            from pdf2image import convert_from_bytes
            # Set headers to mimic a browser and request PDF content
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
                "Accept": "application/pdf"
            }
            with httpx.Client(timeout=15, headers=headers) as client:
                pdf_response = client.get(url)
                pdf_response.raise_for_status()
                images = convert_from_bytes(pdf_response.content)
                pdf_text = ""
                for image in images:
                    text = pytesseract.image_to_string(image, lang="eng")
                    pdf_text += "\n" + text
                extracted_text += "\nPDF OCR Extracted Text:\n" + pdf_text
        except Exception as e:
            extracted_text += f"\nPDF OCR extraction error: {str(e)}"
        return extracted_text

    # OCR extraction on images
    try:
        # Ensure soup is available
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

def crawl_extract_text_from_log(input_text: str) -> dict:
    """
    Accepts an input text variable containing one URL per line,
    crawls each URL using traditional methods, aggregates the extracted text,
    and for each domain, assigns the aggregated text to a global variable named:
      <<domain>>_crawl_extract_<<yyyymmdd-hhmmss>>
    Returns a dictionary mapping each domain to its aggregated extracted text.
    """
    # Parse input text to get the list of URLs
    url_list = [line.strip() for line in input_text.splitlines() if line.strip()]
    domain_aggregates = {}

    for url in url_list:
        # Normalize URL (assume HTTPS if scheme missing)
        if not urlparse(url).scheme:
            url = "https://" + url
        domain = urlparse(url).netloc
        page_text = extract_text_from_url(url)
        entry = f"URL: {url}\n{page_text}\n"
        if domain in domain_aggregates:
            domain_aggregates[domain] += "\n" + entry
        else:
            domain_aggregates[domain] = entry

    # For each domain, assign the aggregated text to a dynamically named global variable.
    for domain, content in domain_aggregates.items():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        var_name = f"{domain.replace('.', '_')}_crawl_extract_{timestamp}"
        globals()[var_name] = content

    return domain_aggregates

# Example usage for testing (remove or comment out when integrating into the UI)
if __name__ == "__main__":
    # Assume this is the content of the variable imgflip_com_url_log_20250330-121314
    sample_input = """https://imgflip.com/about
https://imgflip.com/
https://imgflip.com/memegenerator
"""
    results = crawl_extract_text_from_log(sample_input)
    for domain, text in results.items():
        print(f"--- Extracted content for {domain} (first 500 characters) ---")
        print(text[:500])
