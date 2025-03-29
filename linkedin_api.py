import os
import httpx
import json
from datetime import datetime
import time

class LinkedInAPI:
    """
    A class to interact with LinkedIn's official API for job searches.
    Uses environment variables for API credentials.
    """
    
    def __init__(self):
        self.client_id = os.environ.get('LINKEDIN_CLIENT_ID')
        self.client_secret = os.environ.get('LINKEDIN_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('LINKEDIN_REDIRECT_URI')
        self.access_token = os.environ.get('LINKEDIN_ACCESS_TOKEN')
        
        self.base_url = "https://api.linkedin.com/v2"
        self.job_search_url = f"{self.base_url}/jobSearch"
        
        self.is_configured = self._check_configuration()
        
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_per_minute = 60
        
        self.use_mock_data = True
        self.session = httpx.Client()  # Using httpx for synchronous requests
    
    def _check_configuration(self):
        required_vars = ['LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET', 
                         'LINKEDIN_REDIRECT_URI', 'LINKEDIN_ACCESS_TOKEN']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            print(f"Missing environment variables: {', '.join(missing_vars)}")
            return False
        return True
    
    def _handle_rate_limiting(self):
        current_time = time.time()
        time_diff = current_time - self.last_request_time
        if time_diff < 60 and self.request_count >= self.rate_limit_per_minute:
            sleep_time = 60 - time_diff
            print(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            self.request_count = 0
            self.last_request_time = time.time()
        elif time_diff >= 60:
            self.request_count = 0
            self.last_request_time = current_time
        self.request_count += 1
    
    def _get_mock_job_search_response(self, keywords=None, location=None, count=25):
        current_time = int(time.time() * 1000)
        job_listings = []
        for i in range(min(count, 25)):
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
                "listedAt": current_time - (i * 86400000),
                "applyUrl": f"https://www.linkedin.com/jobs/view/{job_id}",
                "description": f"This is a mock job description for {job_title} at {company_name}. " +
                               f"The position is located in {job_location} and requires skills in programming, " +
                               f"communication, and problem-solving.",
                "employmentStatus": "FULL_TIME",
                "experienceLevel": "MID_SENIOR",
                "industries": ["Technology", "Software Development"]
            }
            job_listings.append(job_listing)
        mock_response = {
            "elements": job_listings,
            "paging": {
                "count": len(job_listings),
                "start": 0,
                "total": 250
            },
            "metadata": {
                "searchId": f"mock-search-{int(time.time())}",
                "status": "COMPLETE"
            }
        }
        return mock_response
    
    def _get_mock_job_details(self, job_id):
        job_number = job_id.split("-")[-1] if "-" in job_id else "1"
        current_time = int(time.time() * 1000)
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
        company_number = company_id.split("-")[-1] if "-" in company_id else "1"
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
        if not self.is_configured:
            return {
                "success": False,
                "message": "LinkedIn API not configured. Please set environment variables.",
                "data": None
            }
        if self.use_mock_data:
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
                if method.upper() == "POST":
                    return {
                        "success": True,
                        "message": "Job saved successfully (mock data)",
                        "data": {"id": params.get("jobId"), "saved": True}
                    }
                else:
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
                return {
                    "success": True,
                    "message": f"Request successful for endpoint {endpoint} (mock data)",
                    "data": {"message": "This is mock data for an unspecified endpoint"}
                }
        
        self._handle_rate_limiting()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        try:
            url = f"{self.base_url}/{endpoint}"
            if method.upper() == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, json=params, headers=headers, timeout=10)
            else:
                response = self.session.request(method.upper(), url, json=params, headers=headers, timeout=10)
            response.raise_for_status()
            return {
                "success": True,
                "message": "Request successful",
                "data": response.json()
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Request error: {str(e)}",
                "data": None
            }
    
    def search_jobs(self, **kwargs):
        if self.use_mock_data:
            return {
                "success": True,
                "message": "Mock search jobs successful",
                "data": self._get_mock_job_search_response(**kwargs)
            }
        return self._make_request("jobSearch", params=kwargs, method="GET")
    
    def get_job_details(self, job_id):
        if self.use_mock_data:
            return {
                "success": True,
                "message": "Mock job details successful",
                "data": self._get_mock_job_details(job_id)
            }
        return self._make_request(f"jobs/{job_id}", method="GET")
    
    def check_api_status(self):
        if not self.is_configured:
            return {"success": False, "message": "LinkedIn API not configured."}
        try:
            response = self.session.get(f"{self.base_url}/me", timeout=10)
            if response.status_code == 200:
                return {"success": True, "message": "API is operational."}
            else:
                return {"success": False, "message": f"API returned status code {response.status_code}."}
        except Exception as e:
            return {"success": False, "message": f"API check error: {str(e)}"}
