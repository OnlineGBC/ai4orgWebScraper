import streamlit as st
import openai
import json
import numpy as np
import re
from datetime import datetime
from config import OPENAI_CLIENT

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

    # Dictionary for unambiguous expansions
    ACRONYM_SINGLE_MAP = {
        "CEO": "Chief Executive Officer",
        "CFO": "Chief Financial Officer",
        "COO": "Chief Operating Officer",
        "CTO": "Chief Technology Officer",
        "CMO": "Chief Marketing Officer",
        "CIO": "Chief Information Officer",
        "CHRO": "Chief Human Resources Officer",
    }

    # Dictionary mapping each ambiguous acronym to possible expansions
    # each with hint words that help us disambiguate
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

    expanded_query = query
    lower_query = query.lower()

    # ---------------- Unambiguous expansions ----------------
    for acronym, full_title in ACRONYM_SINGLE_MAP.items():
        # If acronym is present but the full title is not, add the full title
        if acronym.lower() in lower_query and full_title.lower() not in lower_query:
            expanded_query += f" {full_title}"
        # If the full title is present but not the acronym, add the acronym
        if full_title.lower() in lower_query and acronym.lower() not in lower_query:
            expanded_query += f" {acronym}"

    # ---------------- Ambiguous expansions ----------------
    for acronym, expansions in ACRONYM_AMBIGUOUS_MAP.items():
        # Check if the acronym is present in the query
        if acronym.lower() in lower_query:
            matched_expansions = []
            # For each possible meaning, see if any hint words appear
            for (title, hint_words) in expansions:
                if any(hint in lower_query for hint in hint_words):
                    matched_expansions.append(title)
            if matched_expansions:
                # If we found one or more matches, add them all (some contexts might overlap)
                for title in matched_expansions:
                    if title.lower() not in lower_query:
                        expanded_query += f" {title}"
            else:
                # No disambiguating words found -> optionally add ALL expansions
                for (title, _) in expansions:
                    if title.lower() not in lower_query:
                        expanded_query += f" {title}"
        else:
            # The user didn't explicitly mention the acronym, but maybe spelled out the full title
            for (title, hint_words) in expansions:
                if title.lower() in lower_query and acronym.lower() not in lower_query:
                    expanded_query += f" {acronym}"

    return expanded_query

# --- Helper functions for RAG ---

def split_text_into_chunks(text, chunk_size=2000):
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if current_chunk:
            candidate = current_chunk + "\n\n" + para
        else:
            candidate = para
        if len(candidate) > chunk_size and current_chunk:
            # Current chunk is full; start a new chunk
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = candidate
    if current_chunk:
        chunks.append(current_chunk.strip())
    # Now ensure no chunk exceeds chunk_size by splitting at neat boundaries
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= chunk_size:
            final_chunks.append(chunk)
        else:
            start = 0
            while start < len(chunk):
                # Try to cut at a newline boundary within the next chunk_size characters
                end = min(start + chunk_size, len(chunk))
                if end < len(chunk):
                    newline_idx = chunk.rfind("\n", start, end)
                    if newline_idx != -1 and newline_idx > start:
                        end = newline_idx  # break at the last newline within the limit
                final_chunks.append(chunk[start:end].strip())
                start = end
    return final_chunks

