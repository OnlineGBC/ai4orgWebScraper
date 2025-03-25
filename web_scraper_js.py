import sys
import requests
from bs4 import BeautifulSoup
import json
import base64
from urllib.parse import urlparse
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import subprocess

class WebScraperJS:
    """Web scraper class with JavaScript support using Selenium"""
    
    def __init__(self):
        self.url = None
        self.soup = None
        self.data = {}
        self.session = requests.Session()
        self.driver = None
        
    def _find_chrome_binary(self):
        """Find Chrome or Chromium binary path"""
        # Check common locations
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                return path
        
        # Try using which command
        try:
            result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            result = subprocess.run(['which', 'chromium-browser'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        
        return None
        
    def _initialize_driver(self):
        """Initialize Selenium WebDriver with headless Chrome"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Find Chrome binary path
            chrome_binary = self._find_chrome_binary()
            if chrome_binary:
                chrome_options.binary_location = chrome_binary
            
            # Initialize Chrome WebDriver
            try:
                # First try with ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                # If that fails, try with default service
                driver = webdriver.Chrome(options=chrome_options)
            
            return driver, None
        except Exception as e:
            # Try Firefox as fallback
            try:
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                from selenium.webdriver.firefox.service import Service as FirefoxService
                from webdriver_manager.firefox import GeckoDriverManager
                
                firefox_options = FirefoxOptions()
                firefox_options.add_argument("--headless")
                
                try:
                    service = FirefoxService(GeckoDriverManager().install())
                    driver = webdriver.Firefox(service=service, options=firefox_options)
                except:
                    driver = webdriver.Firefox(options=firefox_options)
                
                return driver, None
            except Exception as firefox_error:
                return None, f"Failed to initialize WebDriver: {str(e)}. Firefox fallback also failed: {str(firefox_error)}"
    
    def fetch_url(self, url, auth_required=False, use_javascript=True, wait_time=5, **auth_params):
        """Fetch content from the provided URL with JavaScript support"""
        try:
            # Validate URL format
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return False, "Error: Invalid URL format. Please include http:// or https://"
            
            domain = parsed_url.netloc
            
            # Determine if we should use Selenium (JavaScript) or requests
            if use_javascript:
                # Initialize Selenium WebDriver if not already initialized
                if self.driver is None:
                    self.driver, error = self._initialize_driver()
                    if error:
                        return False, error
                
                # Handle authentication if required
                if auth_required:
                    auth_success, auth_message = self._authenticate_with_selenium(url, **auth_params)
                    if not auth_success:
                        return False, f"Authentication failed: {auth_message}"
                
                # Navigate to the URL
                self.driver.get(url)
                
                # Wait for the page to load
                time.sleep(wait_time)
                
                # Get the page source after JavaScript execution
                page_source = self.driver.page_source
                
                self.url = url
                self.soup = BeautifulSoup(page_source, 'lxml')
                return True, "Successfully fetched content with JavaScript support"
            
            else:
                # Use regular requests for non-JavaScript pages
                # Add user agent to avoid being blocked
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # Handle authentication if required
                if auth_required:
                    auth_success, auth_message = self._authenticate(url, **auth_params)
                    if not auth_success:
                        return False, f"Authentication failed: {auth_message}"
                
                # Use the session to maintain cookies and authentication
                response = self.session.get(url, headers=headers, timeout=10)
                response.raise_for_status()  # Raise exception for 4XX/5XX responses
                
                self.url = url
                self.soup = BeautifulSoup(response.text, 'lxml')
                return True, "Successfully fetched content"
                
        except Exception as e:
            return False, f"Error fetching URL: {str(e)}"
        
    def _authenticate_with_selenium(self, url, username=None, password=None, auth_type="form", 
                                   username_field="username", password_field="password", 
                                   form_selector="form", submit_button=None, auth_url=None,
                                   success_indicator=None):
        """
        Authenticate with a website using Selenium
        
        Parameters:
        - url: The website URL
        - username: Login username
        - password: Login password
        - auth_type: Authentication type ('form', 'basic', 'custom')
        - username_field: Name or ID of username field in form
        - password_field: Name or ID of password field in form
        - form_selector: CSS selector for the login form
        - submit_button: CSS selector for the submit button
        - auth_url: Specific authentication URL if different from main URL
        - success_indicator: Text or element that indicates successful login
        
        Returns:
        - (success, message) tuple
        """
        try:
            # Determine authentication URL
            if not auth_url:
                auth_url = url
                
            # Navigate to the auth URL
            self.driver.get(auth_url)
            
            # Wait for the page to load
            time.sleep(3)
            
            if auth_type == "form":
                # Find the form
                form = self.driver.find_element(By.CSS_SELECTOR, form_selector)
                if not form:
                    return False, f"Login form not found using selector: {form_selector}"
                
                # Find username and password fields
                try:
                    # Try by name first
                    username_elem = self.driver.find_element(By.NAME, username_field)
                except:
                    try:
                        # Try by ID
                        username_elem = self.driver.find_element(By.ID, username_field)
                    except:
                        return False, f"Username field not found: {username_field}"
                
                try:
                    # Try by name first
                    password_elem = self.driver.find_element(By.NAME, password_field)
                except:
                    try:
                        # Try by ID
                        password_elem = self.driver.find_element(By.ID, password_field)
                    except:
                        return False, f"Password field not found: {password_field}"
                
                # Enter credentials
                username_elem.send_keys(username)
                password_elem.send_keys(password)
                
                # Submit the form
                if submit_button:
                    try:
                        submit_btn = self.driver.find_element(By.CSS_SELECTOR, submit_button)
                        submit_btn.click()
                    except:
                        # If submit button not found, try submitting the form directly
                        form.submit()
                else:
                    # Try submitting the form directly
                    form.submit()
                
                # Wait for the page to load after submission
                time.sleep(3)
                
                # Check if login was successful
                if success_indicator:
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{success_indicator}')]"))
                        )
                        return True, "Form authentication successful"
                    except:
                        return False, "Form authentication failed: Success indicator not found"
                else:
                    # Default check: we're redirected away from login page
                    current_url = self.driver.current_url
                    if current_url != auth_url:
                        return True, "Form authentication successful"
                    else:
                        return False, "Form authentication failed: Still on login page"
            
            elif auth_type == "basic":
                # HTTP Basic Authentication with Selenium requires a different approach
                # We need to include credentials in the URL
                parsed_url = urlparse(auth_url)
                auth_url_with_creds = f"{parsed_url.scheme}://{username}:{password}@{parsed_url.netloc}{parsed_url.path}"
                
                self.driver.get(auth_url_with_creds)
                time.sleep(3)
                
                # Check if we're on the expected page
                if success_indicator:
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{success_indicator}')]"))
                        )
                        return True, "Basic authentication successful"
                    except:
                        return False, "Basic authentication failed: Success indicator not found"
                else:
                    # Default check: response is OK
                    return True, "Basic authentication completed"
            
            else:
                return False, f"Unsupported authentication type for Selenium: {auth_type}"
                
        except Exception as e:
            return False, f"Selenium authentication error: {str(e)}"
    
    def _authenticate(self, url, username=None, password=None, auth_type="form", 
                     username_field="username", password_field="password", 
                     form_selector="form", submit_button=None, auth_url=None,
                     success_indicator=None):
        """
        Authenticate with a website using requests
        
        Parameters:
        - url: The website URL
        - username: Login username
        - password: Login password
        - auth_type: Authentication type ('form', 'basic', 'custom')
        - username_field: Name of username field in form
        - password_field: Name of password field in form
        - form_selector: CSS selector for the login form
        - submit_button: CSS selector for the submit button
        - auth_url: Specific authentication URL if different from main URL
        - success_indicator: Text or element that indicates successful login
        
        Returns:
        - (success, message) tuple
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Determine authentication URL
        if not auth_url:
            auth_url = url
        
        # Perform authentication based on type
        if auth_type == "basic":
            # HTTP Basic Authentication
            self.session.auth = (username, password)
            try:
                response = self.session.get(auth_url, timeout=10)
                success = response.status_code == 200
                return success, "Basic authentication successful" if success else "Basic authentication failed"
            except Exception as e:
                return False, f"Authentication error: {str(e)}"
                
        elif auth_type == "form":
            # Form-based authentication
            try:
                # Get the login page to retrieve any CSRF tokens
                response = self.session.get(auth_url, timeout=10)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find the login form
                form = soup.select_one(form_selector)
                if not form:
                    return False, f"Login form not found using selector: {form_selector}"
                
                # Extract form action URL
                form_action = form.get('action')
                if form_action:
                    if form_action.startswith('/'):
                        # Relative URL
                        form_action = f"{parsed_url.scheme}://{domain}{form_action}"
                    elif not form_action.startswith('http'):
                        # Relative URL without leading slash
                        form_action = f"{parsed_url.scheme}://{domain}/{form_action}"
                else:
                    form_action = auth_url
                
                # Prepare form data
                form_data = {}
                
                # Extract all input fields from the form
                for input_field in form.find_all('input'):
                    input_name = input_field.get('name')
                    input_value = input_field.get('value', '')
                    input_type = input_field.get('type', '').lower()
                    
                    # Skip submit buttons and empty names
                    if not input_name or input_type == 'submit':
                        continue
                    
                    # Add to form data
                    form_data[input_name] = input_value
                
                # Add username and password to form data
                form_data[username_field] = username
                form_data[password_field] = password
                
                # Submit the form
                response = self.session.post(form_action, data=form_data, timeout=10)
                
                # Check if login was successful
                if success_indicator:
                    success = success_indicator in response.text
                else:
                    # Default check: response is OK and we're redirected away from login page
                    success = response.status_code == 200 and response.url != auth_url
                
                return success, "Form authentication successful" if success else "Form authentication failed"
                
            except Exception as e:
                return False, f"Form authentication error: {str(e)}"
                
        elif auth_type == "custom":
            # Custom authentication - would need specific implementation
            return False, "Custom authentication requires specific implementation"
            
        else:
            return False, f"Unsupported authentication type: {auth_type}"
    
    def list_available_fields(self):
        """List common fields that can be extracted from the page"""
        if not self.soup:
            return []
        
        fields = []
        
        # Title
        if self.soup.title:
            fields.append("title")
        
        # Meta description
        if self.soup.find("meta", attrs={"name": "description"}):
            fields.append("meta_description")
        
        # Headings
        if self.soup.find_all(['h1', 'h2', 'h3']):
            fields.append("headings")
        
        # Links
        if self.soup.find_all('a'):
            fields.append("links")
        
        # Images
        if self.soup.find_all('img'):
            fields.append("images")
        
        # Tables
        if self.soup.find_all('table'):
            fields.append("tables")
        
        # Paragraphs
        if self.soup.find_all('p'):
            fields.append("paragraphs")
        
        # Lists
        if self.soup.find_all(['ul', 'ol']):
            fields.append("lists")
        
        # Forms
        if self.soup.find_all('form'):
            fields.append("forms")
        
        return fields
    
    def extract_field(self, field_name, selector=None):
        """Extract data for a specific field"""
        if not self.soup:
            return None
        
        result = None
        
        # If a custom CSS selector is provided, use it
        if selector:
            elements = self.soup.select(selector)
            if elements:
                result = [elem.get_text(strip=True) for elem in elements]
                if len(result) == 1:
                    result = result[0]
            return result
        
        # Otherwise use predefined field extractors
        if field_name == "title":
            result = self.soup.title.string if self.soup.title else None
        
        elif field_name == "meta_description":
            meta = self.soup.find("meta", attrs={"name": "description"})
            result = meta["content"] if meta and "content" in meta.attrs else None
        
        elif field_name == "headings":
            h1 = [h.get_text(strip=True) for h in self.soup.find_all('h1')]
            h2 = [h.get_text(strip=True) for h in self.soup.find_all('h2')]
            h3 = [h.get_text(strip=True) for h in self.soup.find_all('h3')]
            result = {"h1": h1, "h2": h2, "h3": h3}
        
        elif field_name == "links":
            result = [{"text": a.get_text(strip=True), "href": a.get("href")} 
                     for a in self.soup.find_all('a') if a.get("href")]
        
        elif field_name == "images":
            result = [{"alt": img.get("alt", ""), "src": img.get("src")} 
                     for img in self.soup.find_all('img') if img.get("src")]
        
        elif field_name == "tables":
            tables = []
            for i, table in enumerate(self.soup.find_all('table')):
                rows = []
                for tr in table.find_all('tr'):
                    row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if row:  # Skip empty rows
                        rows.append(row)
                if rows:  # Skip empty tables
                    tables.append(rows)
            result = tables
        
        elif field_name == "paragraphs":
            result = [p.get_text(strip=True) for p in self.soup.find_all('p')]
        
        elif field_name == "lists":
            lists = []
            for list_elem in self.soup.find_all(['ul', 'ol']):
                items = [li.get_text(strip=True) for li in list_elem.find_all('li')]
                if items:  # Skip empty lists
                    lists.append(items)
            result = lists
        
        elif field_name == "forms":
            forms = []
            for form in self.soup.find_all('form'):
                form_data = {
                    "action": form.get("action", ""),
                    "method": form.get("method", ""),
                    "fields": []
                }
                
                for input_field in form.find_all(['input', 'select', 'textarea']):
                    field_info = {
                        "type": input_field.name,
                        "name": input_field.get("name", ""),
                        "id": input_field.get("id", ""),
                        "value": input_field.get("value", "")
                    }
                    
                    if input_field.name == "input":
                        field_info["input_type"] = input_field.get("type", "text")
                    
                    form_data["fields"].append(field_info)
                
                forms.append(form_data)
            
            result = forms
        
        return result
    
    def extract_multiple_fields(self, field_names):
        """Extract multiple fields at once"""
        results = {}
        for field in field_names:
            results[field] = self.extract_field(field)
        return results
    
    def extract_custom_fields(self, selectors_dict):
        """Extract data using custom CSS selectors"""
        results = {}
        for name, selector in selectors_dict.items():
            results[f"custom_{name}"] = self.extract_field(name, selector)
        return results
    
    def close(self):
        """Close the Selenium WebDriver if it's open"""
        if self.driver:
            self.driver.quit()
            self.driver = None
