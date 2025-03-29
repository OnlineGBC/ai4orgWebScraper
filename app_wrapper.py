import streamlit as st
import io
import random
import re
import string
import web_scraper
import os
from urllib.parse import urljoin, urlparse
import pandas as pd
import openai
from datetime import datetime

MAX_TOKEN_LIMIT = 15000

def sanitize_for_xml(text):
    return re.sub(
        r'[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF\uE000-\uFFFD]', '', text
    )

def format_recursive_data_for_word(data, indent=0):
    # We reuse this function name, but it's just for formatting text now.
    text = ""
    prefix = "    " * indent
    if isinstance(data, dict):
        text += f"{prefix}URL: {data.get('URL', '')}\n"
        text += f"{prefix}Title: {data.get('Title', '')}\n"
        text += f"{prefix}Headings: {data.get('Headings', {})}\n"
        text += f"{prefix}Content:\n{prefix}{data.get('FullContent', '')}\n"
        if data.get('sub_pages'):
            text += f"{prefix}Sub-pages:\n"
            for sub in data['sub_pages']:
                text += format_recursive_data_for_word(sub, indent+1)
    return text

def collect_urls(data):
    """
    Recursively collect all URLs from the nested data structure.
    Each node is a dictionary with a "URL" key and optionally a "sub_pages" list.
    """
    urls = []
    if isinstance(data, dict):
        url = data.get("URL", "")
        if url:
            urls.append(url)
        if "sub_pages" in data:
            for sub in data["sub_pages"]:
                urls.extend(collect_urls(sub))
    return urls

def sanitize_recursive_data(data):
    if isinstance(data, dict):
        return {
            key: sanitize_for_xml(str(value)) if isinstance(value, str) else sanitize_recursive_data(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [sanitize_recursive_data(item) for item in data]
    else:
        return data

def save_to_text(text_content, domain_url):
    """
    Save text content to a .txt file based on a synthetic domain URL.
    """
    directory = "temp_uploaded_files"
    if not os.path.exists(directory):
        os.makedirs(directory)
    sanitized_text = sanitize_for_xml(text_content)
    base_name = urlparse(domain_url).hostname.replace(".", "_")
    random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    filename = f"{base_name}_{random_suffix}.txt"
    save_path = os.path.join(directory, filename)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(sanitized_text)
    return save_path

@st.cache_data(show_spinner="Performing recursive extraction (depth = 3)...", ttl=3600, hash_funcs={tuple: lambda x: hash(x)})
def cached_recursive_extract_all(urls_tuple, max_depth=3):
    """
    Uses web_scraper.recursive_extract_all to recursively gather data
    for each URL in the list, up to the specified depth.
    """
    urls_list = list(urls_tuple)
    return web_scraper.recursive_extract_all(urls_list, max_depth=max_depth)

def run_app():
    st.title("Web Scraping for Senior Leadership information")
    st.write("Enter URLs manually or upload a plain text file with URLs (one URL per line).")

    user_prompt = st.text_area(
        "Optionally describe specific info you want (e.g. names, titles, board members):",
        value="Act like an experienced marketer and data miner.  Please provide contact information for senior leadership, including the CEO and the Board of Directors, along with their names, titles, and contact details.",
        height=80,
    )

    uploaded_file = st.file_uploader("Upload a plain text file with URLs", type=["txt"])
    urls = []

    if uploaded_file is not None:
        file_content = io.StringIO(uploaded_file.read().decode("utf-8"))
        urls = [line.strip() for line in file_content if line.strip()]
    else:
        manual_input = st.text_area("Enter one URL per line:", "")
        urls = [line.strip() for line in manual_input.splitlines() if line.strip()]

    # Normalize URLs to ensure they have a scheme (http/https).
    normalized_urls = [url if urlparse(url).scheme else f"https://{url}" for url in urls]

    if normalized_urls:
        # Use AI analysis to figure out a prioritized list.
        prioritized_list, _ = web_scraper.ai_assisted_robots_analysis(normalized_urls, user_prompt)

        # Check if we already have the data in st.session_state.
        if "recursive_data" not in st.session_state:
            with st.spinner("Performing recursive extraction (depth = 3)..."):
                st.session_state.recursive_data = cached_recursive_extract_all(tuple(prioritized_list))

        recursive_data = st.session_state.recursive_data

        # Group results by domain
        domain_results = {}
        for url in prioritized_list:
            if url in recursive_data:
                domain = urlparse(url).netloc
                domain_results.setdefault(domain, []).append(recursive_data[url])

        if domain_results:
            st.subheader("Download Text File Per Domain")
            for domain, results_list in domain_results.items():
                # Combine all node URLs for this domain, remove duplicates, and join them as a simple list
                all_urls = []
                for res in results_list:
                    all_urls.extend(collect_urls(res))
                unique_urls = list(dict.fromkeys(all_urls))
                text_content = "\n".join(unique_urls)

                # Assign the content to a variable named <domain>_url_log_<timestamp>
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                var_domain = domain.replace(".", "_")
                var_name = f"{var_domain}_url_log_{timestamp}"
                globals()[var_name] = text_content

                # Save to a text file and also store it in session_state for crawl extraction
                domain_url = f"https://{domain}"
                text_filepath = save_to_text(text_content, domain_url)
                st.session_state.consolidated_url_log = text_content

                st.markdown(f"**Files for {domain}**")
                with open(text_filepath, "rb") as f_txt:
                    st.download_button(
                        f"Download Text File for {domain}",
                        f_txt,
                        os.path.basename(text_filepath),
                        key=f"download_text_{domain}"
                    )
        else:
            st.info("No extraction data found for the provided URLs.")

        # --- Crawl Extraction Section ---
        # Process the consolidated text log using crawl_extractor and display download buttons
        if "consolidated_url_log" in st.session_state and st.session_state.consolidated_url_log:
            from crawl_extractor import crawl_extract_text_from_log
            crawl_results = crawl_extract_text_from_log(st.session_state.consolidated_url_log)
            st.subheader("Crawled Extraction per Domain")
            for domain, crawl_text in crawl_results.items():
                st.markdown(f"**Crawled Extraction for {domain}**")
                temp_filename = f"{domain.replace('.', '_')}_crawl_extract.txt"
                with open(temp_filename, "w", encoding="utf-8") as f:
                    f.write(crawl_text)
                with open(temp_filename, "rb") as f:
                    st.download_button(
                        f"Download Crawled Text for {domain}",
                        f,
                        file_name=temp_filename,
                        key=f"download_crawl_{domain}"
                    )
                os.remove(temp_filename)

if __name__ == "__main__":
    run_app()
