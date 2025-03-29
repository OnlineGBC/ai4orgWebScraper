import streamlit as st
import io
import random
import re
import string
import web_scraper
import os
from urllib.parse import urljoin, urlparse
from docx import Document
import pandas as pd
import openai
from datetime import datetime

MAX_TOKEN_LIMIT = 15000

def sanitize_for_xml(text):
    return re.sub(
        r'[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF\uE000-\uFFFD]', '', text
    )

def generate_random_filename(url):
    base_name = urlparse(url).hostname.replace(".", "_")
    random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{base_name}_{random_suffix}"

def format_recursive_data_for_word(data, indent=0):
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

def flatten_recursive_data(data, depth=0, rows=None):
    if rows is None:
        rows = []
    if isinstance(data, dict):
        rows.append({
            "URL": data.get("URL", ""),
            "Title": data.get("Title", ""),
            "Headings": str(data.get("Headings", {})),
            "Content": data.get("FullContent", ""),
            "Depth": depth
        })
        if data.get("sub_pages"):
            for sub in data["sub_pages"]:
                flatten_recursive_data(sub, depth+1, rows)
    return rows

def save_to_word(results, url):
    directory = "temp_uploaded_files"
    if not os.path.exists(directory):
        os.makedirs(directory)
    document = Document()
    document.add_heading('Extraction Results', level=1)
    sanitized_url = sanitize_for_xml(url)
    document.add_paragraph(f"Source URL: {sanitized_url}")
    sanitized_results = sanitize_for_xml(results)
    if sanitized_results != results:
        print(f"⚠️ Invalid XML characters detected and removed for URL: {url}")
    document.add_paragraph(sanitized_results)
    filename = generate_random_filename(url) + ".docx"
    save_path = os.path.join(directory, filename)
    document.save(save_path)
    return save_path

def save_to_excel(rows, url):
    directory = "temp_uploaded_files"
    if not os.path.exists(directory):
        os.makedirs(directory)
    sanitized_rows = []
    for row in rows:
        sanitized_row = {key: sanitize_for_xml(str(value)) for key, value in row.items()}
        sanitized_rows.append(sanitized_row)
    df = pd.DataFrame(sanitized_rows)
    filename = generate_random_filename(url) + ".xlsx"
    save_path = os.path.join(directory, filename)
    df.to_excel(save_path, index=False)
    return save_path

def save_to_text(text, url):
    """Save text content to a .txt file."""
    directory = "temp_uploaded_files"
    if not os.path.exists(directory):
        os.makedirs(directory)
    sanitized_text = sanitize_for_xml(text)
    filename = generate_random_filename(url) + ".txt"
    save_path = os.path.join(directory, filename)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(sanitized_text)
    return save_path

def collect_urls(data):
    """
    Recursively collect all URLs from the nested data structure.
    Each node is a dictionary with a "URL" key and an optional "sub_pages" list.
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

@st.cache_data(show_spinner="Performing recursive extraction (depth = 3)...", ttl=3600, hash_funcs={tuple: lambda x: hash(x)})
def cached_recursive_extract_all(urls_tuple, max_depth=3):
    urls_list = list(urls_tuple)
    return web_scraper.recursive_extract_all(urls_list, max_depth=max_depth)

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

def run_app():
    st.title("General Web Scraper")
    st.write("Enter URLs manually or upload a plain text file with URLs (one URL per line).")

    user_prompt = st.text_area(
        "Optionally describe specific info you want (e.g. names, titles, board members):",
        value="Please gather contact information for senior leadership, including the CEO and the Board of Directors, along with their names, titles, and contact details.",
        height=80,
    )

    uploaded_file = st.file_uploader("Upload a plain text file with URLs", type=["txt"])
    urls = []

    if uploaded_file is not None:
        file_content = io.StringIO(uploaded_file.read().decode("utf-8"))
        urls = [line.strip() for line in file_content if line.strip()]
    else:
        manual_input = st.text_area("Enter one URL per line (press Enter after each URL):", "")
        urls = [line.strip() for line in manual_input.splitlines() if line.strip()]

    normalized_urls = [url if urlparse(url).scheme else f"https://{url}" for url in urls]

    if normalized_urls:
        # Use AI analysis and recursive extraction
        prioritized_list, _ = web_scraper.ai_assisted_robots_analysis(normalized_urls, user_prompt)
        if "recursive_data" not in st.session_state:
            with st.spinner("Performing recursive extraction (depth = 3)..."):
                st.session_state.recursive_data = cached_recursive_extract_all(tuple(prioritized_list))
        recursive_data = st.session_state.recursive_data
        
        # Group results by domain so that each domain's data is kept together
        domain_results = {}
        for url in prioritized_list:
            result = recursive_data.get(url)
            if result:
                domain = urlparse(url).netloc
                domain_results.setdefault(domain, []).append(result)
        
        if domain_results:
            st.subheader("Download Files Per Domain")
            for domain, results_list in domain_results.items():
                # Combine results for the same domain
                word_contents = "\n\n".join([format_recursive_data_for_word(res) for res in results_list])
                excel_rows = []
                for res in results_list:
                    excel_rows.extend(flatten_recursive_data(res))
                text_contents = word_contents  # Using the same content for text output
                
                # Use a synthetic URL for the domain to drive the naming algorithm
                domain_url = "https://" + domain
                word_filepath = save_to_word(word_contents, domain_url)
                excel_filepath = save_to_excel(excel_rows, domain_url)
                text_filepath = save_to_text(text_contents, domain_url)
                
                st.markdown(f"**Files for {domain}**")
                with open(word_filepath, "rb") as f_word:
                    st.download_button(
                        f"Download Word File for {domain}",
                        f_word,
                        os.path.basename(word_filepath),
                        key=f"download_word_{domain}"
                    )
                with open(excel_filepath, "rb") as f_excel:
                    st.download_button(
                        f"Download Excel File for {domain}",
                        f_excel,
                        os.path.basename(excel_filepath),
                        key=f"download_excel_{domain}"
                    )
                with open(text_filepath, "rb") as f_text:
                    st.download_button(
                        f"Download Text File for {domain}",
                        f_text,
                        os.path.basename(text_filepath),
                        key=f"download_text_{domain}"
                    )
        else:
            st.info("No extraction data found for the provided URLs.")

if __name__ == "__main__":
    run_app()
