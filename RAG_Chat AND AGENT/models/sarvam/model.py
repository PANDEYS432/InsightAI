from sarvamai import SarvamAI
import json
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "sarvam-m"


def generate_qa_dataset(context, query=None, num_pairs=5, difficulty="intermediate", api_key=None):

    if not api_key:
        api_key = os.getenv("SARVAM_API_KEY")

    if not api_key:
        raise ValueError("SARVAM_API_KEY not found in .env")

    client = SarvamAI()

    system_message = {
        "role": "system",
        "content": f"You generate exactly {num_pairs} question-answer pairs from the given text. Return JSON only."
    }

    query_instruction = ""
    if query:
        query_instruction = f"\nFocus Topic: {query}"

    user_message = {
        "role": "user",
        "content": f"""
<CONTENT>
{context}
</CONTENT>

{query_instruction}

Return JSON format:

[
  {{
    "question": "Question text here?",
    "answer": "Answer text here."
  }}
]
"""
    }

    try:

        response = client.chat.completions(
            model=DEFAULT_MODEL,
            messages=[system_message, user_message],
            temperature=0.7,
            max_tokens=2048
        )

        content = response.choices[0].message.content

        try:
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            json_str = content[json_start:json_end]
            return json.loads(json_str)

        except:
            return extract_qa_pairs_fallback(content)

    except Exception as e:

        logger.error(f"Sarvam error: {str(e)}")
        raise ValueError(f"Sarvam API error: {str(e)}")


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