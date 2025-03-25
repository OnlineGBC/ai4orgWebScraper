import os
import requests
import json
from datetime import datetime
import time

class LinkedInAPI:
    """
    A class to interact with LinkedIn's official API for job searches.
    Uses environment variables for API credentials.
    """
    
    def __init__(self):
        """Initialize the LinkedIn API client with credentials from environment variables."""
        self.client_id = os.environ.get('LINKEDIN_CLIENT_ID')
        self.client_secret = os.environ.get('LINKEDIN_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('LINKEDIN_REDIRECT_URI')
        self.access_token = os.environ.get('LINKEDIN_ACCESS_TOKEN')
        
        self.base_url = "https://api.linkedin.com/v2"
        self.job_search_url = f"{self.base_url}/jobSearch"
        
        # Check if credentials are available
        self.is_configured = self._check_configuration()
        
        # Rate limiting parameters
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_per_minute = 60  # Adjust based on your API tier
        
        # Mock data flag - set to True to use mock responses instead of real API calls
        self.use_mock_data = True
    
    def _check_configuration(self):
        """Check if all required credentials are available."""
        required_vars = ['LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET', 
                         'LINKEDIN_REDIRECT_URI', 'LINKEDIN_ACCESS_TOKEN']
        
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            print(f"Missing environment variables: {', '.join(missing_vars)}")
            return False
        return True
    
    def _handle_rate_limiting(self):
        """Implement rate limiting to avoid exceeding API quotas."""
        current_time = time.time()
        time_diff = current_time - self.last_request_time
        
        # If less than a minute has passed since first request in this minute
        if time_diff < 60 and self.request_count >= self.rate_limit_per_minute:
            # Sleep until a minute has passed
            sleep_time = 60 - time_diff
            print(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            # Reset counter
            self.request_count = 0
            self.last_request_time = time.time()
        
        # If more than a minute has passed, reset counter
        elif time_diff >= 60:
            self.request_count = 0
            self.last_request_time = current_time
        
        # Increment request counter
        self.request_count += 1
    
    def _get_mock_job_search_response(self, keywords=None, location=None, count=25):
        """Generate mock job search response data"""
        current_time = int(time.time() * 1000)  # Current time in milliseconds
        
        # Create mock job listings based on search parameters
        job_listings = []
        for i in range(min(count, 25)):  # Limit to requested count or 25 max
            job_id = f"mock-job-{i+1}"
            job_title = f"{keywords if keywords else 'Software Engineer'} {i+1}"
            company_name = f"Mock Company {(i % 5) + 1}"
            job_location = location if location else "Remote"
            
            job_listing = {
                "id": job_id,
                "title": job_title,
                "companyName": company_name,
                "location": {
                    "name": job_location,
                    "country": "US",
                    "city": job_location.split(",")[0] if "," in job_location else job_location
                },
                "listedAt": current_time - (i * 86400000),  # Subtract days in milliseconds
                "applyUrl": f"https://www.linkedin.com/jobs/view/{job_id}",
                "description": f"This is a mock job description for {job_title} at {company_name}. " +
                              f"The position is located in {job_location} and requires skills in programming, " +
                              f"communication, and problem-solving.",
                "employmentStatus": "FULL_TIME",
                "experienceLevel": "MID_SENIOR",
                "industries": ["Technology", "Software Development"]
            }
            job_listings.append(job_listing)
        
        # Create the mock response structure
        mock_response = {
            "elements": job_listings,
            "paging": {
                "count": len(job_listings),
                "start": 0,
                "total": 250  # Mock total number of results
            },
            "metadata": {
                "searchId": f"mock-search-{int(time.time())}",
                "status": "COMPLETE"
            }
        }
        
        return mock_response
    
    def _get_mock_job_details(self, job_id):
        """Generate mock job details response"""
        job_number = job_id.split("-")[-1] if "-" in job_id else "1"
        current_time = int(time.time() * 1000)  # Current time in milliseconds
        
        # Create detailed mock job data
        mock_job_details = {
            "id": job_id,
            "title": f"Software Engineer {job_number}",
            "companyName": f"Mock Company {int(job_number) % 5 + 1}",
            "location": {
                "name": "San Francisco, CA",
                "country": "US",
                "city": "San Francisco",
                "postalCode": "94105"
            },
            "listedAt": current_time - (int(job_number) * 86400000),
            "applyUrl": f"https://www.linkedin.com/jobs/view/{job_id}",
            "description": f"""<p>Mock Company {int(job_number) % 5 + 1} is seeking a talented Software Engineer to join our team.</p>
            <p><strong>Responsibilities:</strong></p>
            <ul>
                <li>Design and develop high-quality software solutions</li>
                <li>Collaborate with cross-functional teams</li>
                <li>Write clean, scalable code</li>
                <li>Participate in code reviews</li>
                <li>Troubleshoot and debug applications</li>
            </ul>
            <p><strong>Requirements:</strong></p>
            <ul>
                <li>Bachelor's degree in Computer Science or related field</li>
                <li>3+ years of software development experience</li>
                <li>Proficiency in Python, JavaScript, and SQL</li>
                <li>Experience with web frameworks and cloud services</li>
                <li>Strong problem-solving skills</li>
            </ul>
            <p><strong>Benefits:</strong></p>
            <ul>
                <li>Competitive salary</li>
                <li>Health, dental, and vision insurance</li>
                <li>401(k) matching</li>
                <li>Flexible work arrangements</li>
                <li>Professional development opportunities</li>
            </ul>""",
            "employmentStatus": "FULL_TIME",
            "experienceLevel": "MID_SENIOR",
            "industries": ["Technology", "Software Development"],
            "functions": ["Engineering", "Information Technology"],
            "companyDetails": {
                "id": f"mock-company-{int(job_number) % 5 + 1}",
                "name": f"Mock Company {int(job_number) % 5 + 1}",
                "url": f"https://www.linkedin.com/company/mock-company-{int(job_number) % 5 + 1}",
                "logoUrl": "https://media.licdn.com/dms/image/mock_company_logo.png",
                "employeeCount": 500 + (int(job_number) * 100),
                "headquarters": "San Francisco, CA"
            },
            "skills": ["Python", "JavaScript", "SQL", "AWS", "Docker"]
        }
        
        return mock_job_details
    
    def _get_mock_company_details(self, company_id):
        """Generate mock company details response"""
        company_number = company_id.split("-")[-1] if "-" in company_id else "1"
        
        # Create mock company data
        mock_company = {
            "id": company_id,
            "name": f"Mock Company {company_number}",
            "url": f"https://www.linkedin.com/company/{company_id}",
            "description": f"Mock Company {company_number} is a leading technology company specializing in software development, cloud computing, and artificial intelligence solutions.",
            "industry": "Technology",
            "headquartersLocation": {
                "country": "US",
                "city": "San Francisco",
                "state": "CA"
            },
            "foundedYear": 2010 - (int(company_number) % 10),
            "employeeCount": 500 + (int(company_number) * 100),
            "specialties": ["Software Development", "Cloud Computing", "Artificial Intelligence", "Data Analytics"],
            "website": f"https://www.mockcompany{company_number}.com",
            "logoUrl": "https://media.licdn.com/dms/image/mock_company_logo.png"
        }
        
        return mock_company
    
    def _get_mock_user_profile(self):
        """Generate mock user profile response"""
        # Create mock user profile data
        mock_profile = {
            "id": "mock-user-123",
            "firstName": "John",
            "lastName": "Doe",
            "headline": "Software Engineer at Mock Company",
            "location": {
                "country": "US",
                "city": "San Francisco"
            },
            "industry": "Technology",
            "summary": "Experienced software engineer with expertise in web development, cloud computing, and machine learning.",
            "positions": [
                {
                    "title": "Senior Software Engineer",
                    "companyName": "Mock Company 1",
                    "startDate": {
                        "year": 2020,
                        "month": 6
                    },
                    "isCurrent": True
                },
                {
                    "title": "Software Engineer",
                    "companyName": "Mock Company 2",
                    "startDate": {
                        "year": 2018,
                        "month": 3
                    },
                    "endDate": {
                        "year": 2020,
                        "month": 5
                    },
                    "isCurrent": False
                }
            ],
            "skills": ["Python", "JavaScript", "React", "Node.js", "AWS", "Docker", "Machine Learning"]
        }
        
        return mock_profile
    
    def _make_request(self, endpoint, params=None, method="GET"):
        """Make a request to the LinkedIn API with rate limiting."""
        if not self.is_configured:
            return {
                "success": False,
                "message": "LinkedIn API not configured. Please set environment variables.",
                "data": None
            }
        
        # Use mock data if enabled
        if self.use_mock_data:
            # Determine which mock response to return based on the endpoint
            if endpoint == "jobSearch":
                mock_data = self._get_mock_job_search_response(
                    keywords=params.get("keywords") if params else None,
                    location=params.get("location") if params else None,
                    count=params.get("count", 25) if params else 25
                )
                return {
                    "success": True,
                    "message": "Request successful (mock data)",
                    "data": mock_data
                }
            elif endpoint.startswith("jobs/"):
                job_id = endpoint.split("/")[1]
                mock_data = self._get_mock_job_details(job_id)
                return {
                    "success": True,
                    "message": "Request successful (mock data)",
                    "data": mock_data
                }
            elif endpoint.startswith("organizations/"):
                company_id = endpoint.split("/")[1]
                mock_data = self._get_mock_company_details(company_id)
                return {
                    "success": True,
                    "message": "Request successful (mock data)",
                    "data": mock_data
                }
            elif endpoint == "me":
                mock_data = self._get_mock_user_profile()
                return {
                    "success": True,
                    "message": "Request successful (mock data)",
                    "data": mock_data
                }
            elif endpoint == "jobRecommendations":
                # Return mock job recommendations (similar to job search)
                mock_data = self._get_mock_job_search_response(
                    keywords="recommended",
                    count=params.get("count", 25) if params else 25
                )
                return {
                    "success": True,
                    "message": "Request successful (mock data)",
                    "data": mock_data
                }
            elif endpoint == "jobSaves":
                if method == "POST":
                    # Mock saving a job
                    return {
                        "success": True,
                        "message": "Job saved successfully (mock data)",
                        "data": {"id": params.get("jobId"), "saved": True}
                    }
                else:
                    # Mock getting saved jobs
                    mock_data = self._get_mock_job_search_response(
                        keywords="saved",
                        count=params.get("count", 25) if params else 25
                    )
                    return {
                        "success": True,
                        "message": "Request successful (mock data)",
                        "data": mock_data
                    }
            else:
                # Generic mock response for other endpoints
                return {
                    "success": True,
                    "message": f"Request successful for endpoint {endpoint} (mock data)",
                    "data": {"message": "This is mock data for an unspecified endpoint"}
                }
        
        # If not using mock data, proceed with actual API request
        # Handle rate limiting
        self._handle_rate_limiting()
        
        # Prepare headers with access token
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params)
            else:
                return {
                    "success": False,
                    "message": f"Unsupported method: {method}",
                    "data": None
                }
            
            # Check for successful response
            response.raise_for_status()
            
            return {
                "success": True,
                "message": "Request successful",
                "data": response.json()
            }
        
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_message = f"HTTP Error: {status_code}"
            
            # Handle specific error codes
            if status_code == 401:
                error_message = "Authentication failed. Please check your access token."
            elif status_code == 403:
                error_message = "Permission denied. Your API key may not have access to this endpoint."
            elif status_code == 429:
                error_message = "Rate limit exceeded. Please try again later."
            
            return {
                "success": False,
                "message": error_message,
                "data": None
            }
        
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Request failed: {str(e)}",
                "data": None
            }
        
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "Failed to parse response JSON",
                "data": None
            }
    
    def search_jobs(self, keywords=None, location=None, job_titles=None, 
                   company_names=None, experience_levels=None, job_types=None,
                   industries=None, distance=None, sort_by="RELEVANCE", 
                   start=0, count=25):
        """
        Search for jobs using LinkedIn's Job Search API.
        
        Parameters:
        - keywords: Search keywords
        - location: Location name or ID
        - job_titles: List of job titles to filter by
        - company_names: List of company names to filter by
        - experience_levels: List of experience levels (ENTRY_LEVEL, MID_SENIOR, etc.)
        - job_types: List of job types (FULL_TIME, PART_TIME, CONTRACT, etc.)
        - industries: List of industry IDs
        - distance: Distance in miles from location
        - sort_by: How to sort results (RELEVANCE, RECENT)
        - start: Starting index for pagination
        - count: Number of results to return (max 100)
        
        Returns:
        - Dictionary with search results
        """
        # Build query parameters
        params = {
            "start": start,
            "count": min(count, 100),  # LinkedIn API typically limits to 100 per request
            "sortBy": sort_by
        }
        
        # Add optional parameters if provided
        if keywords:
            params["keywords"] = keywords
        
        if location:
            params["location"] = location
        
        if job_titles and isinstance(job_titles, list):
            params["jobTitles"] = ",".join(job_titles)
        
        if company_names and isinstance(company_names, list):
            params["companyNames"] = ",".join(company_names)
        
        if experience_levels and isinstance(experience_levels, list):
            params["experienceLevels"] = ",".join(experience_levels)
        
        if job_types and isinstance(job_types, list):
            params["jobTypes"] = ",".join(job_types)
        
        if industries and isinstance(industries, list):
            params["industries"] = ",".join(industries)
        
        if distance:
            params["distance"] = distance
        
        # Make the API request
        return self._make_request("jobSearch", params=params)
    
    def get_job_details(self, job_id):
        """
        Get detailed information about a specific job posting.
        
        Parameters:
        - job_id: LinkedIn job ID
        
        Returns:
        - Dictionary with job details
        """
        return self._make_request(f"jobs/{job_id}")
    
    def get_company_details(self, company_id):
        """
        Get detailed information about a company.
        
        Parameters:
        - company_id: LinkedIn company ID
        
        Returns:
        - Dictionary with company details
        """
        return self._make_request(f"organizations/{company_id}")
    
    def get_recommended_jobs(self, job_titles=None, skills=None, 
                            industries=None, location=None, count=25):
        """
        Get job recommendations based on provided criteria.
        
        Parameters:
        - job_titles: List of job titles
        - skills: List of skills
        - industries: List of industry IDs
        - location: Location name or ID
        - count: Number of recommendations to return
        
        Returns:
        - Dictionary with recommended jobs
        """
        params = {
            "count": min(count, 100)
        }
        
        # Add optional parameters if provided
        if job_titles and isinstance(job_titles, list):
            params["jobTitles"] = ",".join(job_titles)
        
        if skills and isinstance(skills, list):
            params["skills"] = ",".join(skills)
        
        if industries and isinstance(industries, list):
            params["industries"] = ",".join(industries)
        
        if location:
            params["location"] = location
        
        return self._make_request("jobRecommendations", params=params)
    
    def save_job(self, job_id):
        """
        Save a job to the user's saved jobs list.
        
        Parameters:
        - job_id: LinkedIn job ID
        
        Returns:
        - Dictionary with result of save operation
        """
        params = {
            "jobId": job_id
        }
        
        return self._make_request("jobSaves", params=params, method="POST")
    
    def get_saved_jobs(self, start=0, count=25):
        """
        Get the user's saved jobs.
        
        Parameters:
        - start: Starting index for pagination
        - count: Number of results to return
        
        Returns:
        - Dictionary with saved jobs
        """
        params = {
            "start": start,
            "count": min(count, 100)
        }
        
        return self._make_request("jobSaves", params=params)
    
    def check_api_status(self):
        """
        Check if the LinkedIn API is properly configured and accessible.
        
        Returns:
        - Dictionary with API status information
        """
        if not self.is_configured:
            return {
                "success": False,
                "message": "LinkedIn API not configured. Please set environment variables.",
                "data": {
                    "missing_vars": [var for var in ['LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET', 
                                                    'LINKEDIN_REDIRECT_URI', 'LINKEDIN_ACCESS_TOKEN'] 
                                    if not os.environ.get(var)]
                }
            }
        
        # Make a simple request to check if the API is accessible
        test_response = self._make_request("me")
        
        if test_response["success"]:
            return {
                "success": True,
                "message": "LinkedIn API is properly configured and accessible.",
                "data": {
                    "api_version": "v2",
                    "rate_limit": self.rate_limit_per_minute,
                    "credentials_configured": True,
                    "using_mock_data": self.use_mock_data
                }
            }
        else:
            return {
                "success": False,
                "message": f"LinkedIn API is configured but not accessible: {test_response['message']}",
                "data": {
                    "credentials_configured": True,
                    "error": test_response['message'],
                    "using_mock_data": self.use_mock_data
                }
            }

# Example usage
if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["LINKEDIN_CLIENT_ID"] = "your_client_id"
    os.environ["LINKEDIN_CLIENT_SECRET"] = "your_client_secret"
    os.environ["LINKEDIN_REDIRECT_URI"] = "your_redirect_uri"
    os.environ["LINKEDIN_ACCESS_TOKEN"] = "your_access_token"
    
    # Initialize the API client
    linkedin_api = LinkedInAPI()
    
    # Check API status
    status = linkedin_api.check_api_status()
    print(f"API Status: {status['message']}")
    
    # Search for jobs
    if status["success"]:
        job_search = linkedin_api.search_jobs(
            keywords="Python Developer",
            location="San Francisco",
            experience_levels=["ENTRY_LEVEL", "MID_SENIOR"],
            job_types=["FULL_TIME"],
            count=10
        )
        
        if job_search["success"]:
            jobs = job_search["data"]["elements"]
            print(f"Found {len(jobs)} jobs:")
            for job in jobs:
                print(f"- {job['title']} at {job['companyName']}")
        else:
            print(f"Job search failed: {job_search['message']}")
