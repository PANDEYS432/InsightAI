from sarvamai import SarvamAI
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sarvam-m"


def generate_response(context, query, api_key=None, sources=None):

    if not api_key:
        api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        return "Error: SARVAM_API_KEY not found in .env"

    try:

        client = SarvamAI()

        if context and context.strip():

            source_info = ""
            if sources:
                source_info = "\nSources used:\n"
                for source in sources:
                    source_name = source.get('name', 'Unknown')
                    source_type = source.get('type', 'document')
                    source_url = source.get('url', '')

                    if source_type == "url":
                        source_info += f"- URL: {source_url}\n"
                    else:
                        source_info += f"- Document: {source_name}\n"

            system_prompt = f"""
Answer the question using the provided context.

Context:
{context}

Question:
{query}

{source_info}

Instructions:
1. Use only the provided context.
2. If answer not in context, say so politely.

Answer:
"""

        else:

            system_prompt = """
No relevant context found for the user's question.
Inform the user politely.
"""

        response = client.chat.completions(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.7,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:

        logger.error(f"Sarvam error: {str(e)}")

        error_str = str(e).lower()

        if "api key" in error_str:
            return "Error: Invalid SARVAM API key."

        elif "rate limit" in error_str:
            return "Error: Sarvam API rate limit exceeded."

        else:
            return "Error: Could not generate response from Sarvam."