# email_extractor.py
# This script creates a Streamlit app to upload, parse, and analyze email files (.eml or .msg).
# It extracts details like sender, subject, and attachments, groups emails into threads, and offers export options (JSON, CSV, PDF).
# Features include sentiment analysis, content safety checks, and text normalization for better display.

import streamlit as st  # Web app framework for interactive UI
import inspect  # Used to get line numbers for debugging
import os  # For file operations like removing temp files
import char_text_norm as char_text_norm  # Custom module to clean up text
import re  # Regular expressions for text processing
import json  # For JSON export
import csv  # For CSV export
import io  # For in-memory file handling
import tempfile  # For temporary file creation
import email  # Built-in email parsing library
from email import policy  # Email parsing policy
from email.parser import BytesParser  # Parser for email bytes

import extract_msg  # Library to parse .msg files (Outlook format)
from fpdf import FPDF  # Library to generate PDF reports
import nltk  # Natural language toolkit for sentiment analysis
from nltk.sentiment.vader import SentimentIntensityAnalyzer  # VADER sentiment analyzer

# Ensure nltk vader_lexicon is downloaded for sentiment analysis
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon")  # Download if missing

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

def log_debug(msg):
    # Log debug messages with the line number of the caller
    line_no = inspect.currentframe().f_back.f_lineno
    # st.write(f"DEBUG (line {line_no}): {msg}")  # Commented out for later use

# Helper: Normalize subject by removing common prefixes
def normalize_subject(subject):
    # Clean up email subject for consistent threading
    if subject:
        subject = subject.lower()
        subject = re.sub(r'^(re:|fwd:)\s*', '', subject)  # Remove "re:" or "fwd:"
        return subject.strip()
    return "no subject"

# Helper: Simple summarization (naive implementation)
def summarize_text(text, max_length=200):
    # Shorten text to a manageable length with ellipsis if needed
    if text and len(text) > max_length:
        return text[:max_length] + "..."
    return text

""" 
Option 1 below code manages the conversions but display is not great. This is currently disabled
def is_content_safe(content):
    if content:
        try:
            # Convert content to bytes if it's not already bytes.
            content_bytes = content if isinstance(content, bytes) else content.encode('utf-8', errors='ignore')
        except Exception:
            # If conversion fails, fall back to the original content.
            content_bytes = content
        if b"<script" in content_bytes or b"javascript:" in content_bytes:
            return False
    return True
"""

""" 
Option 2 below code manages the conversions but display should be better. This is currently enabled
""" 
def is_content_safe(content):
    """
    Check whether the content is safe by searching for suspicious patterns.
    For bytes input, decode it into a string (using UTF-8 with errors ignored)
    solely for comparison.
    """
    if content:
        if isinstance(content, bytes):
            try:
                check = content.decode('utf-8', errors='ignore').lower()
            except Exception:
                check = ""  # Fallback to empty string if decoding fails
        else:
            check = content.lower()
        if "<script" in check or "javascript:" in check:  # Look for potential scripts
            return False
    return True

# Helper: Parse attachments for eml messages
def extract_attachments_eml(msg_obj):
    # Extract attachment details from .eml files
    attachments = []
    for part in msg_obj.walk():  # Walk through all parts of the email
        content_disp = part.get("Content-Disposition", "")
        if content_disp and "attachment" in content_disp.lower():
            filename = part.get_filename() or "attachment"  # Default name if none found
            payload = part.get_payload(decode=True)  # Get binary content
            mime = part.get_content_type()  # MIME type of the attachment
            attachments.append({
                "filename": filename,
                "content": payload,
                "mime": mime
            })
    return attachments

# Helper: Parse attachments for msg messages using extract_msg
def extract_attachments_msg(msg):
    # Extract attachment details from .msg files
    attachments = []
    for att in msg.attachments:
        filename = att.longFilename or att.shortFilename or "attachment"  # Pick best filename
        content = att.data  # Binary content
        # Guess MIME type based on file extension
        ext = os.path.splitext(filename)[1].lower()
        mime = "application/octet-stream"  # Default MIME
        if ext in [".jpg", ".jpeg"]:
            mime = "image/jpeg"
        elif ext == ".png":
            mime = "image/png"
        elif ext == ".pdf":
            mime = "application/pdf"
        attachments.append({
            "filename": filename,
            "content": content,
            "mime": mime
        })
    return attachments

