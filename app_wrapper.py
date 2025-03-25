import streamlit as st
import io
import os
import random
import re
import string
import web_scraper
from dotenv import load_dotenv

load_dotenv()


def normalize_url(url):
    """Ensure the URL begins with 'https://'. Replace 'http://' with 'https://' or add the prefix if missing."""
    url = url.strip()
    if not url:
        return None
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    elif not url.startswith("https://"):
        url = "https://" + url
    return url


def generate_random_filename(url):
    """
    Generate a base filename of exactly 15 alphanumeric characters.
    Take the first 8 alphanumeric characters from the URL (after 'https://')
    and append random alphanumeric characters to reach 15 characters.
    """
    if url.startswith("https://"):
        trimmed = url[len("https://") :]
    else:
        trimmed = url
    alphanum = re.sub(r"[^A-Za-z0-9]", "", trimmed)
    base = alphanum[:8]
    remaining = 15 - len(base)
    rand_chars = "".join(
        random.choices(string.ascii_letters + string.digits, k=remaining)
    )
    return base + rand_chars


def convert_to_clear_english(text):
    """
    Convert the given text into clear, grammatical English using the OpenAI API (v1.x).
    The OpenAI API key is expected to be stored in the environment variable 'OPENAI_API_KEY'.
    """
    import openai
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error(
            "OpenAI API key not found. Please set OPENAI_API_KEY in your environment."
        )
        return text

    client = OpenAI(api_key=api_key)

    prompt = f"Please rewrite the following text in clear, concise, and grammatically correct English:\n\n{text}\n\nRewritten version:"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that rewrites text in clear, grammatical English.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=10240,
        )
        rewritten_text = response.choices[0].message.content.strip()
        return rewritten_text
    except Exception as e:
        st.error(f"OpenAI error: {str(e)}")
        return text


def save_to_txt_and_summary(result, url):
    """
    Save two files:
    1. Main .txt file with extracted content
    2. Summary .txt file with improved clarity (converted by OpenAI)
    """
    directory = "temp_uploaded_files"
    if not os.path.exists(directory):
        os.makedirs(directory)

    base_filename = generate_random_filename(url)
    main_filepath = os.path.join(directory, base_filename + ".txt")
    summary_filepath = os.path.join(directory, "Sum_" + base_filename + ".txt")

    import json

    content = json.dumps(result, indent=2)

    with open(main_filepath, "w", encoding="utf-8") as f:
        f.write(content)

    converted_content = convert_to_clear_english(content)

    with open(summary_filepath, "w", encoding="utf-8") as f:
        f.write(converted_content)

    return main_filepath, summary_filepath


def main():
    st.title("General Web Scraper")
    st.write(
        "Enter URLs manually or upload a plain text file with URLs (one URL per line)."
    )

    uploaded_file = st.file_uploader("Upload a plain text file with URLs", type=["txt"])
    urls = []

    if uploaded_file is not None:
        try:
            file_content = io.StringIO(uploaded_file.read().decode("utf-8"))
        except Exception:
            st.error("Error reading the file. Please ensure it is a valid text file.")
            st.stop()

        file_urls = [line.strip() for line in file_content if line.strip()]
        if len(file_urls) > 100:
            st.error(
                "Only 100 entries may be processed at a time. Please attach a file with 100 or fewer URLs or close."
            )
            st.stop()
        urls.extend(file_urls)
    else:
        manual_input = st.text_area(
            "Enter one URL per line (press Enter after each URL):", ""
        )
        if manual_input:
            manual_urls = [
                line.strip() for line in manual_input.splitlines() if line.strip()
            ]
            if len(manual_urls) > 9:
                st.error(
                    "For more than 9 entries, please attach a plain text file with the full list."
                )
                st.stop()
            urls.extend(manual_urls)

    if urls:
        normalized_urls = []
        for url in urls:
            norm_url = normalize_url(url)
            if norm_url:
                normalized_urls.append(norm_url)

        st.subheader("Normalized URLs:")
        # Choose number of columns (e.g. 3 or 4 depending on screen width)
        cols = st.columns(4)
        for idx, url in enumerate(normalized_urls):
            col = cols[idx % len(cols)]
            col.write(url)

        st.subheader("Processing URLs . . .  ")
        for url in normalized_urls:
            st.write(f"Processing {url}  . . .  ")
            result = web_scraper.extract_article_content(url)
            main_file, summary_file = save_to_txt_and_summary(result, url)
            st.success("Files saved successfully:")

            # Load contents
            with open(main_file, "r", encoding="utf-8") as f_main:
                main_text = f_main.read()
                main_preview = "\n".join(main_text.splitlines()[:10])

            with open(summary_file, "r", encoding="utf-8") as f_summary:
                summary_text = f_summary.read()
                summary_preview = "\n".join(summary_text.splitlines()[:10])

            # Arrange in a row using columns
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                with st.expander("📄 Preview main file"):
                    st.text(main_preview)

            with col2:
                st.download_button(
                    label="📥 Download main",
                    data=main_text,
                    file_name=os.path.basename(main_file),
                    mime="text/plain",
                )

            with col3:
                with st.expander("📝 Preview AI Content"):
                    st.text(summary_preview)

            with col4:
                st.download_button(
                    label="📥 Download AI Content",
                    data=summary_text,
                    file_name=os.path.basename(summary_file),
                    mime="text/plain",
                )


def run_app():
    main()


if __name__ == "__main__":
    run_app()
