import streamlit as st
import openai
import numpy as np
from datetime import datetime
from config import OPENAI_CLIENT

# --- Helper functions for RAG ---

def split_text_into_chunks(text, chunk_size=2000):
    """
    Splits text into chunks using paragraph breaks as boundaries.
    It groups paragraphs until the total length exceeds `chunk_size`.
    Then, it ensures that no chunk exceeds `chunk_size` by further splitting if needed.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if current_chunk:
            candidate = current_chunk + "\n\n" + para
        else:
            candidate = para
        if len(candidate) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = candidate
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size:
            for i in range(0, len(chunk), chunk_size):
                final_chunks.append(chunk[i:i+chunk_size])
        else:
            final_chunks.append(chunk)
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

def retrieve_relevant_context(query, vector_store, top_k=3):
    """
    Given a query and a vector store, compute the query's embedding,
    compare it against each stored chunk, and return the top_k most relevant segments.
    """
    query_embedding = get_embedding(query)
    scored_chunks = []
    for item in vector_store:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored_chunks.append((score, item["text"]))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [chunk for score, chunk in scored_chunks[:top_k]]
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
        context = ""
        if "vector_store" in st.session_state:
            context = retrieve_relevant_context(default_query, st.session_state.vector_store, top_k=5)
            # st.write("Debug: Retrieved context for default query:", context)
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({"role": "system", "content": f"Relevant context:\n{context}"})
        # Use the default query solely for prompt construction.
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
        
        context = ""
        if "vector_store" in st.session_state:
            context = retrieve_relevant_context(user_input, st.session_state.vector_store, top_k=5)
            # st.write("Debug: Retrieved context for user query:", context)
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({"role": "system", "content": f"Relevant context:\n{context}"})
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
