# pdf_extractor.py

import io
import os
import logging
import httpx
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract
import camelot
from pdf2docx import Converter
import streamlit as st
import tempfile

logging.basicConfig(level=logging.INFO)

# Define a no-op callback function
def noop():
    pass

def is_text_valid(text, threshold=0.1):
    """
    Check if the extracted text is likely valid by calculating the ratio 
    of alphanumeric characters (ignoring whitespace) to the total length.
    A threshold of 0.1 is used so that even if text contains lots of spaces 
    or punctuation, we accept it as long as there's a minimal proportion of 
    alphanumeric content.
    """
    if not text:
        return False
    text = text.strip()
    if not text:
        return False
    total = len(text)
    alpha_count = sum(1 for c in text if c.isalnum())
    ratio = alpha_count / total
    logging.info(f"Text validity ratio: {ratio:.2f} (threshold {threshold})")
    return ratio > threshold

def extract_native_text_from_pdf_bytes(pdf_bytes):
    """Attempt to extract native text from a PDF using pdfplumber."""
    try:
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        text = text.strip()
        if text and len(text) > 50 and is_text_valid(text):
            return text
        else:
            return ""
    except Exception as e:
        logging.error(f"Native extraction error: {e}")
        return ""

def extract_ocr_text_from_pdf_bytes(pdf_bytes, lang='eng'):
    """Perform OCR on PDF pages using pdf2image and pytesseract."""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
        ocr_text = ""
        for image in images:
            text = pytesseract.image_to_string(image, lang=lang)
            ocr_text += text + "\n"
        return ocr_text.strip()
    except Exception as e:
        logging.error(f"OCR extraction error: {e}")
        return ""

def extract_text_from_pdf_url(url, languages=['eng', 'jpn', 'chi_sim', 'kor']):
    """
    Download a PDF from the given URL and extract its text.
    First, try native extraction; if that fails (or yields invalid text), 
    fall back to OCR.
    """
    lang_str = "+".join(languages)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        with httpx.Client(timeout=30, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            pdf_bytes = response.content
    except Exception as e:
        logging.error(f"Error downloading PDF: {e}")
        return f"Error downloading PDF: {e}"
    
    native_text = extract_native_text_from_pdf_bytes(pdf_bytes)
    if native_text and len(native_text) > 50 and is_text_valid(native_text):
        logging.info("Native text extraction successful and valid.")
        return native_text
    else:
        logging.info("Native text extraction insufficient or invalid; proceeding with OCR.")
    
    ocr_text = extract_ocr_text_from_pdf_bytes(pdf_bytes, lang=lang_str)
    return ocr_text

def convert_pdf_to_docx(pdf_path, docx_path):
    """Convert a PDF file to a DOCX file using pdf2docx."""
    try:
        cv = Converter(pdf_path)
        cv.convert(docx_path, start=0, end=None)
        cv.close()
        return True, f"Converted to DOCX: {docx_path}"
    except Exception as e:
        logging.error(f"Error converting PDF to DOCX: {e}")
        return False, str(e)

def convert_pdf_to_excel(pdf_path, excel_path):
    """Extract tables from a PDF and save as CSV (which Excel can open) using Camelot."""
    try:
        tables = camelot.read_pdf(pdf_path, pages='all')
        if tables:
            csv_outputs = []
            for i, table in enumerate(tables):
                csv_output = table.df.to_csv(index=False)
                csv_outputs.append(csv_output)
            with open(excel_path, "w", encoding="utf-8") as f:
                f.write("\n".join(csv_outputs))
            return True, f"Extracted tables to CSV: {excel_path}"
        else:
            return False, "No tables found"
    except Exception as e:
        logging.error(f"Error converting PDF to Excel: {e}")
        return False, str(e)

def run_app():
    """Run the Streamlit UI for PDF Extraction and Processing."""
    st.title("PDF Extraction and Processing")
    st.markdown("Enter a PDF URL or upload a PDF file from your local system. Then choose an output format.")
    
    # Conversion options
    conversion_type = st.radio("Choose Conversion Option:", options=["Convert to Excel (tables)", "Convert to Word", "Convert to Text"])
    
    # Create two tabs: one for URL input and one for local file upload.
    tab1, tab2 = st.tabs(["Extract from URL", "Upload PDF"])
    
    # Tab 1: Extract from URL
    with tab1:
        pdf_url = st.text_input("Enter PDF URL:")
        if st.button("Process URL"):
            if pdf_url:
                with st.spinner("Extracting text from URL..."):
                    extracted_text = extract_text_from_pdf_url(pdf_url)
                if conversion_type == "Convert to Text":
                    st.text_area("Extracted Text", extracted_text, height=300)
                else:
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        with httpx.Client(timeout=30, headers=headers) as client:
                            response = client.get(pdf_url)
                            response.raise_for_status()
                            pdf_bytes = response.content
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(pdf_bytes)
                            tmp_path = tmp.name
                        if conversion_type == "Convert to Excel (tables)":
                            success, msg = convert_pdf_to_excel(tmp_path, tmp_path + ".csv")
                            if success:
                                with open(tmp_path + ".csv", "rb") as f:
                                    st.download_button("Download Excel (CSV)", f, file_name="converted_tables.csv", on_click=noop)
                            else:
                                st.error(msg)
                        elif conversion_type == "Convert to Word":
                            success, msg = convert_pdf_to_docx(tmp_path, tmp_path + ".docx")
                            if success:
                                with open(tmp_path + ".docx", "rb") as f:
                                    st.download_button("Download Word Document", f, file_name="converted_document.docx", on_click=noop)
                            else:
                                st.error(msg)
                    except Exception as e:
                        st.error(f"Error processing URL: {e}")
            else:
                st.error("Please enter a valid PDF URL.")
    
    # Tab 2: Upload PDF
    with tab2:
        uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
        if uploaded_file is not None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                if conversion_type == "Convert to Text":
                    with st.spinner("Extracting text from uploaded file..."):
                        with open(tmp_path, "rb") as f:
                            pdf_bytes = f.read()
                        native_text = extract_native_text_from_pdf_bytes(pdf_bytes)
                        if native_text and len(native_text) > 50 and is_text_valid(native_text):
                            extracted_text = native_text
                        else:
                            lang_str = "+".join(['eng', 'jpn', 'chi_sim', 'kor'])
                            extracted_text = extract_ocr_text_from_pdf_bytes(pdf_bytes, lang=lang_str)
                    st.text_area("Extracted Text", extracted_text, height=300)
                elif conversion_type == "Convert to Excel (tables)":
                    success, msg = convert_pdf_to_excel(tmp_path, tmp_path + ".csv")
                    if success:
                        with open(tmp_path + ".csv", "rb") as f:
                            st.download_button("Download Excel (CSV)", f, file_name="converted_tables.csv", on_click=noop)
                    else:
                        st.error(msg)
                elif conversion_type == "Convert to Word":
                    success, msg = convert_pdf_to_docx(tmp_path, tmp_path + ".docx")
                    if success:
                        with open(tmp_path + ".docx", "rb") as f:
                            st.download_button("Download Word Document", f, file_name="converted_document.docx", on_click=noop)
                    else:
                        st.error(msg)
            except Exception as e:
                st.error(f"Error processing uploaded file: {e}")

if __name__ == "__main__":
    run_app()