# Parse .eml files using built-in email package
def parse_eml(file_bytes):
    # Parse an .eml file and extract its metadata and content
    msg = BytesParser(policy=policy.default).parsebytes(file_bytes)
    details = {
        "subject": msg.get("subject", "No Subject"),
        "from": msg.get("from", "Unknown Sender"),
        "to": msg.get("to", "Unknown Recipients"),
        "cc": msg.get("cc", "N/A"),
        "bcc": msg.get("bcc", "N/A"),
        "reply_to": msg.get("reply-to", "N/A"),
        "message_id": msg.get("message-id", "N/A"),
        "date": msg.get("date", "Unknown Date"),
        "attachments": extract_attachments_eml(msg)
    }

    html_body = None
    plain_body = None
    if msg.is_multipart():  # Handle multi-part emails
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_body is None:
                html_body = part.get_content()
            elif ctype == "text/plain" and plain_body is None:
                plain_body = part.get_content()
    else:  # Single-part email
        ctype = msg.get_content_type()
        if ctype == "text/html":
            html_body = msg.get_content()
        else:
            plain_body = msg.get_content()
    
    # Normalize text content for consistency
    details["plain_body"] = char_text_norm.normalize_text(plain_body or "No content available.")
    if html_body:
        details["html_body"] = char_text_norm.normalize_text(html_body)
    else:
        details["html_body"] = None

    sentiment = sia.polarity_scores(details["plain_body"])  # Analyze sentiment
    details["sentiment"] = sentiment
    details["summary"] = summarize_text(details["plain_body"])  # Summarize content
    details["is_safe"] = is_content_safe(details["plain_body"])  # Check safety
    
    return details

def parse_msg(file_bytes, file_name):
    # Parse an .msg file using a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".msg") as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    msg = extract_msg.Message(temp_path)
    details = {
        "subject": msg.subject or "No Subject",
        "from": msg.sender or "Unknown Sender",
        "to": msg.to or "Unknown Recipients",
        "cc": msg.cc or "N/A",
        "bcc": getattr(msg, "bcc", "N/A"),
        "reply_to": getattr(msg, "reply", "N/A"),
        "message_id": getattr(msg, "message_id", "N/A"),
        "date": msg.date or "Unknown Date",
        "attachments": extract_attachments_msg(msg)
    }
    details["html_body"] = msg.htmlBody if hasattr(msg, "htmlBody") else None
    details["plain_body"] = msg.body or "No content available."

    # Convert bytes to string if necessary
    if isinstance(details["plain_body"], bytes):
        details["plain_body"] = details["plain_body"].decode('utf-8', errors='ignore')
    
    if details["html_body"] and isinstance(details["html_body"], bytes):
        details["html_body"] = details["html_body"].decode('utf-8', errors='ignore')
    
    # Normalize text content
    details["plain_body"] = char_text_norm.normalize_text(details["plain_body"])
    if details["html_body"]:
        details["html_body"] = char_text_norm.normalize_text(details["html_body"])

    sentiment = sia.polarity_scores(details["plain_body"])
    details["sentiment"] = sentiment
    details["summary"] = summarize_text(details["plain_body"])
    details["is_safe"] = is_content_safe(details["plain_body"])
    
    os.remove(temp_path)  # Clean up temp file
    return details

# Function to export emails data to JSON
def export_to_json(data):
    # Export email data as JSON, excluding binary content
    export_data = []
    for email_item in data:
        email_copy = {}
        for key, value in email_item.items():
            if key == "attachments":
                # Include attachment metadata, skip binary content
                cleaned_attachments = []
                for att in value:
                    att_copy = {k: v for k, v in att.items() if k != "content"}
                    cleaned_attachments.append(att_copy)
                email_copy[key] = cleaned_attachments
            elif not isinstance(value, bytes):  # Skip binary data
                email_copy[key] = value
        export_data.append(email_copy)
    
    json_data = json.dumps(export_data, indent=4, default=str)  # Handle non-JSON-serializable objects
    return json_data

# Function to export emails data to CSV (flattened)
def export_to_csv(data):
    # Export email data as a flat CSV table
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Subject", "From", "To", "CC", "Date", "Message ID", "Summary", "Sentiment Compound"]
    writer.writerow(header)
    for email_item in data:
        sentiment_value = email_item.get("sentiment", {}).get("compound", 0) if isinstance(email_item.get("sentiment"), dict) else 0
        writer.writerow([
            email_item.get("subject", ""),
            email_item.get("from", ""),
            email_item.get("to", ""),
            email_item.get("cc", ""),
            email_item.get("date", ""),
            email_item.get("message_id", ""),
            email_item.get("summary", ""),
            sentiment_value
        ])
    return output.getvalue()

