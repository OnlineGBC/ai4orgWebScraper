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
import base64
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key from environment variable
# openai.api_key = os.getenv("OPENAI_API_KEY")          #  This is the old syntax 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))    # This is the new syntax

# logging.basicConfig(level=logging.INFO)

# Define a no-op callback function for download buttons
def noop():
    pass

def is_text_valid(text, threshold=0.1):
    """
    Check if the extracted text is likely valid by calculating the ratio 
    of alphanumeric characters (ignoring whitespace) to the total length.
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
    First, try native extraction; if that fails, fall back to OCR.
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
        logging.info("Native text extraction insufficient; proceeding with OCR.")
    
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

def convert_pdf_to_excel_csv(pdf_path, csv_path):
    """Extract tables from a PDF and save as CSV using Camelot."""
    try:
        tables = camelot.read_pdf(pdf_path, pages='all')
        if tables:
            csv_outputs = []
            for i, table in enumerate(tables):
                csv_output = table.df.to_csv(index=False)
                csv_outputs.append(csv_output)
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("\n".join(csv_outputs))
            return True, f"Extracted tables to CSV: {csv_path}"
        else:
            return False, "No tables found"
    except Exception as e:
        logging.error(f"Error converting PDF to CSV: {e}")
        return False, str(e)

def convert_pdf_to_excel_xlsx(pdf_path, xlsx_path):
    """Extract tables from a PDF and save as an Excel file (XLSX) using Camelot and pandas."""
    try:
        tables = camelot.read_pdf(pdf_path, pages='all')
        if tables:
            with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
                for i, table in enumerate(tables):
                    sheet_name = f"Table{i+1}"
                    table.df.to_excel(writer, sheet_name=sheet_name, index=False)
            return True, f"Extracted tables to Excel: {xlsx_path}"
        else:
            return False, "No tables found"
    except Exception as e:
        logging.error(f"Error converting PDF to XLSX: {e}")
        return False, str(e)

def ask_pdf_question(pdf_text, question):
    """
    Ask a question about the PDF using OpenAI's GPT-4.
    The prompt includes the extracted PDF text as context.
    """
    system_prompt = (
        "You are an expert assistant that answers questions about a PDF document. "
        "Use the provided PDF content to answer the question as accurately as possible. "
        "Only refer to the information in the PDF."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"PDF Content:\n{pdf_text}\n\nQuestion: {question}"}
    ]
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        logging.error(f"Error during OpenAI API call: {e}")
        return f"Error: {e}"

def run_app():
    """Run the Streamlit UI for PDF Extraction, Processing, and Chatbot."""
    st.title("PDF Extraction and Processing")
    st.markdown("Enter a PDF URL or upload a PDF file from your local system. Then choose an output format or interact with the loaded PDF via chat.")
    
    # Conversion options: five choices.
    conversion_type = st.radio("Choose Option:", 
                               options=["Convert to Excel (CSV)", "Convert to Excel (XLSX)", "Convert to Word", "Convert to Text", "Chat with PDF"])
    
    # Create two tabs: one for URL input and one for file upload.
    tab1, tab2 = st.tabs(["Extract from URL", "Upload PDF"])
    
    tmp_path = None  # This will store the temporary file path for the processed PDF.
    
    # Process PDF via URL
    with tab1:
        pdf_url = st.text_input("Enter PDF URL:")
        if st.button("Process URL"):
            if pdf_url:
                with st.spinner("Processing PDF from URL..."):
                    extracted_text = extract_text_from_pdf_url(pdf_url)
                st.session_state.pdf_text = extracted_text
                if conversion_type in ["Convert to Text", "Chat with PDF"]:
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
                        if conversion_type == "Convert to Excel (CSV)":
                            success, msg = convert_pdf_to_excel_csv(tmp_path, tmp_path + ".csv")
                            if success:
                                with open(tmp_path + ".csv", "rb") as f:
                                    st.download_button("Download Excel (CSV)", f, file_name="converted_tables.csv", on_click=noop)
                            else:
                                st.error(msg)
                        elif conversion_type == "Convert to Excel (XLSX)":
                            success, msg = convert_pdf_to_excel_xlsx(tmp_path, tmp_path + ".xlsx")
                            if success:
                                with open(tmp_path + ".xlsx", "rb") as f:
                                    st.download_button("Download Excel (XLSX)", f, file_name="converted_tables.xlsx", on_click=noop)
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
                # Layout: Display PDF preview and chat history side-by-side.
                try:
                    with open(tmp_path, "rb") as pdf_file:
                        base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
                    # Create two columns: left for PDF preview, right for chat history.
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown("### PDF Preview", unsafe_allow_html=True)
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    with col2:
                        st.markdown("### Chat History")
                        if "chat_history" not in st.session_state:
                            st.session_state.chat_history = []
                        for msg in st.session_state.chat_history:
                            if msg["role"] == "user":
                                st.chat_message("user").write(msg["content"])
                            else:
                                st.chat_message("assistant").write(msg["content"])
                except Exception as e:
                    st.error(f"Error displaying PDF or chat history: {e}")
            else:
                st.error("Please enter a valid PDF URL.")
    
    # Process PDF via Upload
    with tab2:
        uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
        if uploaded_file is not None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                if conversion_type in ["Convert to Text", "Chat with PDF"]:
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
                    st.session_state.pdf_text = extracted_text
                elif conversion_type == "Convert to Excel (CSV)":
                    success, msg = convert_pdf_to_excel_csv(tmp_path, tmp_path + ".csv")
                    if success:
                        with open(tmp_path + ".csv", "rb") as f:
                            st.download_button("Download Excel (CSV)", f, file_name="converted_tables.csv", on_click=noop)
                    else:
                        st.error(msg)
                elif conversion_type == "Convert to Excel (XLSX)":
                    success, msg = convert_pdf_to_excel_xlsx(tmp_path, tmp_path + ".xlsx")
                    if success:
                        with open(tmp_path + ".xlsx", "rb") as f:
                            st.download_button("Download Excel (XLSX)", f, file_name="converted_tables.xlsx", on_click=noop)
                    else:
                        st.error(msg)
                elif conversion_type == "Convert to Word":
                    success, msg = convert_pdf_to_docx(tmp_path, tmp_path + ".docx")
                    if success:
                        with open(tmp_path + ".docx", "rb") as f:
                            st.download_button("Download Word Document", f, file_name="converted_document.docx", on_click=noop)
                    else:
                        st.error(msg)
                # Layout: Display PDF preview and chat history side-by-side.
                try:
                    with open(tmp_path, "rb") as pdf_file:
                        base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown("### PDF Preview", unsafe_allow_html=True)
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    with col2:
                        st.markdown("### Chat History")
                        if "chat_history" not in st.session_state:
                            st.session_state.chat_history = []
                        for msg in st.session_state.chat_history:
                            if msg["role"] == "user":
                                st.chat_message("user").write(msg["content"])
                            else:
                                st.chat_message("assistant").write(msg["content"])
                except Exception as e:
                    st.error(f"Error displaying PDF or chat history: {e}")
            except Exception as e:
                st.error(f"Error processing uploaded file: {e}")
    
    # Place the chat input outside any tabs or columns.
    if conversion_type == "Chat with PDF":
        if "pdf_text" not in st.session_state or not st.session_state.pdf_text:
            st.info("Please process a PDF first to load its text for chat.")
        else:
            user_input = st.chat_input("Ask a question about the PDF:")
            if user_input:
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.spinner("Generating response..."):
                    answer = ask_pdf_question(st.session_state.pdf_text, user_input)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.experimental_rerun()

if __name__ == "__main__":
    run_app()
