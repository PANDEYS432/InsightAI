import requests
import json
import logging
import time
from requests.exceptions import Timeout, ConnectionError
import re
from pydantic import BaseModel, RootModel
from typing import List
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3")
MAX_RETRIES = 3
TIMEOUT = 180  # 3 minutes timeout

# Define Pydantic model for QA pairs validation
class QAPair(BaseModel):
    question: str
    answer: str

# Use RootModel instead of __root__ field
class QAList(RootModel):
    root: List[QAPair]

def generate_qa_dataset(context, query=None, num_pairs=10, difficulty="intermediate", api_key=None):
    """
    Generate QA pairs using the Ollama local API with robust JSON validation.
    
    Args:
        context (str): The source text to generate questions from
        query (str, optional): Custom query to include in generation
        num_pairs (int): Number of QA pairs to generate
        difficulty (str): Difficulty level ('basic', 'intermediate', 'advanced')
        
    Returns:
        list: List of dictionaries containing question, answer pairs
    """
    # Construct appropriate system prompt based on difficulty
    if difficulty == "basic":
        level_description = "simple factual questions that can be directly answered from the text"
    elif difficulty == "advanced":
        level_description = "complex analytical questions requiring synthesis of multiple concepts and inferential reasoning"
    else:  # intermediate
        level_description = "moderately complex questions requiring understanding connections between concepts"
    
    # Build the prompt - using a clear separation between instruction and expected output
    # Enhanced to be more explicit about exact number requirement
    prompt = f"""<INSTRUCTIONS>
You are generating EXACTLY {num_pairs} question-answer pairs based on the provided content.
You MUST generate EXACTLY {num_pairs} question-answer pairs - not more, not less.
The questions should be {difficulty} level ({level_description}).
Each question must be based only on information in the provided content.
Each pair MUST have both a question and an answer.

{query if query else ""}
</INSTRUCTIONS>

<CONTENT>
        {context}
</CONTENT>

<OUTPUT_FORMAT>
Return a JSON array with EXACTLY {num_pairs} question-answer pairs like this:
[
  {{
    "question": "First question here?",
    "answer": "First answer here."
  }},
  // Continue until you have EXACTLY {num_pairs} pairs
]
COUNT your pairs to ensure you generate EXACTLY {num_pairs}.
DO NOT include the instructions or any explanatory text in your response.
</OUTPUT_FORMAT>"""
    
    # Prepare the request payload
    payload = {
        "model": MODEL_NAME,  # Default model, could be parameterized
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 2048  # Increased for longer QA generation
    }
    
    # Add retry logic with JSON validation feedback loop
    retries = 0
    last_error = None
    last_response_text = None
    
    while retries < MAX_RETRIES:
        try:
            # If we have a previous failed response and error, create a fixing prompt
            if retries > 0 and last_response_text and last_error:
                # Create a JSON fixing prompt
                fixing_prompt = f"""<INSTRUCTIONS>
You are fixing invalid JSON output for question-answer pairs.
You must return a valid JSON array with EXACTLY {num_pairs} question-answer pairs.
Count carefully to ensure you have EXACTLY {num_pairs} pairs.
</INSTRUCTIONS>

<CONTENT>
{context}
</CONTENT>

<INVALID_JSON>
{last_response_text}
</INVALID_JSON>

<ERROR>
{str(last_error)}
</ERROR>

<OUTPUT_FORMAT>
Return a fixed JSON array with EXACTLY {num_pairs} question-answer pairs like this:
[
  {{
    "question": "First question here?",
    "answer": "First answer here."
  }},
  // Continue until you have EXACTLY {num_pairs} pairs
]
DO NOT include any explanations or text outside the JSON array.
</OUTPUT_FORMAT>"""
                payload["prompt"] = fixing_prompt
            
            # Send the request to Ollama
            logger.info(f"Sending QA generation request to Ollama (attempt {retries+1}/{MAX_RETRIES})")
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT)
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "")
                last_response_text = response_text
                
                # Extract the JSON part from the response
                try:
                    # First, try to find JSON in code blocks (```json ... ```)
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                    if json_match:
                        json_str = json_match.group(1).strip()
                        # Handle potential extra markdown formatting
                        json_str = json_str.replace('\\n', '\n').replace('\\"', '"')
                        qa_pairs = json.loads(json_str)
                    else:
                        # Next, try to extract just the JSON array 
                        json_start = response_text.find('[')
                        json_end = response_text.rfind(']') + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            
                            # Clean up potential issues in the JSON string
                            json_str = re.sub(r'^```.*?\n', '', json_str)
                            json_str = re.sub(r'\n```$', '', json_str)
                            
                            qa_pairs = json.loads(json_str)
                        else:
                            raise ValueError("Could not find JSON array in response")
                    
                    # Validate the structure with Pydantic - updated to use RootModel
                    validated_qa_pairs = QAList.model_validate(qa_pairs).root
                    validated_qa_pairs = [qa_pair.model_dump() for qa_pair in validated_qa_pairs]
                    
                    # Check if we have exactly the requested number of pairs
                    if len(validated_qa_pairs) == num_pairs:
                        return validated_qa_pairs
                    elif len(validated_qa_pairs) > num_pairs:
                        # If we have too many, trim the excess
                        logger.info(f"Trimming excess QA pairs: {len(validated_qa_pairs)} → {num_pairs}")
                        return validated_qa_pairs[:num_pairs]
                    else:
                        # If we have too few, generate additional pairs
                        logger.warning(f"Not enough QA pairs: got {len(validated_qa_pairs)}/{num_pairs}")
                        if retries == MAX_RETRIES - 1:  # On last retry, fill in missing pairs
                            return fill_missing_pairs(validated_qa_pairs, context, num_pairs, difficulty)
                        else:
                            # Try again with remaining retries
                            raise ValueError(f"Only got {len(validated_qa_pairs)}/{num_pairs} QA pairs")
                    
                except (json.JSONDecodeError, ValueError, Exception) as e:
                    last_error = e
                    logger.warning(f"Error parsing JSON (attempt {retries+1}): {str(e)}")
                    
                    # Try fallback parser first
                    qa_pairs = parse_qa_pairs_fallback(response_text)
                    if qa_pairs and len(qa_pairs) >= num_pairs:
                        logger.info(f"Extracted {len(qa_pairs)} QA pairs using fallback parser")
                        return qa_pairs[:num_pairs]  # Trim to exact number needed
                    elif qa_pairs:
                        # If last retry, fill missing pairs
                        if retries == MAX_RETRIES - 1:
                            logger.warning(f"Fallback parser found {len(qa_pairs)}/{num_pairs} QA pairs, filling missing ones")
                            return fill_missing_pairs(qa_pairs, context, num_pairs, difficulty)
                        else:
                            logger.warning(f"Fallback parser only found {len(qa_pairs)}/{num_pairs} QA pairs, retrying...")
                    
                    # Increment retry counter and continue
                    retries += 1
                    if retries < MAX_RETRIES:
                        wait_time = 2 ** retries
                        logger.info(f"JSON parsing failed. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error("All retries failed due to JSON parsing issues")
                        # On final retry, return whatever we have or generate simple fallback pairs
                        return fill_missing_pairs(qa_pairs if qa_pairs else [], context, num_pairs, difficulty)
            else:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                last_error = ValueError(error_msg)
                logger.error(error_msg)
                
                # If we get a 503 or 504, retry
                if response.status_code in [503, 504]:
                    retries += 1
                    if retries < MAX_RETRIES:
                        wait_time = 2 ** retries  # Exponential backoff
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        # On final retry, generate simple fallback pairs
                        return generate_simple_qa_pairs(context, num_pairs)
                else:
                    return generate_simple_qa_pairs(context, num_pairs)
                
        except Timeout:
            last_error = TimeoutError(f"Request timed out after {TIMEOUT} seconds")
            logger.error(f"Request timed out after {TIMEOUT} seconds")
            retries += 1
            if retries < MAX_RETRIES:
                wait_time = 2 ** retries
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("All retries failed due to timeout")
                return generate_simple_qa_pairs(context, num_pairs)
        
        except ConnectionError:
            last_error = ConnectionError("Connection error when trying to reach Ollama")
            logger.error("Connection error when trying to reach Ollama")
            retries += 1
            if retries < MAX_RETRIES:
                wait_time = 2 ** retries
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("All retries failed due to connection error")
                return generate_simple_qa_pairs(context, num_pairs)
                
        except Exception as e:
            last_error = e
            logger.error(f"Error generating QA pairs with Ollama: {str(e)}")
            return generate_simple_qa_pairs(context, num_pairs)
    
    # Default fallback if all retries fail
    return generate_simple_qa_pairs(context, num_pairs)

def fill_missing_pairs(existing_pairs, context, num_pairs, difficulty):
    """
    Fill in missing QA pairs when we don't have enough.
    
    Args:
        existing_pairs (list): List of existing QA pairs
        context (str): The source text to generate questions from
        num_pairs (int): Total number of QA pairs needed
        difficulty (str): Difficulty level
        
    Returns:
        list: Complete list with num_pairs QA pairs
    """
    if len(existing_pairs) >= num_pairs:
        return existing_pairs[:num_pairs]  # Trim if we have too many
        
    missing_count = num_pairs - len(existing_pairs)
    logger.info(f"Generating {missing_count} additional QA pairs to reach requested {num_pairs}")
    
    # Take a section of context to generate additional questions
    # If context is large, use a different section than before
    context_length = len(context)
    if context_length > 1000:
        # Use a different part of the context for new questions
        section_size = min(2000, context_length // 2)
        mid_point = context_length // 2
        section_context = context[mid_point:mid_point+section_size]
    else:
        section_context = context
        
    # Generate a specific prompt for the additional pairs
    prompt = f"""<INSTRUCTIONS>
Generate EXACTLY {missing_count} new question-answer pairs from the content.
These should be different from any existing questions.
The questions should be {difficulty} level.
</INSTRUCTIONS>

<CONTENT>
{section_context}
</CONTENT>

<OUTPUT_FORMAT>
Return a JSON array with EXACTLY {missing_count} question-answer pairs:
[
  {{
    "question": "Question here?",
    "answer": "Answer here."
  }},
  // Continue until you have EXACTLY {missing_count} pairs
]
</OUTPUT_FORMAT>"""

    payload = {
        "model": "llama3:latest",
        "prompt": prompt,
        "stream": False,
        "temperature": 0.75,  # Slightly higher temperature for variety
        "max_tokens": 1024
    }
    
    try:
        # Send the request
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT)
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "")
            
            # Extract the JSON
            try:
                # Try to find JSON in code blocks
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    json_str = json_match.group(1).strip()
                    additional_pairs = json.loads(json_str)
                else:
                    # Try to extract just the JSON array
                    json_start = response_text.find('[')
                    json_end = response_text.rfind(']') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]
                        additional_pairs = json.loads(json_str)
                    else:
                        # Fallback
                        additional_pairs = parse_qa_pairs_fallback(response_text)
                        if not additional_pairs:
                            raise ValueError("Could not extract additional QA pairs")
                
                # Validate and format
                additional_pairs = [{"question": pair.get("question", ""), "answer": pair.get("answer", "")} 
                                    for pair in additional_pairs if "question" in pair and "answer" in pair]
                
                # Combine with existing pairs
                all_pairs = existing_pairs + additional_pairs
                
                # If we still don't have enough, generate simple ones
                if len(all_pairs) < num_pairs:
                    remaining = num_pairs - len(all_pairs)
                    simple_pairs = generate_simple_qa_pairs(context, remaining)
                    all_pairs.extend(simple_pairs)
                
                # Ensure we return exactly num_pairs
                return all_pairs[:num_pairs]
                
            except Exception as e:
                logger.error(f"Error parsing additional QA pairs: {str(e)}")
                # Generate simple pairs for the remainder
                remaining = num_pairs - len(existing_pairs)
                simple_pairs = generate_simple_qa_pairs(context, remaining) 
                return existing_pairs + simple_pairs
        else:
            # Generate simple pairs for the remainder
            remaining = num_pairs - len(existing_pairs)
            simple_pairs = generate_simple_qa_pairs(context, remaining)
            return existing_pairs + simple_pairs
            
    except Exception as e:
        logger.error(f"Error generating additional QA pairs: {str(e)}")
        # Generate simple pairs for the remainder
        remaining = num_pairs - len(existing_pairs)
        simple_pairs = generate_simple_qa_pairs(context, remaining)
        return existing_pairs + simple_pairs

