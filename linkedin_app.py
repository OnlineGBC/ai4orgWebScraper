import streamlit as st
import os
import pandas as pd
import json
import plotly.express as px
from linkedin_api import LinkedInAPI
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="LinkedIn Job Search",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize LinkedIn API client
@st.cache_resource
def get_linkedin_api():
    return LinkedInAPI()

# Function to set environment variables
def set_linkedin_credentials(client_id, client_secret, redirect_uri, access_token):
    os.environ["LINKEDIN_CLIENT_ID"] = client_id
    os.environ["LINKEDIN_CLIENT_SECRET"] = client_secret
    os.environ["LINKEDIN_REDIRECT_URI"] = redirect_uri
    os.environ["LINKEDIN_ACCESS_TOKEN"] = access_token
    return True

# Initialize session state variables
if 'linkedin_configured' not in st.session_state:
    st.session_state.linkedin_configured = False
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'selected_job' not in st.session_state:
    st.session_state.selected_job = None
if 'saved_searches' not in st.session_state:
    st.session_state.saved_searches = []

# Main title
st.title("💼 LinkedIn Job Search")
st.markdown("Search for jobs using LinkedIn's official API")

# Sidebar for configuration and search parameters
with st.sidebar:
    st.header("LinkedIn API Configuration")
    
    # Check if credentials are already configured
    if not st.session_state.linkedin_configured:
        with st.form("linkedin_credentials_form"):
            st.markdown("Enter your LinkedIn API credentials:")
            client_id = st.text_input("Client ID", type="password")
            client_secret = st.text_input("Client Secret", type="password")
            redirect_uri = st.text_input("Redirect URI", value="http://localhost:8501/")
            access_token = st.text_input("Access Token", type="password")
            
            submit_button = st.form_submit_button("Save Credentials")
            
            if submit_button:
                if client_id and client_secret and redirect_uri and access_token:
                    set_linkedin_credentials(client_id, client_secret, redirect_uri, access_token)
                    st.session_state.linkedin_configured = True
                    st.success("LinkedIn API credentials saved!")
                    st.rerun()
                else:
                    st.error("Please fill in all credential fields")
    else:
        st.success("LinkedIn API credentials configured")
        if st.button("Reset Credentials"):
            st.session_state.linkedin_configured = False
            st.rerun()
    
    # Search parameters (only shown if credentials are configured)
    if st.session_state.linkedin_configured:
        st.header("Job Search Parameters")
        
        with st.form("job_search_form"):
            keywords = st.text_input("Keywords", placeholder="e.g., Python Developer")
            
            location = st.text_input("Location", placeholder="e.g., San Francisco")
            
            job_titles = st.text_input("Job Titles (comma separated)", 
                                      placeholder="e.g., Software Engineer, Developer")
            
            company_names = st.text_input("Companies (comma separated)", 
                                         placeholder="e.g., Google, Microsoft")
            
            experience_levels = st.multiselect(
                "Experience Level",
                options=["INTERNSHIP", "ENTRY_LEVEL", "ASSOCIATE", "MID_SENIOR", "DIRECTOR", "EXECUTIVE"],
                default=["ENTRY_LEVEL", "MID_SENIOR"]
            )
            
            job_types = st.multiselect(
                "Job Type",
                options=["FULL_TIME", "PART_TIME", "CONTRACT", "TEMPORARY", "VOLUNTEER", "INTERNSHIP"],
                default=["FULL_TIME"]
            )
            
            industries = st.text_input("Industries (comma separated)", 
                                      placeholder="e.g., Technology, Finance")
            
            distance = st.slider("Distance (miles)", 0, 100, 25)
            
            sort_by = st.selectbox(
                "Sort By",
                options=["RELEVANCE", "RECENT"],
                index=0
            )
            
            count = st.slider("Number of Results", 10, 100, 25)
            
            search_button = st.form_submit_button("Search Jobs")
            
            if search_button:
                linkedin_api = get_linkedin_api()
                
                # Process inputs
                job_titles_list = [title.strip() for title in job_titles.split(",")] if job_titles else None
                company_names_list = [company.strip() for company in company_names.split(",")] if company_names else None
                industries_list = [industry.strip() for industry in industries.split(",")] if industries else None
                
                with st.spinner("Searching for jobs..."):
                    search_results = linkedin_api.search_jobs(
                        keywords=keywords,
                        location=location,
                        job_titles=job_titles_list,
                        company_names=company_names_list,
                        experience_levels=experience_levels if experience_levels else None,
                        job_types=job_types if job_types else None,
                        industries=industries_list,
                        distance=distance,
                        sort_by=sort_by,
                        count=count
                    )
                    
                    if search_results["success"]:
                        st.session_state.search_results = search_results["data"]
                        
                        # Save this search for later reference
                        search_params = {
                            "keywords": keywords,
                            "location": location,
                            "job_titles": job_titles,
                            "company_names": company_names,
                            "experience_levels": experience_levels,
                            "job_types": job_types,
                            "industries": industries,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state.saved_searches.append(search_params)
                        
                        st.success(f"Found {len(search_results['data'].get('elements', []))} jobs!")
                    else:
                        st.error(f"Search failed: {search_results['message']}")

# Main content area
if st.session_state.linkedin_configured:
    # Check API status
    linkedin_api = get_linkedin_api()
    api_status = linkedin_api.check_api_status()
    
    if not api_status["success"]:
        st.error(f"LinkedIn API Error: {api_status['message']}")
        st.info("Please check your API credentials and try again.")
    else:
        # Create tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["Search Results", "Job Details", "Saved Searches", "API Status"])
        
        # Tab 1: Search Results
        with tab1:
            if st.session_state.search_results:
                jobs = st.session_state.search_results.get("elements", [])
                
                if not jobs:
                    st.info("No jobs found matching your criteria. Try broadening your search.")
                else:
                    st.subheader(f"Found {len(jobs)} Jobs")
                    
                    # Create a DataFrame for better display
                    job_data = []
                    for job in jobs:
                        job_data.append({
                            "Job ID": job.get("id", "N/A"),
                            "Title": job.get("title", "N/A"),
                            "Company": job.get("companyName", "N/A"),
                            "Location": job.get("location", {}).get("name", "N/A"),
                            "Listed Date": job.get("listedAt", "N/A"),
                            "Apply URL": job.get("applyUrl", "N/A")
                        })
                    
                    job_df = pd.DataFrame(job_data)
                    
                    # Add a column with buttons to view details
                    st.dataframe(job_df)
                    
                    # Allow selecting a job to view details
                    selected_job_id = st.selectbox(
                        "Select a job to view details",
                        options=job_df["Job ID"].tolist(),
                        format_func=lambda x: f"{job_df[job_df['Job ID']==x]['Title'].iloc[0]} at {job_df[job_df['Job ID']==x]['Company'].iloc[0]}"
                    )
                    
                    if st.button("View Job Details"):
                        with st.spinner("Fetching job details..."):
                            job_details = linkedin_api.get_job_details(selected_job_id)
                            if job_details["success"]:
                                st.session_state.selected_job = job_details["data"]
                                # Switch to the Job Details tab
                                tab2.active = True
                            else:
                                st.error(f"Failed to fetch job details: {job_details['message']}")
                    
                    # Export options
                    st.subheader("Export Results")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # CSV export
                        csv_data = job_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv_data,
                            file_name=f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    
                    with col2:
                        # JSON export
                        json_data = json.dumps(jobs, indent=2)
                        st.download_button(
                            label="Download JSON",
                            data=json_data,
                            file_name=f"linkedin_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
            else:
                st.info("Use the sidebar to search for jobs on LinkedIn")
        
        # Tab 2: Job Details
        with tab2:
            if st.session_state.selected_job:
                job = st.session_state.selected_job
                
                # Display job details
                st.title(job.get("title", "No Title"))
                st.subheader(job.get("companyName", "Unknown Company"))
                st.write(f"📍 {job.get('location', {}).get('name', 'No Location')}")
                
                # Job type and level
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"💼 {job.get('employmentType', 'Not specified')}")
                with col2:
                    st.write(f"🔼 {job.get('seniorityLevel', 'Not specified')}")
                
                # Description
                st.subheader("Job Description")
                description = job.get("description", "No description available")
                st.markdown(description)
                
                # Apply button
                apply_url = job.get("applyUrl")
                if apply_url:
                    st.link_button("Apply for this job", apply_url)
                
                # Save job button
                if st.button("Save Job"):
                    with st.spinner("Saving job..."):
                        save_result = linkedin_api.save_job(job.get("id"))
                        if save_result["success"]:
                            st.success("Job saved successfully!")
                        else:
                            st.error(f"Failed to save job: {save_result['message']}")
            else:
                st.info("Select a job from the Search Results tab to view details")
        
        # Tab 3: Saved Searches
        with tab3:
            if st.session_state.saved_searches:
                st.subheader("Your Saved Searches")
                
                for i, search in enumerate(st.session_state.saved_searches):
                    with st.expander(f"Search {i+1}: {search['keywords']} in {search['location']} ({search['timestamp']})"):
                        st.write(f"**Keywords:** {search['keywords']}")
                        st.write(f"**Location:** {search['location']}")
                        st.write(f"**Job Titles:** {search['job_titles']}")
                        st.write(f"**Companies:** {search['company_names']}")
                        st.write(f"**Experience Levels:** {', '.join(search['experience_levels'])}")
                        st.write(f"**Job Types:** {', '.join(search['job_types'])}")
                        st.write(f"**Industries:** {search['industries']}")
                        
                        # Button to rerun this search
                        if st.button(f"Rerun Search {i+1}"):
                            # Set form values and trigger search
                            # Note: This is a placeholder as Streamlit doesn't allow direct form manipulation
                            st.info("To rerun this search, please copy the parameters to the search form in the sidebar.")
            else:
                st.info("Your saved searches will appear here")
        
        # Tab 4: API Status
        with tab4:
            st.subheader("LinkedIn API Status")
            
            st.json(api_status)
            
            st.subheader("Rate Limiting Information")
            st.write("LinkedIn API has rate limits that restrict the number of requests you can make in a given time period.")
            st.write(f"Current rate limit: {linkedin_api.rate_limit_per_minute} requests per minute")
            
            # Display current environment variables (masked)
            st.subheader("Current Configuration")
            st.write("Client ID: " + "*" * 8)
            st.write("Client Secret: " + "*" * 8)
            st.write("Redirect URI: " + os.environ.get("LINKEDIN_REDIRECT_URI", "Not set"))
            st.write("Access Token: " + "*" * 8)
else:
    st.info("Please configure your LinkedIn API credentials in the sidebar to start searching for jobs.")
    
    st.markdown("""
    ## How to Get LinkedIn API Credentials
    
    1. Go to the [LinkedIn Developer Portal](https://developer.linkedin.com/)
    2. Create a new app or use an existing one
    3. Request access to the necessary APIs (Jobs, Search, etc.)
    4. Generate an access token with the required scopes
    5. Enter your credentials in the sidebar form
    
    For more information, see the [LinkedIn API Documentation](https://developer.linkedin.com/docs).
    """)

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • LinkedIn API Integration • Job Search Tool")