def get_embedding(text):
    """
    Retrieve the embedding for a given text using OpenAI's Embedding API.
    Using model "text-embedding-ada-002" for embeddings.
    """
    response = OPENAI_CLIENT.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def cosine_similarity(vec1, vec2):
    """
    Compute cosine similarity between two vectors.
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2) + 1e-10)

def build_vector_store(text):
    """
    Given a large text, split it into chunks and compute embeddings for each chunk.
    Returns a list of dictionaries with keys "embedding" and "text".
    """
    chunks = split_text_into_chunks(text, chunk_size=2000)
    vector_store = []
    for chunk in chunks:
        embedding = get_embedding(chunk)
        vector_store.append({"embedding": embedding, "text": chunk})
    return vector_store

def retrieve_relevant_context(query, vector_store, top_k=10, similarity_threshold=0.3):
    """
    Given a query and a vector store, compute the query's embedding,
    compare it against each stored chunk, and return the top_k most relevant segments.
    
    :param query: The user query string
    :param vector_store: A list of dicts with "embedding" and "text" keys
    :param top_k: Number of chunks to return after filtering/sorting
    :param similarity_threshold: Chunks below this cosine similarity score are dropped
    :return: A single string concatenating the most relevant chunk texts
    """
    query_embedding = get_embedding(query)
    scored_chunks = []
    
    for item in vector_store:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored_chunks.append((score, item["text"]))

    # Sort chunks by descending similarity
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Filter out low-similarity chunks
    filtered_chunks = [(score, text) for (score, text) in scored_chunks if score >= similarity_threshold]
    
    # Take top_k after filtering
    top_chunks = [text for score, text in filtered_chunks[:top_k]]
    
    return "\n".join(top_chunks)

# --- Main Chat Function with RAG Integration ---

def run_chat():
    # Hidden system prompt; not shown in UI.
    system_prompt = (
        "Act like an experienced marketer and data miner and look for information on senior leadership, "
        "like the Founder or Co-Founder, CEO, CFO, other C-level officers, or the Board of Directors, along with their names, titles, and social media or other contact details.  "
        "If senior leadership is not found, get the top 10 team members by title.  Only get information from your RAG and internal data.  Do not search the Internet or any public sources."
    )
    
    # Default query text used internally if no user input is given.
    default_query = (
        "Act like an experienced marketer and data miner and look for information on senior leadership, "
        "like the Founder or Co-Founder, CEO, CFO, other C-level officers, or the Board of Directors, along with their names, titles, and social media or other contact details.  "
        "If senior leadership is not found, get the top 10 team members by title.  Only get information from your RAG and internal data.  Do not search the Internet or any public sources."
    )
    
    # Initialize conversation history if it doesn't exist.
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    if not getattr(OPENAI_CLIENT, "api_key", None):
        st.error("OPENAI API key is not set in OPENAI_CLIENT.")
    
    # Check that crawled_text exists and is non-empty.
    if "crawled_text" not in st.session_state or not st.session_state.crawled_text.strip():
        st.error("No crawled text data available. Please ensure that the crawled_text variable is populated.")
        return
    
    # Build vector store from crawled_text if not already processed.
    if "vector_store" not in st.session_state:
        with st.spinner("Processing crawled text for retrieval..."):
            st.session_state.vector_store = build_vector_store(st.session_state.crawled_text)
    
    st.markdown("### Follow-up Chat")
    
    # Display chat history.
    for msg in st.session_state.chat_history:
        if msg["role"] == "assistant":
            st.chat_message("assistant").write(msg["content"])
        elif msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
    
    # If no chat history exists (first run), generate an initial response using default_query
    # without adding the default query to the visible chat history.
    if not st.session_state.chat_history:
        # Retrieve context for the default query, if possible

        if "vector_store" in st.session_state:
            retrieved_context = retrieve_relevant_context(default_query, st.session_state.vector_store, top_k=10)
        else:
            retrieved_context = ""
        
        # Merge system prompt and retrieved context into a single system message
        system_content = system_prompt
        if retrieved_context:
            system_content += f"\n\nRelevant context:\n{retrieved_context}"

        # Now build the messages list with a single system message
        messages = []
        messages.append({"role": "system", "content": system_content})
        # Present the default_query as a user question in conversation
        messages.append({"role": "user", "content": default_query})        

        with st.spinner("Generating response..."):
            response = OPENAI_CLIENT.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            assistant_response = response.choices[0].message.content.strip()
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
        st.experimental_rerun()
    
    # Accept new user input via st.chat_input.
    user_input = st.chat_input("Ask a follow-up question about the crawled content:")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # --- Use the expand_query() function to add synonyms ---
        # This ensures the retrieval step sees extra relevant terms.
        expanded_user_input = expand_query(user_input)

        if "vector_store" in st.session_state:
            retrieved_context = retrieve_relevant_context(expanded_user_input, st.session_state.vector_store, top_k=10)
        else:
            retrieved_context = ""
        
        # Build a single system message that merges instructions + context
        merged_system_content = system_prompt
        if retrieved_context:
            merged_system_content += f"\n\nRelevant context:\n{retrieved_context}"
        messages = [ {"role": "system", "content": merged_system_content} ]
        messages.extend(st.session_state.chat_history)
        
        with st.spinner("Generating response..."):
            response = OPENAI_CLIENT.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            assistant_response = response.choices[0].message.content.strip()
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
        st.experimental_rerun()

if __name__ == "__main__":
    run_chat()
