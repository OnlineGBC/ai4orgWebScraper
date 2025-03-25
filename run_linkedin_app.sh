#!/bin/bash

# Script to run the LinkedIn Job Search application
# This script sets up environment variables from a .env file if it exists

# Check if .env file exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    echo "No .env file found. Please set LinkedIn API credentials manually or create a .env file."
    echo "Creating sample .env file..."
    cat > .env << EOL
# LinkedIn API Credentials
# Replace these values with your actual credentials
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=http://aienterpriseagent.onlinegbc.com:8601/
LINKEDIN_ACCESS_TOKEN=


EOL
    echo "Sample .env file created. Please edit it with your actual credentials."
fi

# Run the Streamlit app
echo "Starting LinkedIn Job Search application..."
streamlit run linkedin_app.py