def generate_simple_qa_pairs(context, count):
    """
    Generate simple fallback QA pairs when all else fails.
    Creates basic factoid questions from the context.
    
    Args:
        context (str): The source text
        count (int): Number of QA pairs to generate
        
    Returns:
        list: List of simple QA pairs
    """
    logger.info(f"Generating {count} simple fallback QA pairs")
    
    # Extract sentences for simple factoid questions
    sentences = re.split(r'(?<=[.!?])\s+', context)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    qa_pairs = []
    
    # Generate simple pairs based on the first sentences in the context
    for i in range(min(count, len(sentences))):
        sentence = sentences[i]
        words = sentence.split()
        
        if len(words) < 5:
            continue
            
        # Create a simple factoid question
        qa_pair = {
            "question": f"What is mentioned about {' '.join(words[:3])}?",
            "answer": sentence
        }
        
        qa_pairs.append(qa_pair)
    
    # If we still don't have enough, create generic questions
    while len(qa_pairs) < count:
        index = len(qa_pairs) % max(1, len(sentences))
        sentence = sentences[index] if index < len(sentences) else "The context contains information on this topic."
        
        qa_pair = {
            "question": f"What information is provided in part {len(qa_pairs)+1} of the text?",
            "answer": sentence
        }
        
        qa_pairs.append(qa_pair)
    
    return qa_pairs

