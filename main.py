import streamlit as st
import sys
import warnings
import os

from config import OPENAI_CLIENT

# Suppress all warnings globally
warnings.simplefilter("ignore")

# Set page configuration
st.set_page_config(
    page_title="ai4org Web Scraper Hub",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar Navigation
st.sidebar.title("Navigation")
mode = st.sidebar.radio(
    "Select a Mode:",
    options=[
        "Home", 
        "General Scraper", 
        "PDF Processing", 
        "Email Processing",
        "LinkedIn Scraper"
    ]
)

if mode == "Home":
    st.markdown(
        """
        <h1 style='text-align: center;'>🌐 ai4org Web Scraper Hub</h1>
        <h3 style='text-align: center;'>
            Your centralized platform for intelligent, efficient, and flexible data extraction.
        </h3>
        <div style='font-size: 16px; padding: 20px 80px;'>
            <p>Explore a suite of powerful tools tailored to various scraping needs:</p>
            <ul>
                <li><b>🔍 General Web Scraper</b> – Extract structured data from websites with ease.</li>
                <li><b>📄 PDF Extraction & Processing</b> – Parse and analyze tables and text from complex PDF documents.</li>
                <li><b>👥 LinkedIn Scraper</b> – Automate profile data retrieval for professional insights (compliant use only).</li>
            </ul>
            <p>Use the sidebar to navigate to your desired scraper. Whether you're researching, aggregating content, or processing documents, this hub is built to streamline your workflow with minimal effort and maximum reliability.</p>
            <p><i>Start exploring—your data awaits!</i></p>
        </div>
        """,
        unsafe_allow_html=True
    )    

elif mode == "General Scraper":
    # Launch the General Scraper UI
    sys.path.append(os.path.dirname(__file__))
    import app_wrapper
    app_wrapper.run_app()

elif mode == "PDF Processing":
    # Launch the PDF Extraction UI from pdf_extractor module
    import sys
    try:
        import pdf_extractor
        pdf_extractor.run_app()
    except Exception as e:
        print(f"Error during import or run_app: {e}")  # Print the actual exception

elif mode == "Email Processing":
    # Launch the Email Processing UI from email_extractor module
    import sys
    try:
        import email_extractor
        email_extractor.run_app()
    except Exception as e:
        print(f"Error during import or run_app: {e}")  # Print the actual exception

elif mode == "LinkedIn Scraper":
    # Launch the LinkedIn Scraper UI
    sys.path.append(os.path.dirname(__file__))
    import linkedin_app_wrapper
    linkedin_app_wrapper.run_app()


