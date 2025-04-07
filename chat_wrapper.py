# chat_wrapper.py
# This script creates a smart chat tool that helps users dig into a collection of pre-gathered text data (like company info scraped from websites or emails).
# It adapts dynamically to the calling program: for app_wrapper.py, it focuses on leadership info; for email_extractor.py, it analyzes email content including bodies, summaries, and attachments.

import streamlit as st  # Library to build an interactive web app
import openai  # Library to interact with OpenAI's AI models
import json  # Library to handle JSON data (not used here but imported)
import numpy as np  # Library for math operations on arrays (like vectors)
import re  # Library for working with text patterns (not used here but imported)
from datetime import datetime  # Library for handling dates/times (not used here but imported)
from config import OPENAI_CLIENT  # Custom file storing the OpenAI connection setup


# --- Query rewriting utility ---
def expand_query(query: str) -> str:
    """
    Expand the user's query with synonyms or related terms to improve retrieval matching.
    1) For unambiguous acronyms, do a straightforward two-way expansion (if "CEO" found,
       append "Chief Executive Officer", etc.).
    2) For ambiguous acronyms like "CDO" or "CSO", attempt to detect context from the query.
       If context words match a specific meaning, append that full title.
       If multiple expansions match or there's no context, optionally append all expansions.
    This helps align the user's question with how the data might appear in the RAG corpus.
    """
    # Dictionary for simple, clear acronym expansions
    ACRONYM_SINGLE_MAP = {
        "CEO": "Chief Executive Officer",
        "CFO": "Chief Financial Officer",
        "COO": "Chief Operating Officer",
        "CTO": "Chief Technology Officer",
        "CMO": "Chief Marketing Officer",
        "CIO": "Chief Information Officer",
        "CHRO": "Chief Human Resources Officer",
    }

    # Dictionary for acronyms with multiple meanings, paired with clue words
    ACRONYM_AMBIGUOUS_MAP = {
        "CDO": [
            ("Chief Data Officer", ["data", "analytics", "big data", "etl", "database"]),
            ("Chief Diversity Officer", ["diversity", "inclusion", "dei"]),
        ],
        "CSO": [
            ("Chief Strategy Officer", ["strategy", "strategic", "vision", "business plan"]),
            ("Chief Security Officer", ["security", "risk", "cyber", "compliance"]),
            ("Chief Sustainability Officer", ["sustainability", "environment", "green", "CSR", "corporate social responsibility"]),
        ],
        "CRO": [
            ("Chief Revenue Officer", ["revenue", "sales", "growth", "pricing", "market share", "monetization"]),
            ("Chief Risk Officer", ["risk", "compliance", "mitigation", "assurance", "regulatory", "governance"]),
        ]
    }

    expanded_query = query  # Start with the original question
    lower_query = query.lower()  # Convert to lowercase for easier matching

    # Add full titles or acronyms for clear-cut cases (e.g., "CEO")
    for acronym, full_title in ACRONYM_SINGLE_MAP.items():
        if acronym.lower() in lower_query and full_title.lower() not in lower_query:
            expanded_query += f" {full_title}"  # Add full title if acronym is used
        if full_title.lower() in lower_query and acronym.lower() not in lower_query:
            expanded_query += f" {acronym}"  # Add acronym if full title is used

    # Handle trickier acronyms with multiple meanings (e.g., "CSO")
    for acronym, expansions in ACRONYM_AMBIGUOUS_MAP.items():
        if acronym.lower() in lower_query:
            matched_expansions = []
            # Check for clue words to pick the right meaning
            for (title, hint_words) in expansions:
                if any(hint in lower_query for hint in hint_words):
                    matched_expansions.append(title)
            if matched_expansions:
                # Add all matched titles (e.g., if "security" fits "CSO")
                for title in matched_expansions:
                    if title.lower() not in lower_query:
                        expanded_query += f" {title}"
            else:
                # No clues? Add all possible meanings
                for (title, _) in expansions:
                    if title.lower() not in lower_query:
                        expanded_query += f" {title}"
        else:
            # If full title is used, add the acronym too
            for (title, hint_words) in expansions:
                if title.lower() in lower_query and acronym.lower() not in lower_query:
                    expanded_query += f" {acronym}"

    return expanded_query  # Return the beefed-up question


