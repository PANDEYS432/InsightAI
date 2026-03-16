from google import genai
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


def generate_response(context, query, api_key=None, sources=None):

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return "Error: GEMINI_API_KEY not found in .env"

    try:

        client = genai.Client(api_key=api_key)

        if context and context.strip():

            source_info = ""

            if sources:
                source_info = "\nSources used:\n"

                for source in sources:

                    source_name = source.get("name", "Unknown")
                    source_type = source.get("type", "document")
                    source_url = source.get("url", "")

                    if source_type == "url":
                        source_info += f"- URL: {source_url}\n"
                    else:
                        source_info += f"- Document: {source_name}\n"

            prompt = f"""
Answer the question using the provided context.

Context:
{context}

Question:
{query}

{source_info}

Instructions:
1. Use only the provided context
2. If the answer is not in the context, say so politely
3. Provide a detailed answer

Answer:
"""

        else:

            prompt = f"""
The user asked:

{query}

But no relevant context was found in the uploaded documents.

Politely inform the user that the question cannot be answered because it is unrelated to the documents.
"""

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt
        )

        return response.text

    except Exception as e:

        logger.error(f"Gemini error: {str(e)}")

        error_str = str(e).lower()

        if "api key" in error_str:
            return "Error: Invalid Gemini API key."

        elif "quota" in error_str:
            return "Error: Gemini API quota exceeded."

        else:
            return "Error: Could not generate response from Gemini."