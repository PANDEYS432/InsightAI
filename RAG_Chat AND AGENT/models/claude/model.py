import requests
import json
import logging
import time
import anthropic
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = "claude-3-haiku-20240307"  

def generate_qa_dataset(context, query=None, num_pairs=5, difficulty="intermediate", api_key=None):
    """
    Generate QA pairs using Anthropic's Claude model.
    
    Args:
        context (str): The source text to generate questions from
        query (str, optional): Custom query to include in generation
        num_pairs (int): Number of QA pairs to generate
        difficulty (str): Difficulty level ('basic', 'intermediate', 'advanced')
        api_key (str): Claude API key
        
    Returns:
        list: List of dictionaries containing question, answer pairs
        
    Raises:
        ValueError: If API key is missing, API returns an error, or response parsing fails
    """
    if not api_key:
        logger.error("Claude API key is required")
        raise ValueError("API key is required for Claude. Please provide a valid API key.")
    
    # Create the prompt for Claude
    system_message, user_prompt = create_qa_prompt(context, query, num_pairs, difficulty)
    
    client = None  # Initialize client variable for cleanup in finally block
    try:
        logger.info("Sending QA generation request to Claude")
        
        # Initialize the Claude client with the API key
        client = anthropic.Anthropic(api_key=api_key)
        
        # Make the API call
        response = client.messages.create(
            model=DEFAULT_MODEL,
            system=system_message,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2048
        )
        
        # Extract the text from the content blocks
        full_text = ""
        for content_block in response.content:
            if content_block.type == "text":
                full_text += content_block.text
        
        # Try to parse JSON response
        qa_pairs = parse_claude_response(full_text)
        
        # Fall back to regex extraction if JSON parsing fails
        if not qa_pairs:
            qa_pairs = extract_qa_pairs_fallback(full_text)
        
        # Validate the pairs
        valid_pairs = []
        for pair in qa_pairs:
            if ('question' in pair and pair['question'].strip() and 
                'answer' in pair and pair['answer'].strip()):
                valid_pairs.append(pair)
        
        if not valid_pairs:
            logger.error("No valid QA pairs found in Claude response")
            raise ValueError("Failed to generate valid QA pairs: No valid pairs in Claude response")
        
        return valid_pairs
                
    except anthropic.APIError as e:
        error_msg = f"Claude API error: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
            
    except anthropic.APITimeoutError:
        error_msg = "Request to Claude API timed out"
        logger.error(error_msg)
        raise ValueError(error_msg)
            
    except Exception as e:
        if isinstance(e, ValueError) and "Claude" in str(e):
            # Re-raise custom ValueError exceptions we've already created
            raise
        error_msg = f"Unexpected error when generating QA pairs with Claude: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    finally:
        # Clean up client resources if possible
        if client:
            if hasattr(client, 'close') and callable(client.close):
                client.close()
            elif hasattr(client, '_client') and hasattr(client._client, 'close'):
                client._client.close()
    
    # This should never be reached due to exceptions above
    raise ValueError("Unexpected error generating QA pairs with Claude")

def create_qa_prompt(context, query=None, num_pairs=5, difficulty='intermediate'):
    """
    Create a prompt for the Claude model to generate QA pairs
    
    Args:
        context (str): The source text to generate questions from
        query (str, optional): Custom query to include in generation
        num_pairs (int): Number of QA pairs to generate
        difficulty (str): Difficulty level ('basic', 'intermediate', 'advanced')
        
    Returns:
        tuple: (system_message, user_prompt)
    """
    # Construct appropriate system prompt based on difficulty
    if difficulty == "basic":
        level_description = "simple factual questions that can be directly answered from the text"
    elif difficulty == "advanced":
        level_description = "complex analytical questions requiring synthesis of multiple concepts and inferential reasoning"
    else:  # intermediate
        level_description = "moderately complex questions requiring understanding connections between concepts"
    
    # Create the system message
    system_message = f"You are an expert at creating high-quality question-answer pairs for educational datasets. Your task is to generate exactly {num_pairs} question-answer pairs at {difficulty} difficulty level ({level_description}). Output only valid JSON."
    
    # Add query focus if provided
    query_focus = ""
    if query:
        query_focus = f"\n\nFOCUS AREA: {query}"
    
    # Create the user prompt
    user_prompt = f"""<CONTENT>
{context}
</CONTENT>{query_focus}

<OUTPUT_FORMAT>
Create a JSON array with exactly {num_pairs} question-answer pairs based strictly on the provided content:
[
  {{
    "question": "Question text here?",
    "answer": "Answer text here."
  }},
  ...
]
</OUTPUT_FORMAT>

Your response must contain ONLY the JSON array without any explanations, introductions or instructions."""
    
    return system_message, user_prompt

def parse_claude_response(content):
    """
    Parse the response from Claude to extract QA pairs
    
    Args:
        content (str): Text response from Claude
        
    Returns:
        list: List of dictionaries with question, answer pairs
    """
    try:
        # First, try to extract JSON block if it's formatted as a code block
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
            logger.error("Could not find JSON array in Claude response")
            return None
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Claude: {e}")
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