# --- Helper functions for RAG (Retrieval-Augmented Generation) ---
def split_text_into_chunks(text, chunk_size=2000):
    # Break big text into smaller pieces (about 2000 characters each)
    paragraphs = text.split("\n\n")  # Split by blank lines
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if current_chunk:
            candidate = current_chunk + "\n\n" + para  # Try adding paragraph
        else:
            candidate = para
        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())  # Save full chunk
            current_chunk = para  # Start new chunk
        else:
            current_chunk = candidate
    if current_chunk:
        chunks.append(current_chunk.strip())  # Add last chunk
    # Double-check no piece is too long, split further if needed
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= chunk_size:
            final_chunks.append(chunk)
        else:
            start = 0
            while start < len(chunk):
                end = min(start + chunk_size, len(chunk))
                if end < len(chunk):
                    newline_idx = chunk.rfind("\n", start, end)
                    if newline_idx != -1 and newline_idx > start:
                        end = newline_idx  # Cut at a clean break
                final_chunks.append(chunk[start:end].strip())
                start = end
    return final_chunks


def get_embedding(text):
    """
    Turn text into a numerical "fingerprint" (embedding) using OpenAI's AI.
    This helps the computer understand and compare text meanings.
    """
    response = OPENAI_CLIENT.embeddings.create(
        model="text-embedding-ada-002",  # Specific AI model for embeddings
        input=text
    )
    return response.data[0].embedding  # Return the fingerprint


def cosine_similarity(vec1, vec2):
    """
    Measure how similar two text fingerprints are (closer to 1 = more similar).
    """
    vec1 = np.array(vec1)  # Convert to math-friendly format
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2) + 1e-10)  # Math formula for similarity


def build_vector_store(text):
    """
    Break text into chunks and create fingerprints for each one.
    Stores them in a list for quick lookup later.
    """
    chunks = split_text_into_chunks(text, chunk_size=2000)
    vector_store = []
    for chunk in chunks:
        embedding = get_embedding(chunk)  # Get fingerprint
        vector_store.append({"embedding": embedding, "text": chunk})  # Save with text
    return vector_store


def retrieve_relevant_context(query, vector_store, top_k=10, similarity_threshold=0.3):
    """
    Find the most relevant text chunks for a question by comparing fingerprints.
    Returns a big string of the best matches.
    """
    query_embedding = get_embedding(query)  # Fingerprint the question
    scored_chunks = []
    for item in vector_store:
        score = cosine_similarity(query_embedding, item["embedding"])  # Compare to each chunk
        scored_chunks.append((score, item["text"]))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)  # Sort by best match
    filtered_chunks = [(score, text) for (score, text) in scored_chunks if score >= similarity_threshold]  # Drop weak matches
    top_chunks = [text for score, text in filtered_chunks[:top_k]]  # Take top matches
    return "\n".join(top_chunks)  # Combine into one string


