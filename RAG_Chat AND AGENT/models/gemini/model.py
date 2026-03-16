from google import genai
import json
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


def generate_qa_dataset(context, query=None, num_pairs=5, difficulty="intermediate", api_key=None):

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")

    try:

        client = genai.Client(api_key=api_key)

        query_instruction = ""

        if query:
            query_instruction = f"\nFocus Topic: {query}"

        prompt = f"""
Generate exactly {num_pairs} question-answer pairs from the text.

Content:
{context}

{query_instruction}

Return JSON only:

[
  {{
    "question": "Question text",
    "answer": "Answer text"
  }}
]
"""

        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt
        )

        content = response.text

        qa_pairs = parse_response(content)

        if not qa_pairs:
            qa_pairs = extract_qa_pairs_fallback(content)

        return qa_pairs

    except Exception as e:

        logger.error(f"Gemini error: {str(e)}")

        raise ValueError(f"Gemini API error: {str(e)}")


def parse_response(content):

    try:

        json_start = content.find("[")
        json_end = content.rfind("]") + 1

        if json_start >= 0:

            json_str = content[json_start:json_end]

            return json.loads(json_str)

    except:
        return None


def extract_qa_pairs_fallback(text):

    qa_pairs = []

    blocks = re.findall(
        r'Q:(.*?)A:(.*?)(?=Q:|$)',
        text,
        re.DOTALL
    )

    for q, a in blocks:

        qa_pairs.append({
            "question": q.strip(),
            "answer": a.strip()
        })

    return qa_pairs