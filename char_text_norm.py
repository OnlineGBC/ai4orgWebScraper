import re

def normalize_text(text):
    if not text:
        return text
    
    # Ensure we're working with a string
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8', errors='ignore')
        except Exception:
            return "Unable to decode text content"
    
    # Remove zero-width spaces and non-breaking spaces
    text = re.sub(r'[\u200B\u00A0]', '', text)
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    # Trim leading and trailing whitespace
    text = text.strip()
    return text