# Function to export emails data to a PDF report using fpdf
def export_to_pdf(data):
    # Generate a PDF report summarizing email data
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Email Analysis Report", ln=1, align="C")
    pdf.ln(5)
    
    for idx, email_item in enumerate(data, 1):
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Email {idx}: {email_item.get('subject', 'No Subject')}", ln=1)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 8, f"From: {email_item.get('from', '')}", ln=1)
        pdf.cell(0, 8, f"To: {email_item.get('to', '')}", ln=1)
        pdf.cell(0, 8, f"Date: {email_item.get('date', '')}", ln=1)
        
        # Add sentiment score if available
        sentiment = email_item.get("sentiment", {})
        if isinstance(sentiment, dict) and "compound" in sentiment:
            pdf.cell(0, 8, f"Sentiment Score: {sentiment['compound']:.2f}", ln=1)
        
        # Add summary
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, "Summary:", ln=1)
        pdf.set_font("Arial", "", 10)
        summary = email_item.get("summary", "No summary available")
        pdf.multi_cell(0, 8, summary)
        
        # List attachments
        attachments = email_item.get("attachments", [])
        if attachments:
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 8, f"Attachments: {len(attachments)}", ln=1)
            pdf.set_font("Arial", "", 10)
            for att in attachments:
                pdf.cell(0, 8, f"- {att.get('filename', 'Unknown')}", ln=1)
        
        pdf.ln(5)
        pdf.cell(0, 0, "", ln=1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())  # Separator line
        pdf.ln(5)
    
    pdf_output = io.BytesIO()
    try:
        pdf_str = pdf.output(dest='S')  # Get PDF as string or bytes
        if isinstance(pdf_str, str):
            pdf_output.write(pdf_str.encode('latin1'))  # Encode string to bytes
        else:
            pdf_output.write(pdf_str)  # Write bytes directly
        pdf_output.seek(0)
        return pdf_output
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        return io.BytesIO(b"Error generating PDF")

