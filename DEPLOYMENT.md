# ai4org Web Scraper Hub - Deployment Instructions

This document provides instructions for deploying and running the aioOrg Web Scraper Hub, a unified interface for multiple web scraping tools.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- Required Python packages (installed via requirements.txt)

## Installation

1. **Clone or download the repository**

2. **Install required dependencies**
   ```bash
   cd ai4orgWebScraper
   pip install -r requirements.txt
   git clone git@github.com:OnlineGBC/ai4orgWebScraper.git .
   git clone https://github.com/tesseract-ocr/tessdata.git  (for languages)
   sudo cp tessdata/*.traineddata /usr/share/tesseract-ocr/4.00/tessdata/
   ```

3. **Download NLTK resources (for the general web scraper)**
   ```bash
   python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
   ```

## Running the Application

### Option 1: Using the run script (recommended)

1. Make the run script executable (first time only):
   ```bash
   chmod +x run_main.sh
   ```

2. Run the application:
   ```bash
   ./run_main.sh
   ```

### Option 2: Using Streamlit directly

```bash
streamlit run main.py
```

## Accessing the Application

Once running, the application will be available at:
- Local URL: http://localhost:8501
- Network URL: http://[your-ip-address]:8501

## Using the Web Scraper Hub

### Main Menu

The main menu provides access to different scraper options:

1. **General Web Scraper**: Extract data from any public URL with authentication support
2. **LinkedIn Job Search**: Search for jobs using LinkedIn's official API
3. **Coming Soon**: Additional scrapers (Twitter Data Scraper, E-commerce Scraper)

Click on the button for the scraper you want to use.

### General Web Scraper

1. Enter the URL you want to scrape in the sidebar
2. Configure authentication if needed
3. Click "Fetch URL"
4. Use the tabs to:
   - Extract common fields
   - Define custom CSS selectors
   - View results
   - Generate visualizations
5. Export data in JSON or CSV format
6. Click "← Return to Menu" to go back to the main menu

### LinkedIn Job Search

1. Enter your LinkedIn API credentials in the sidebar
   - Client ID
   - Client Secret
   - Redirect URI
   - Access Token
2. Configure job search parameters
3. Click "Search Jobs"
4. Use the tabs to:
   - View search results
   - See job details
   - Access saved searches
   - Check API status
5. Export data in JSON or CSV format
6. Click "← Return to Menu" to go back to the main menu

## LinkedIn API Credentials

To use the LinkedIn Job Search functionality, you need to:

1. Create a LinkedIn Developer application at developer.linkedin.com
2. Configure the application with appropriate permissions for job search APIs
3. Generate an access token
4. Enter these credentials in the application

## Troubleshooting

- If you encounter issues with NLTK resources, the application will fall back to a simpler tokenization method
- For LinkedIn API issues, check your credentials and API status in the "API Status" tab

## Adding New Scrapers

The menu interface is designed to be extensible. To add new scrapers:

1. Create a new wrapper file (e.g., `twitter_app_wrapper.py`) following the pattern of existing wrappers
2. Update the `main.py` file to include the new scraper option
3. Implement the scraper functionality

## Support

For issues or questions, please contact the ai4org support team.
