import streamlit as st
import openai
from datetime import datetime
from config import OPENAI_CLIENT

def run_chat():
    # Hidden system prompt; not shown in UI.
    system_prompt = (
        "Act like an experienced marketer and data miner. "
        "Act like an experienced marketer and data miner.  Please provide contact information for senior leadership, including the CEO and the Board of Directors, along with their names, titles, and contact details.  "
    )
    
    # Initialize conversation history if it doesn't exist.
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    st.markdown("### Follow-up Chat")
    
    # Display previous messages using st.chat_message
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        elif msg["role"] == "assistant":
            st.chat_message("assistant").write(msg["content"])
    
    # Accept new user input via st.chat_input.
    user_input = st.chat_input("Ask a follow-up question about the crawled content:")
    if user_input:
        # Append new user message.
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Build full conversation with the hidden system prompt.
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(st.session_state.chat_history)
        
        with st.spinner("Generating response..."):
            response = OPENAI_CLIENT.chat.completions.create(
                model="gpt-3.5-turbo",  # Use your desired model; change to "gpt-4" if needed.
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            assistant_response = response.choices[0].message.content.strip()
            st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})
            st.experimental_rerun()

if __name__ == "__main__":
    run_chat()
