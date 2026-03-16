import openai
from openai import OpenAI
import json
import logging
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = "gpt-3.5-turbo"  # Could also use "gpt-3.5-turbo" for faster, cheaper results

def generate_qa_dataset(context, query=None, num_pairs=5, difficulty="intermediate", api_key=None):
    """
    Generate QA pairs using OpenAI's GPT model.
    
    Args:
        context (str): The source text to generate questions from
        query (str, optional): Custom query to include in generation
        num_pairs (int): Number of QA pairs to generate
        difficulty (str): Difficulty level ('basic', 'intermediate', 'advanced')
        api_key (str): OpenAI API key
        
    Returns:
        list: List of dictionaries containing question, answer pairs
        
    Raises:
        ValueError: If API key is missing, API returns an error, or response parsing fails
    """
    if not api_key:
        logger.error("OpenAI API key is required")
        raise ValueError("API key is required for OpenAI. Please provide a valid API key.")
    
    # Create the messages for OpenAI
    system_message, user_message = create_qa_prompt(context, query, num_pairs, difficulty)
    
    try:
        logger.info("Sending QA generation request to OpenAI")
        
        # Prepare the context for the model
        if context and len(context) > 32000:
            logger.warning(f"Context length {len(context)} exceeds recommended limit. Truncating...")
            context = context[:32000]
            
        # Set up the OpenAI client inside try block for proper cleanup
        client = OpenAI(api_key=api_key)
        
        # Make the API call
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    system_message,
                    user_message
                ],
                temperature=0.7,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )
            
            # Explicitly close the client's session to free up resources
            if hasattr(client, 'close') and callable(client.close):
                client.close()
            elif hasattr(client, '_session') and hasattr(client._session, 'close'):
                client._session.close()
                
        except openai.APIError as e:
            # Ensure client is closed on error
            if hasattr(client, 'close') and callable(client.close):
                client.close()
            elif hasattr(client, '_session') and hasattr(client._session, 'close'):
                client._session.close()
                
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(error_msg)
            if "API key" in str(e).lower():
                raise ValueError("Invalid API key provided for OpenAI. Please check your API key.")
            raise ValueError(error_msg)
        
        # Get the content from the response
        content = response.choices[0].message.content
        
        if not content or content.strip() == "":
            error_msg = "Empty response from OpenAI"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Try to parse JSON response
        qa_pairs = parse_openai_response(content)
        
        # Fall back to regex extraction if JSON parsing fails
        if not qa_pairs:
            qa_pairs = extract_qa_pairs_fallback(content)
            
        # Validate the QA pairs
        if not qa_pairs:
            error_msg = "Failed to extract valid QA pairs from OpenAI response"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Validate each pair has a question and answer
        valid_pairs = []
        for pair in qa_pairs:
            if ('question' in pair and pair['question'].strip() and 
                'answer' in pair and pair['answer'].strip()):
                valid_pairs.append(pair)
        
        if not valid_pairs:
            error_msg = "No valid QA pairs found in OpenAI response"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return valid_pairs
            
    except Exception as e:
        if isinstance(e, ValueError) and "OpenAI" in str(e):
            # Re-raise custom ValueError exceptions we've already created
            raise
        error_msg = f"Unexpected error when generating QA pairs with OpenAI: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # This should never be reached due to exceptions above
    raise ValueError("Unexpected error generating QA pairs with OpenAI")

def create_qa_prompt(context, query=None, num_pairs=5, difficulty='intermediate'):
    """
    Create a prompt for the OpenAI model to generate QA pairs
    
    Args:
        context (str): The source text to generate questions from
        query (str, optional): Custom query to include in generation
        num_pairs (int): Number of QA pairs to generate
        difficulty (str): Difficulty level ('basic', 'intermediate', 'advanced')
        
    Returns:
        tuple: (system_message, user_message) formatted as dicts for OpenAI
    """
    # Construct appropriate system prompt based on difficulty
    if difficulty == "basic":
        level_description = "simple factual questions that can be directly answered from the text"
    elif difficulty == "advanced":
        level_description = "complex analytical questions requiring synthesis of multiple concepts and inferential reasoning"
    else:  # intermediate
        level_description = "moderately complex questions requiring understanding connections between concepts"
    
    # Create the system message
    system_message = {
        "role": "system", 
        "content": f"You are an expert at creating high-quality question-answer pairs for educational datasets. Your task is to generate exactly {num_pairs} pairs at {difficulty} difficulty level ({level_description}). Return only JSON without including the instructions in your output."
    }
    
    # Add query focus if provided
    query_instruction = ""
    if query:
        query_instruction = f"\n\nFOCUS TOPIC: {query}"
    
    # Create the user message
    user_message = {
        "role": "user",
        "content": f"""<CONTENT>
{context}
</CONTENT>{query_instruction}

<OUTPUT_FORMAT>
Create a JSON array with exactly {num_pairs} question-answer pairs based ONLY on the above content:
[
  {{
    "question": "Question text here?",
    "answer": "Answer text here."
  }},
  ...
]
</OUTPUT_FORMAT>

Your response must contain ONLY the JSON array - do not include any explanations, introductions, or the instructions themselves."""
    }
    
    return system_message, user_message

def parse_openai_response(content):
    """
    Parse the response from OpenAI to extract QA pairs
    
    Args:
        content (str): Text response from OpenAI
        
    Returns:
        list: List of dictionaries with question, answer pairs
    """
    try:
        # First, handle the case where GPT returns a JSON object with a key
        if content.strip().startswith("{"):
            parsed_content = json.loads(content)
            if "qa_pairs" in parsed_content:
                return parsed_content["qa_pairs"]
            else:
                # Find a key that looks like it contains Q&A pairs
                for key in parsed_content:
                    if isinstance(parsed_content[key], list) and len(parsed_content[key]) > 0:
                        return parsed_content[key]
        
        # Try to extract JSON block if it's formatted as a code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            json_str = json_match.group(1)
            qa_pairs = json.loads(json_str)
            return qa_pairs
        
        # If no code block, try to find JSON array directly
        json_start = content.find('[')
        json_end = content.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            qa_pairs = json.loads(json_str)
            return qa_pairs
        else:
            logger.error("Could not find JSON array in OpenAI response")
            return None
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from OpenAI: {e}")
        return None

def extract_qa_pairs_fallback(text):
    """
    Fallback function to extract question-answer pairs from unstructured text
    when JSON parsing fails.
    
    Args:
        text (str): Text response from model
        
    Returns:
        list: List of dictionaries with question, answer pairs
    """
    qa_pairs = []
    
    # Try to identify question-answer patterns
    # Look for patterns like "Q1: ....\nA1: ...." or "Question 1: ....\nAnswer 1: ...."
    qa_blocks = re.findall(r'(?:(?:Q|Question)[^\n]*?\:)(.*?)(?:(?:A|Answer)[^\n]*?\:)(.*?)(?=(?:(?:Q|Question)[^\n]*?\:)|$)', 
                          text, re.DOTALL)
    
    if qa_blocks:
        for q, a in qa_blocks:
            qa_pairs.append({
                "question": q.strip(),
                "answer": a.strip()
            })
    
    return qa_pairs 