# --- Main Chat Function with RAG Integration ---
def run_chat():
    # Dynamically set system_prompt and default_query based on caller context
    context = st.session_state.get("data_context", "leadership")  # Default to leadership
    if context == "email":
        system_prompt = (
            "Act as an assistant analyzing email data. Answer questions about subjects, senders, recipients, dates, bodies, summaries, and attachments. Include attachment content if available, or note they’re recommended for reading."
        )
        default_query = "Provide a summary of the emails, including key senders, subjects, and notable attachments."
        data_key = "email_text"
    else:  # leadership from app_wrapper.py
        system_prompt = (
            "Act like an experienced marketer and data miner and look for information on senior leadership, "
            "like the Founder or Co-Founder, CEO, CFO, other C-level officers, or the Board of Directors, along with their names, titles, and social media or other contact details.  "
            "If senior leadership is not found, get the top 10 team members by title.  Only get information from your RAG and internal data.  Do not search the Internet or any public sources."
        )
        default_query = (
            "Act like an experienced marketer and data miner and look for information on senior leadership, "
            "like the Founder or Co-Founder, CEO, CFO, other C-level officers, or the Board of Directors, along with their names, titles, and social media or other contact details.  "
            "If senior leadership is not found, get the top 10 team members by title.  Only get information from your RAG and internal data.  Do not search the Internet or any public sources."
        )
        data_key = "crawled_text"

    # Set up a place to store chat messages if it’s the first run
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Check if the AI connection is ready
    try:
        # Attempt a lightweight API call to verify client readiness
        OPENAI_CLIENT.models.list()  # This will raise an exception if the client isn't configured
    except Exception as e:
        st.error(f"OPENAI_CLIENT not ready: {str(e)}. Please check config.py or API key setup.")
        # st.write(f"DEBUG: OPENAI_CLIENT attributes: {dir(OPENAI_CLIENT)}")
        # st.write(f"DEBUG: Exception details: {str(e)}")
        return  # Halt execution if the client isn’t usable
    # st.write("DEBUG: OPENAI_CLIENT is ready.")  # Confirm success (remove later)

    # Make sure there’s text data to work with
    if data_key not in st.session_state or not st.session_state[data_key].strip():
        st.error(f"No {context} data available. Please process data first.")
        return

    # Process the text data into chunks and fingerprints if not done yet
    if "vector_store" not in st.session_state:
        with st.spinner(f"Processing {context} data for retrieval..."):  # Show a loading sign
            st.session_state.vector_store = build_vector_store(st.session_state[data_key])

    st.markdown("### Follow-up Chat")  # Add a title to the chat section

    # Show all past messages in the chat
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            st.chat_message("assistant").write(msg["content"])  # Show AI replies
        elif msg["role"] == "user":
            st.chat_message("user").write(msg["content"])  # Show user questions

    # If it’s the first time, answer the default question automatically
    if not st.session_state.chat_history:
        if "vector_store" in st.session_state:
            retrieved_context = retrieve_relevant_context(default_query, st.session_state.vector_store, top_k=10)  # Find relevant text
        else:
            retrieved_context = ""
        system_content = system_prompt
        if retrieved_context:
            system_content += f"\n\nRelevant context:\n{retrieved_context}"  # Add found text to instructions
        messages = [{"role": "system", "content": system_content}]
        messages.append({"role": "user", "content": default_query})  # Pretend user asked the default
        with st.spinner("Generating response..."):
            response = OPENAI_CLIENT.chat.completions.create(
                model="chatgpt-4o-latest",  # Use latest ChatGPT model
                messages=messages,
                temperature=0.7,  # Control creativity (0 = strict, 1 = wild)
                max_tokens=500  # Limit reply length
            )
            assistant_response = response.choices[0].message.content.strip()
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
        st.experimental_rerun()  # Refresh the page to show the reply

    # Let the user type a new question
    user_input = st.chat_input("Ask a follow-up question about the crawled content:")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})  # Save question
        expanded_user_input = expand_query(user_input)  # Add extra terms to the question
        if "vector_store" in st.session_state:
            retrieved_context = retrieve_relevant_context(expanded_user_input, st.session_state.vector_store, top_k=10)  # Find relevant text
        else:
            retrieved_context = ""
        merged_system_content = system_prompt
        if retrieved_context:
            merged_system_content += f"\n\nRelevant context:\n{retrieved_context}"  # Add found text
        messages = [{"role": "system", "content": merged_system_content}]
        messages.extend(st.session_state.chat_history)  # Include past chat
        with st.spinner("Generating response..."):
            response = OPENAI_CLIENT.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            assistant_response = response.choices[0].message.content.strip()
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
        st.experimental_rerun()  # Refresh to show the new reply


if __name__ == "__main__":
    run_chat()  # Start the chat tool