def parse_qa_pairs_fallback(text):
    """
    Fallback parser for when JSON parsing fails.
    Attempts to extract question-answer pairs from the raw text response.
    
    Args:
        text (str): Raw text response from the model
        
    Returns:
        list: List of dictionaries containing question, answer pairs with source info
    """
    qa_pairs = []
    lines = text.split('\n')
    current_question = None
    current_answer = None
    current_source = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Handle the format Q1: Question text?
        q_pattern = re.match(r'Q(\d+):\s+(.*)', line)
        if q_pattern:
            # If we have a previous Q/A pair, save it before starting a new one
            if current_question and current_answer:
                qa_pair = {
                    "question": current_question,
                    "answer": current_answer
                }
                # Add source if available
                if current_source:
                    qa_pair["source"] = current_source
                
                qa_pairs.append(qa_pair)
            
            current_question = q_pattern.group(2).strip()
            current_answer = None
            current_source = None
            continue
            
        # Handle the format A: Answer text.
        if line.startswith('A:'):
            current_answer = line[2:].strip()
            continue
        
        # Capture source lines instead of skipping them
        if line.startswith('Source:'):
            current_source = line[7:].strip()
            
            # If we have a complete QA pair and a source, add it
            if current_question and current_answer:
                qa_pair = {
                    "question": current_question,
                    "answer": current_answer
                }
                if current_source:
                    qa_pair["source"] = current_source
                
                qa_pairs.append(qa_pair)
                
                # Reset for next pair
                current_question = None
                current_answer = None
                current_source = None
            continue
            
        # Check for other question patterns
        if line.startswith('"question":') or line.startswith('Q:') or line.startswith('Question:'):
            # Save previous pair if exists
            if current_question and current_answer:
                qa_pair = {
                    "question": current_question,
                    "answer": current_answer
                }
                if current_source:
                    qa_pair["source"] = current_source
                
                qa_pairs.append(qa_pair)
            
            if ":" in line:
                current_question = line.split(":", 1)[1].strip().strip('"').strip(',')
                current_answer = None
                current_source = None
                
        # Check for other answer patterns
        elif (line.startswith('"answer":') or line.startswith('A:') or line.startswith('Answer:')) and current_question:
            if ":" in line:
                current_answer = line.split(":", 1)[1].strip().strip('"').strip(',')
        
        # Check for other source patterns
        elif line.startswith('"source":') or line.startswith('Source:'):
            if ":" in line:
                current_source = line.split(":", 1)[1].strip().strip('"').strip(',')
    
    # Don't forget to add the last pair if it exists
    if current_question and current_answer:
        qa_pair = {
            "question": current_question,
            "answer": current_answer
        }
        if current_source:
            qa_pair["source"] = current_source
            
        qa_pairs.append(qa_pair)
    
    return qa_pairs 