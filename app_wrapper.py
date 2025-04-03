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
        r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]', '', text
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

    user_prompt = (
        "Act like an experienced marketer and data miner and look for information on senior leadership, "
        "like the Founder or Co-Founder, CEO, CFO, other C-level officers, or the Board of Directors, along with their names, titles, and social media or other contact details.  "
        "If senior leadership is not found, get the top 10 team members by title.  Only get information from your RAG and internal data.  Do not search the Internet or any public sources."
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
    else:
        prioritized_list = []  # Ensure prioritized_list is defined even if normalized_urls is empty

    if normalized_urls:
        if "recursive_data" not in st.session_state:
            with st.spinner("Performing recursive extraction (depth = 3)..."):
                st.session_state.recursive_data = cached_recursive_extract_all(tuple(prioritized_list))

            recursive_data = st.session_state.recursive_data

            # Group results by domain.
            domain_results = {}
            for url in prioritized_list:
                if url in recursive_data:
                    domain = urlparse(url).netloc
                    domain_results.setdefault(domain, []).append(recursive_data[url])

            # The option to download extract text files has been removed,
            # since the files are automatically saved to temp_uploaded_files.
            if not domain_results:
                st.info("No extraction data found for the provided URLs.")

            # --- Multi-threaded Crawl Extraction Section with Appending ---
            # Process each domain's URL log concurrently, and append all extracted content to a unique file.
            from crawl_extractor import crawl_extract_text_from_log
            import concurrent.futures
            import base64

            if domain_results:
                st.subheader("Crawling and Extracting Your Data . . . please wait . . . ")
                # Use session_state to store generated file names per domain.
                if "extracted_files" not in st.session_state:
                    st.session_state.extracted_files = {}

                def process_domain(domain, results_list):
                    # Rebuild the domain's consolidated URL log.
                    all_urls = []
                    for res in results_list:
                        all_urls.extend(collect_urls(res))
                    unique_urls = list(dict.fromkeys(all_urls))
                    text_content = "\n".join(unique_urls)
                    # Call the multi-threaded crawl extraction for this domain's log.
                    successes, errors = crawl_extract_text_from_log(text_content)
                    # Retrieve the result for this domain (success and error texts separately).
                    return domain, successes.get(domain, ""), errors.get(domain, "")

                futures = {}
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    for domain, results_list in domain_results.items():
                        futures[executor.submit(process_domain, domain, results_list)] = domain

                for future in concurrent.futures.as_completed(futures):
                    domain, crawl_text, error_text = future.result()
                    st.markdown(f"**Crawled Extraction for {domain}**")
                    # Determine the unique file name for this domain.
                    domain_key = domain.replace('.', '_')
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    file_name = f"{domain_key}_Extract_data-{timestamp}.txt"
                    if domain not in st.session_state.extracted_files:
                        file_path = os.path.join("temp_uploaded_files", file_name)
                        st.session_state.extracted_files[domain] = file_path
                    else:
                        file_path = st.session_state.extracted_files[domain]
                    # Append the successful crawl_text to the file.
                    with open(file_path, "a", encoding="utf-8") as f:
                        f.write(crawl_text + "\n")
                    # If there are errors, write them to a separate error file.
                    if error_text:
                        error_file_name = file_name.replace("Extract_data", "Extract_data_err")
                        error_file_path = os.path.join("temp_uploaded_files", error_file_name)
                        with open(error_file_path, "a", encoding="utf-8") as f:
                            f.write(error_text + "\n")

                    # Read the main file content and encode as Base64 for download.
                    with open(file_path, "rb") as f:
                        data = f.read()
                    b64 = base64.b64encode(data).decode()
                    download_url = f"data:text/plain;base64,{b64}"
                    st.markdown(f"File for {domain}: **{os.path.basename(file_path)}**")
        else:
            st.info("Extraction data already processed.")
    else:
        st.info("Please provide at least one URL.")

    # After processing, if extracted_files exists, load the first file's content into session_state for chat.
    if "extracted_files" in st.session_state and st.session_state.extracted_files:
        all_crawled_text = ""
        for file_path in st.session_state.extracted_files.values():
            with open(file_path, "r", encoding="utf-8") as f:
                all_crawled_text += f.read() + "\n"
        st.session_state.crawled_text = all_crawled_text.strip()

    # Automatically launch the chat interface if crawled_text exists and is non-empty.
    if "crawled_text" in st.session_state and st.session_state.crawled_text.strip():
        import chat_wrapper
        chat_wrapper.run_chat()
    else:
        st.write("Chat interface is not available until extraction is successful.")

if __name__ == "__main__":
    run_app()
