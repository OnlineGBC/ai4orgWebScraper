import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from web_scraper import WebScraper
import re
from collections import Counter
import nltk
from urllib.parse import urlparse

# Download NLTK resources explicitly with error handling
try:
    nltk.download('punkt')
    nltk.download('stopwords')
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
except Exception as e:
    st.error(f"Error loading NLTK resources: {str(e)}")
    # Fallback simple tokenizer in case NLTK fails
    def simple_tokenize(text):
        return re.findall(r'\b\w+\b', text.lower())

# Set page configuration
st.set_page_config(
    page_title="Web Scraper",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'scraper' not in st.session_state:
    st.session_state.scraper = WebScraper()
if 'url' not in st.session_state:
    st.session_state.url = ""
if 'fetched' not in st.session_state:
    st.session_state.fetched = False
if 'available_fields' not in st.session_state:
    st.session_state.available_fields = []
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'auth_required' not in st.session_state:
    st.session_state.auth_required = False
if 'custom_selectors' not in st.session_state:
    st.session_state.custom_selectors = {}
if 'word_cloud_generated' not in st.session_state:
    st.session_state.word_cloud_generated = False

# Main app title
st.title("🕸️ Web Scraper")
st.markdown("Extract data from any public URL with this easy-to-use web scraper.")

# Sidebar for inputs
with st.sidebar:
    st.header("Configuration")
    
    # URL input
    url = st.text_input("Enter URL to scrape:", placeholder="https://example.com")
    
    # Authentication toggle
    auth_required = st.checkbox("This URL requires authentication")
    
    # Authentication details (shown only if auth_required is checked)
    if auth_required:
        st.subheader("Authentication Details")
        auth_type = st.selectbox(
            "Authentication Type",
            options=["form", "basic"],
            index=0,
            help="Form authentication is most common. Basic is used for HTTP authentication."
        )
        
        username = st.text_input("Username:")
        password = st.text_input("Password:", type="password")
        
        if auth_type == "form":
            with st.expander("Advanced Form Settings"):
                username_field = st.text_input("Username Field Name:", value="username")
                password_field = st.text_input("Password Field Name:", value="password")
                form_selector = st.text_input("Form CSS Selector:", value="form")
    
    # Fetch button
    fetch_button = st.button("Fetch URL")
    
    if fetch_button:
        st.session_state.url = url
        st.session_state.auth_required = auth_required
        
        with st.spinner("Fetching URL..."):
            # Prepare authentication parameters if required
            auth_params = {}
            if auth_required:
                auth_params = {
                    "username": username,
                    "password": password,
                    "auth_type": auth_type
                }
                
                if auth_type == "form":
                    auth_params.update({
                        "username_field": username_field,
                        "password_field": password_field,
                        "form_selector": form_selector
                    })
            
            # Fetch the URL
            success, message = st.session_state.scraper.fetch_url(
                url, 
                auth_required=auth_required,
                **auth_params
            )
            
            if success:
                st.success("URL fetched successfully!")
                st.session_state.fetched = True
                st.session_state.available_fields = st.session_state.scraper.list_available_fields()
                st.session_state.results = {}  # Clear previous results
                st.session_state.word_cloud_generated = False
            else:
                st.error(f"Failed to fetch URL: {message}")
                st.session_state.fetched = False

# Helper functions for data visualization
def generate_word_frequency(text_data):
    """Generate word frequency data from text content"""
    if not text_data:
        return None, None
    
    # Combine all text if it's a list
    if isinstance(text_data, list):
        text_data = " ".join(text_data)
    
    try:
        # Try to use NLTK for tokenization
        stop_words = set(stopwords.words('english'))
        word_tokens = word_tokenize(text_data.lower())
        filtered_words = [w for w in word_tokens if w.isalpha() and w not in stop_words and len(w) > 2]
    except Exception as e:
        # Fallback to simple tokenization if NLTK fails
        st.warning(f"Using simple tokenization due to NLTK error: {str(e)}")
        words = simple_tokenize(text_data)
        # Simple stopwords list as fallback
        simple_stops = {'the', 'and', 'to', 'of', 'a', 'in', 'for', 'is', 'on', 'that', 'by', 'this', 'with', 'i', 'you', 'it'}
        filtered_words = [w for w in words if len(w) > 2 and w not in simple_stops]
    
    # Count word frequencies
    word_freq = Counter(filtered_words)
    top_words = word_freq.most_common(30)
    
    # Prepare data for visualization
    words = [word for word, count in top_words]
    counts = [count for word, count in top_words]
    
    return words, counts

def create_word_cloud_chart(words, counts):
    """Create a bar chart for word frequencies"""
    if not words or not counts:
        return None
    
    df = pd.DataFrame({'word': words, 'frequency': counts})
    fig = px.bar(df, x='word', y='frequency', title='Word Frequency Analysis',
                color='frequency', color_continuous_scale='Viridis')
    fig.update_layout(xaxis_title='Word', yaxis_title='Frequency',
                     xaxis={'categoryorder':'total descending'})
    return fig

def create_heading_structure_chart(headings_data):
    """Create a visualization of the heading structure"""
    if not headings_data or not isinstance(headings_data, dict):
        return None
    
    # Count headings by level
    h1_count = len(headings_data.get('h1', []))
    h2_count = len(headings_data.get('h2', []))
    h3_count = len(headings_data.get('h3', []))
    
    # Create chart
    fig = px.bar(
        x=['H1', 'H2', 'H3'],
        y=[h1_count, h2_count, h3_count],
        title='Heading Structure',
        color=['H1', 'H2', 'H3'],
        labels={'x': 'Heading Level', 'y': 'Count'}
    )
    return fig

def create_link_analysis(links_data):
    """Create analysis of link destinations"""
    if not links_data or not isinstance(links_data, list):
        return None
    
    # Extract domains from links
    domains = []
    for link in links_data:
        href = link.get('href', '')
        if href and href.startswith(('http://', 'https://')):
            try:
                domain = urlparse(href).netloc
                domains.append(domain)
            except:
                continue
    
    # Count domains
    domain_counts = Counter(domains)
    top_domains = domain_counts.most_common(10)
    
    # Create chart
    if top_domains:
        domain_names = [domain for domain, count in top_domains]
        domain_counts = [count for domain, count in top_domains]
        
        fig = px.pie(
            values=domain_counts,
            names=domain_names,
            title='External Link Destinations',
            hole=0.4
        )
        return fig
    
    return None

# Main content area
if st.session_state.fetched:
    st.header(f"Scraping: {st.session_state.url}")
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["Extract Data", "Custom Selectors", "Results", "Visualizations"])
    
    # Tab 1: Extract Data
    with tab1:
        st.subheader("Select fields to extract")
        
        if not st.session_state.available_fields:
            st.warning("No extractable fields detected on this page.")
        else:
            # Create columns for checkboxes
            cols = st.columns(3)
            selected_fields = []
            
            # Distribute fields across columns
            for i, field in enumerate(st.session_state.available_fields):
                col_idx = i % 3
                if cols[col_idx].checkbox(field.capitalize(), key=f"field_{field}"):
                    selected_fields.append(field)
            
            if selected_fields:
                if st.button("Extract Selected Fields"):
                    with st.spinner("Extracting data..."):
                        results = st.session_state.scraper.extract_multiple_fields(selected_fields)
                        st.session_state.results.update(results)
                        st.session_state.word_cloud_generated = False
                        st.success(f"Extracted {len(results)} fields successfully!")
                        # Switch to results tab
                        tab3.active = True
    
    # Tab 2: Custom Selectors
    with tab2:
        st.subheader("Custom CSS Selectors")
        st.markdown("""
        Enter custom CSS selectors to extract specific elements from the page.
        
        Format: `name: selector`
        
        Examples:
        - `main_heading: h1.main-title`
        - `product_price: span.price`
        - `navigation: nav.main-nav a`
        """)
        
        custom_selectors_text = st.text_area(
            "Enter one selector per line:",
            height=150,
            placeholder="main_heading: h1.main-title\nproduct_price: span.price"
        )
        
        if st.button("Extract Custom Selectors"):
            # Parse custom selectors
            selectors = {}
            for line in custom_selectors_text.strip().split('\n'):
                if ':' in line:
                    name, selector = line.split(':', 1)
                    selectors[name.strip()] = selector.strip()
            
            if selectors:
                st.session_state.custom_selectors = selectors
                with st.spinner("Extracting custom data..."):
                    custom_results = st.session_state.scraper.extract_custom_fields(selectors)
                    st.session_state.results.update(custom_results)
                    st.session_state.word_cloud_generated = False
                    st.success(f"Extracted {len(custom_results)} custom fields successfully!")
                    # Switch to results tab
                    tab3.active = True
            else:
                st.warning("No valid selectors found. Please use the format 'name: selector'")
    
    # Tab 3: Results
    with tab3:
        st.subheader("Extraction Results")
        
        if not st.session_state.results:
            st.info("No data extracted yet. Use the 'Extract Data' or 'Custom Selectors' tab to extract data.")
        else:
            # Display results
            for field, data in st.session_state.results.items():
                with st.expander(f"{field.capitalize()}", expanded=True):
                    # Handle different data types appropriately
                    if isinstance(data, str):
                        st.write(data)
                    elif isinstance(data, dict):
                        if field == "headings":
                            # Special handling for headings
                            if data.get("h1"):
                                st.write("H1 Headings:")
                                for h in data["h1"]:
                                    st.write(f"- {h}")
                            if data.get("h2"):
                                st.write("H2 Headings:")
                                for h in data["h2"]:
                                    st.write(f"- {h}")
                            if data.get("h3"):
                                st.write("H3 Headings:")
                                for h in data["h3"]:
                                    st.write(f"- {h}")
                        else:
                            # Generic dict display
                            st.json(data)
                    elif isinstance(data, list):
                        if field == "links":
                            # Create a DataFrame for links
                            if data and isinstance(data[0], dict) and "text" in data[0] and "href" in data[0]:
                                df = pd.DataFrame(data)
                                st.dataframe(df)
                            else:
                                st.write(data)
                        elif field == "images":
                            # Display images
                            if data and isinstance(data[0], dict) and "src" in data[0]:
                                cols = st.columns(3)
                                for i, img in enumerate(data):
                                    col_idx = i % 3
                                    with cols[col_idx]:
                                        if img["src"].startswith(('http://', 'https://')):
                                            st.image(img["src"], caption=img.get("alt", ""), width=200)
                                        else:
                                            # Handle relative URLs
                                            base_url = st.session_state.url
                                            if not base_url.endswith('/'):
                                                base_url += '/'
                                            img_url = base_url + img["src"].lstrip('/')
                                            st.write(f"Image: {img_url}")
                            else:
                                st.write(data)
                        elif field == "tables" and data:
                            # Display tables
                            for i, table in enumerate(data):
                                st.write(f"Table {i+1}:")
                                if table:
                                    # Convert to DataFrame
                                    df = pd.DataFrame(table[1:], columns=table[0] if table else None)
                                    st.dataframe(df)
                        else:
                            # Generic list display
                            for item in data:
                                st.write(f"- {item}")
                    else:
                        # Fallback for other data types
                        st.write(data)
            
            # Export options
            st.subheader("Export Results")
            col1, col2, col3 = st.columns(3)
            
            # JSON export
            with col1:
                json_data = json.dumps(st.session_state.results, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name="scraper_results.json",
                    mime="application/json"
                )
            
            # CSV export (simplified)
            with col2:
                # Create a flattened version for CSV
                flat_data = {}
                for field, value in st.session_state.results.items():
                    if isinstance(value, str):
                        flat_data[field] = value
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            if isinstance(v, list):
                                flat_data[f"{field}_{k}"] = ", ".join(str(item) for item in v)
                            else:
                                flat_data[f"{field}_{k}"] = v
                    elif isinstance(value, list):
                        if all(isinstance(item, str) for item in value):
                            flat_data[field] = ", ".join(value)
                        else:
                            flat_data[field] = str(value)
                
                csv_data = pd.DataFrame([flat_data]).to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name="scraper_results.csv",
                    mime="text/csv"
                )
            
            # Text export
            with col3:
                text_data = ""
                for field, value in st.session_state.results.items():
                    text_data += f"{field.upper()}:\n"
                    text_data += f"{json.dumps(value, indent=2)}\n\n"
                
                st.download_button(
                    label="Download TXT",
                    data=text_data,
                    file_name="scraper_results.txt",
                    mime="text/plain"
                )
    
    # Tab 4: Visualizations
    with tab4:
        st.subheader("Data Visualizations")
        
        if not st.session_state.results:
            st.info("No data to visualize. Extract data first using the 'Extract Data' or 'Custom Selectors' tab.")
        else:
            # Generate visualizations based on available data
            
            # Word frequency analysis
            st.write("### Text Content Analysis")
            
            # Collect all text content for analysis
            all_text = ""
            
            # Add title
            if "title" in st.session_state.results:
                all_text += st.session_state.results["title"] + " "
            
            # Add meta description
            if "meta_description" in st.session_state.results:
                all_text += st.session_state.results["meta_description"] + " "
            
            # Add headings
            if "headings" in st.session_state.results:
                headings = st.session_state.results["headings"]
                for level in ["h1", "h2", "h3"]:
                    if level in headings:
                        all_text += " ".join(headings[level]) + " "
            
            # Add paragraphs
            if "paragraphs" in st.session_state.results:
                paragraphs = st.session_state.results["paragraphs"]
                all_text += " ".join(paragraphs) + " "
            
            # Generate word frequency visualization
            if all_text:
                try:
                    words, counts = generate_word_frequency(all_text)
                    if words and counts:
                        word_chart = create_word_cloud_chart(words, counts)
                        if word_chart:
                            st.plotly_chart(word_chart, use_container_width=True)
                            st.session_state.word_cloud_generated = True
                        
                        # Show top words in a table
                        word_df = pd.DataFrame({'Word': words[:15], 'Frequency': counts[:15]})
                        st.write("#### Top Words")
                        st.dataframe(word_df, use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating word frequency analysis: {str(e)}")
                    st.info("Try extracting more text content from the page for better analysis.")
            
            # Heading structure analysis
            if "headings" in st.session_state.results:
                st.write("### Heading Structure Analysis")
                try:
                    heading_chart = create_heading_structure_chart(st.session_state.results["headings"])
                    if heading_chart:
                        st.plotly_chart(heading_chart, use_container_width=True)
                    else:
                        st.info("No heading structure to visualize.")
                except Exception as e:
                    st.error(f"Error generating heading structure analysis: {str(e)}")
            
            # Link analysis
            if "links" in st.session_state.results:
                st.write("### Link Analysis")
                links = st.session_state.results["links"]
                
                # Count total links
                st.metric("Total Links", len(links))
                
                try:
                    # External vs internal links
                    if links and isinstance(links[0], dict) and "href" in links[0]:
                        # Get domain of current page
                        current_domain = urlparse(st.session_state.url).netloc
                        
                        # Count external and internal links
                        external_links = 0
                        internal_links = 0
                        
                        for link in links:
                            href = link.get("href", "")
                            if href.startswith(('http://', 'https://')):
                                try:
                                    link_domain = urlparse(href).netloc
                                    if link_domain != current_domain:
                                        external_links += 1
                                    else:
                                        internal_links += 1
                                except:
                                    continue
                            else:
                                # Relative link
                                internal_links += 1
                        
                        # Display metrics
                        col1, col2 = st.columns(2)
                        col1.metric("Internal Links", internal_links)
                        col2.metric("External Links", external_links)
                        
                        # Create pie chart
                        fig = px.pie(
                            values=[internal_links, external_links],
                            names=['Internal', 'External'],
                            title='Link Distribution',
                            color_discrete_sequence=['#1f77b4', '#ff7f0e']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # External link analysis
                        link_chart = create_link_analysis(links)
                        if link_chart:
                            st.plotly_chart(link_chart, use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating link analysis: {str(e)}")
            
            # Image analysis
            if "images" in st.session_state.results:
                st.write("### Image Analysis")
                images = st.session_state.results["images"]
                
                # Count total images
                st.metric("Total Images", len(images))
                
                try:
                    # Count images with alt text
                    if images and isinstance(images[0], dict):
                        images_with_alt = sum(1 for img in images if img.get("alt", "").strip())
                        images_without_alt = len(images) - images_with_alt
                        
                        # Display metrics
                        col1, col2 = st.columns(2)
                        col1.metric("Images with Alt Text", images_with_alt)
                        col2.metric("Images without Alt Text", images_without_alt)
                        
                        # Create pie chart
                        fig = px.pie(
                            values=[images_with_alt, images_without_alt],
                            names=['With Alt Text', 'Without Alt Text'],
                            title='Image Accessibility',
                            color_discrete_sequence=['#2ca02c', '#d62728']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error generating image analysis: {str(e)}")

else:
    # Show instructions when no URL has been fetched
    st.info("👈 Enter a URL in the sidebar and click 'Fetch URL' to begin scraping.")
    
    # Example usage
    with st.expander("How to use this web scraper"):
        st.markdown("""
        ### Basic Usage
        1. Enter the URL you want to scrape in the sidebar
        2. Click "Fetch URL" to load the page
        3. Select the fields you want to extract
        4. Click "Extract Selected Fields"
        5. View and download your results
        
        ### Authentication
        If the website requires login:
        1. Check "This URL requires authentication"
        2. Enter your username and password
        3. Select the appropriate authentication type
        
        ### Custom Selectors
        For more precise data extraction:
        1. Go to the "Custom Selectors" tab
        2. Enter CSS selectors in the format `name: selector`
        3. Click "Extract Custom Selectors"
        
        ### Visualizations
        After extracting data:
        1. Go to the "Visualizations" tab
        2. Explore interactive charts and insights about the extracted content
        
        ### CSS Selector Examples
        - `h1`: Selects all h1 headings
        - `.classname`: Selects elements with class "classname"
        - `#id`: Selects element with ID "id"
        - `div.content p`: Selects paragraphs inside div with class "content"
        """)

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • [GitHub](https://github.com) • [Report Issues](https://github.com)")
