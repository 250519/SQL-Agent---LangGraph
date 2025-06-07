import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load environment variables (like GROQ_API_KEY)
load_dotenv()

def get_llm(model: str = "llama-3.1-8b-instant") -> ChatGroq:
    """
    Initializes and returns a ChatGroq LLM instance.
    You must have GROQ_API_KEY set in your .env file.
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("Missing GROQ_API_KEY in environment variables.")

    return ChatGroq(model=model)
