import re

def normalize_text(text):
    if not text:
        return text
    # Remove zero-width spaces and non-breaking spaces
    text = re.sub(r'[\u200B\u00A0]', '', text)
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    # Trim leading and trailing whitespace
    text = text.strip()
    return text