# The main run_app() function that encapsulates the Streamlit UI
def run_app():
    # Main function to run the Streamlit email processing app
    try:
        log_debug("run_app() started")
        if "emails_history" not in st.session_state:
            st.session_state.emails_history = []  # Store parsed emails
            st.session_state.processed_files = set()  # Track processed files to avoid duplicates
        log_debug("Session history initialized")

        st.sidebar.header("Email Upload & Filters")
        uploaded_files = st.sidebar.file_uploader("Upload email files (.eml or .msg)", type=["eml", "msg"], accept_multiple_files=True)
        log_debug("File uploader created")

        # Sidebar filters for searching emails
        filter_subject = st.sidebar.text_input("Filter by subject")
        filter_sender = st.sidebar.text_input("Filter by sender")
        filter_date = st.sidebar.text_input("Filter by date (YYYY-MM-DD)")
        log_debug("Search/filter widgets created")

        st.title("Advanced Email Parser and Processor")
        log_debug("Title set")

        parsed_emails = []  # Temporary list for current batch

        if uploaded_files:
            for uploaded_file in uploaded_files:
                # Skip already processed files
                file_identifier = f"{uploaded_file.name}_{uploaded_file.size}"
                if file_identifier in st.session_state.processed_files:
                #    st.info(f"Skipping already processed file: {uploaded_file.name}")
                    continue
                
                # st.write(f"DEBUG: Processing file: {uploaded_file.name}")  # Commented out for later use
                file_bytes = uploaded_file.read()
                file_name = uploaded_file.name.lower()
                if not (file_name.endswith(".eml") or file_name.endswith(".msg")):
                    st.error(f"{uploaded_file.name}: Please upload eml or msg files only")
                    continue

                try:
                    if file_name.endswith(".eml"):
                        details = parse_eml(file_bytes)
                    else:  # .msg file
                        details = parse_msg(file_bytes, file_name)
                        
                    details["filename"] = uploaded_file.name
                    details["norm_subject"] = normalize_subject(details.get("subject"))  # For threading
                    parsed_emails.append(details)
                    st.session_state.emails_history.append(details)
                    st.session_state.processed_files.add(file_identifier)  # Mark as processed
                    log_debug(f"Processed file {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")
                    # st.write(f"DEBUG: Error processing {uploaded_file.name}: {e}")  # Commented out for later use

        # Group emails into threads by normalized subject
        threads = {}
        for email_item in st.session_state.emails_history:
            key = email_item.get("norm_subject", "no subject")
            if key not in threads:
                threads[key] = []
            # Avoid duplicate emails in a thread
            message_id = email_item.get("message_id", "")
            if not any(e.get("message_id", "") == message_id for e in threads[key]):
                threads[key].append(email_item)
        log_debug("Grouped emails into threads")

        def thread_matches(thread_emails, subject_filter, sender_filter, date_filter):
            # Check if a thread matches the filters
            for email_item in thread_emails:
                if subject_filter and subject_filter.lower() not in email_item.get("subject", "").lower():
                    continue
                if sender_filter and sender_filter.lower() not in email_item.get("from", "").lower():
                    continue
                if date_filter and date_filter not in email_item.get("date", ""):
                    continue
                return True
            return False

        # Apply filters to threads
        filtered_threads = {}
        for key, emails in threads.items():
            if thread_matches(emails, filter_subject, filter_sender, filter_date):
                filtered_threads[key] = emails
        log_debug("Filtered threads created")

        st.header("Email Threads")
        if not filtered_threads:
            st.info("No emails to display. Upload some emails or adjust filters.")
        else:
            for thread, emails in filtered_threads.items():
                with st.expander(f"Thread: {emails[0].get('subject', 'No Subject')} (Total emails: {len(emails)})"):
                    for idx, email_item in enumerate(emails, start=1):
                        st.markdown(f"#### Email {idx} - {email_item.get('subject')}")
                        # st.write(f"**From:** {email_item.get('from')}")  # Commented out for later use
                        st.markdown(f"**From:** {email_item.get('from')}")
                        # st.write(f"**To:** {email_item.get('to')}")  # Commented out for later use
                        st.markdown(f"**To:** {email_item.get('to')}")
                        # st.write(f"**CC:** {email_item.get('cc')}")  # Commented out for later use
                        st.markdown(f"**CC:** {email_item.get('cc')}")
                        # st.write(f"**BCC:** {email_item.get('bcc')}")  # Commented out for later use
                        st.markdown(f"**BCC:** {email_item.get('bcc')}")
                        # st.write(f"**Reply-To:** {email_item.get('reply_to')}")  # Commented out for later use
                        st.markdown(f"**Reply-To:** {email_item.get('reply_to')}")
                        # st.write(f"**Message-ID:** {email_item.get('message_id')}")  # Commented out for later use
                        st.markdown(f"**Message-ID:** {email_item.get('message_id')}")
                        # st.write(f"**Date:** {email_item.get('date')}")  # Commented out for later use
                        st.markdown(f"**Date:** {email_item.get('date')}")
                        # st.write(f"**Sentiment:** {email_item.get('sentiment')}")  # Commented out for later use
                        st.markdown(f"**Sentiment:** {email_item.get('sentiment')}")
                        # st.write(f"**Summary:** {email_item.get('summary')}")  # Commented out for later use
                        st.markdown(f"**Summary:** {email_item.get('summary')}")
                        if email_item.get("html_body") and is_content_safe(email_item.get("html_body")):
                            st.markdown(email_item.get("html_body"), unsafe_allow_html=True)  # Render HTML if safe
                        else:
                            st.text(email_item.get("plain_body"))  # Fallback to plain text

                        # Display and allow downloading attachments
                        attachments = email_item.get("attachments", [])
                        if attachments:
                            # st.write("**Attachments:**")  # Commented out for later use
                            st.markdown("**Attachments:**")
                        for att_idx, att in enumerate(attachments):
                            st.download_button(
                                label=f"Download {att['filename']}",
                                data=att["content"],
                                file_name=att["filename"],
                                mime=att["mime"],
                                key=f"download_button_{att['filename']}_{idx}_{att_idx}"
                            )

                        st.markdown("---")  # Separator between emails
        log_debug("Finished displaying threads")

        st.header("Export Parsed Data")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Export as JSON"):
                json_data = export_to_json(st.session_state.emails_history)
                st.download_button("Download JSON", data=json_data, file_name="emails.json", mime="application/json")
        with col2:
            if st.button("Export as CSV"):
                csv_data = export_to_csv(st.session_state.emails_history)
                st.download_button("Download CSV", data=csv_data, file_name="emails.csv", mime="text/csv")
        with col3:
            if st.button("Export as PDF"):
                pdf_file = export_to_pdf(st.session_state.emails_history)
                st.download_button("Download PDF", data=pdf_file, file_name="emails.pdf", mime="application/pdf")
        log_debug("Finished export options")
    except Exception as e:
        st.error(f"run_app() encountered an error: {e}")
        import traceback
        # st.write("DEBUG: run_app() exception:")  # Commented out for later use
        # st.write(traceback.format_exc())  # Commented out for later use
        raise

if __name__ == "__main__":
    run_app()  # Start the app