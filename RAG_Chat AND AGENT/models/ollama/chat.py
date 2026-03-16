import os
import requests
import json
import logging
import time
from requests.exceptions import Timeout, ConnectionError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3")
MAX_RETRIES = 3
TIMEOUT = 120  # Increased from 60 to 120 seconds

def generate_response(context, query, sources=None):
    """
    Generate a response using the Ollama local API.
    
    Args:
        context (str): The relevant context retrieved from the vector store
        query (str): The user's question
        sources (list): List of dictionaries containing source information (name, type, url)
        
    Returns:
        str: The generated response
    """
    # Prepare the prompt with context and query
    if context and context.strip():
        # Add source information if available
        source_info = ""
        if sources:
            source_info = "\n\nSources used:\n"
            for source in sources:
                source_type = source.get('type', 'document')
                source_name = source.get('name', 'Unknown')
                source_url = source.get('url', '')
                if source_type == 'url':
                    source_info += f"- URL: {source_url}\n"
                else:
                    source_info += f"- Document: {source_name}\n"
        
        prompt = f"""Please answer the following question using the context provided. Include relevant information from the sources when applicable.
            
Context:
{context}

Question:
{query}

{source_info}

Instructions:
1. CAREFULLY read through the entire context before answering
2. If any information related to the question appears ANYWHERE in the context, provide that information
3. Be thorough and provide all relevant details from the context
4. NEVER claim that information is missing or not available if ANY related information exists in the context
5. If the question is about a specific topic or section that exists in the context, provide only that much infomation that is present in the context and don't add your own information
6. If the question is a greeting or simple inquiry unrelated to the context, respond appropriately without using the context
7. Be consistent in your responses - if information existed in the context before, it still exists now
8. Always search for related keywords and concepts, not just exact phrase matches
9. Draw reasonable connections between the question and any relevant content in the context
10. If the question is COMPLETELY unrelated to the context (like games, jokes, or personal requests), DO NOT try to force connections to the context - just respond that you can only answer questions related to the provided documents
11. If the user query is a topic that is not related to the context, just respond that you can only answer questions related to the provided documents and not the topic that is not related to the context
Answer:
"""
    else:
        # No relevant context found, instruct the model to decline answering
        prompt = f"""You are a retrieval-augmented AI assistant. The user asked the following question:

Question: 
{query}

However, no relevant information was found in your knowledge base for this query. Please politely inform the user that you cannot answer this question as it appears to be unrelated to the sources they provided. Suggest that they might want to try a different question related to the documents they've uploaded or to upload additional relevant documents if they want an answer to this specific question.

Your response:"""
        
    # Prepare the request payload
    payload = {
        "model": MODEL_NAME,  # Default model
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 512
    }
    
    # Add retry logic
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Send the request to Ollama with increased timeout
            # logger.info(f"Sending request to Ollama (attempt {retries+1}/{MAX_RETRIES})")
            logger.info(f"Sending request to Ollama using model {MODEL_NAME} (attempt {retries+1}/{MAX_RETRIES})")
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response generated")
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                # If we get a 503 or 504, retry
                if response.status_code in [503, 504]:
                    retries += 1
                    if retries < MAX_RETRIES:
                        wait_time = 2 ** retries  # Exponential backoff
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                return f"Error generating response: {response.status_code}"
                
        except Timeout:
            logger.error(f"Request timed out after {TIMEOUT} seconds")
            retries += 1
            if retries < MAX_RETRIES:
                wait_time = 2 ** retries
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return f"Error: Request to Ollama timed out after {TIMEOUT} seconds. Please try again later or check if Ollama is running correctly."
        
        except ConnectionError:
            logger.error("Connection error when trying to reach Ollama")
            retries += 1
            if retries < MAX_RETRIES:
                wait_time = 2 ** retries
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return "Error: Could not connect to Ollama. Please check if the service is running and accessible."
                
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {str(e)}")
            return f"Error: {str(e)}"

        