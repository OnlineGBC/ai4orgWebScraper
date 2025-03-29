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

# Initialize a session state variable to control the displayed page
if "mode" not in st.session_state:
    st.session_state.mode = "menu"

if st.session_state.mode == "menu":
    # Main menu with center-aligned header
    st.markdown(
        "<h1 style='text-align: center;'>🌐 ai4org Web Scraper Hub</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h3 style='text-align: center;'>A comprehensive web scraping application with multiple scraper options</h3>",
        unsafe_allow_html=True,
    )
    st.write("Select an option below:")

    # Create a container for the cards
    container = st.container()
    col1, col2 = container.columns(2)

    # General Web Scraper Card
    with col1:
        st.markdown("### 🕸️ General Web Scraper")
        st.markdown("Extract data from any public URL with authentication support")
        st.markdown(
            """
            - Extract common fields (titles, headings, links, etc.)
            - Custom CSS selector support
            - Authentication for protected websites
            - Data visualization with interactive charts
            - Export results in multiple formats
            """
        )
        if st.button("Launch General Scraper", key="general_button"):
            st.session_state.mode = "general"
            st.experimental_rerun()

    # LinkedIn Job Search Card
    with col2:
        st.markdown("### 💼 LinkedIn Job Search")
        st.markdown("Search for jobs using LinkedIn's official API")
        st.markdown(
            """
            - Comprehensive search parameters
            - View detailed job information
            - Save searches for future reference
            - Export results in CSV or JSON formats
            - Monitor API usage and rate limits
            """
        )
        if st.button("Launch LinkedIn Scraper", key="linkedin_button"):
            st.session_state.mode = "linkedin"
            st.experimental_rerun()

elif st.session_state.mode == "general":
    # Launch the General Scraper UI
    sys.path.append(os.path.dirname(__file__))
    import app_wrapper

    app_wrapper.run_app()
elif st.session_state.mode == "linkedin":
    # Launch the LinkedIn scraper UI
    sys.path.append(os.path.dirname(__file__))
    import linkedin_app_wrapper

    linkedin_app_wrapper.run_app()
