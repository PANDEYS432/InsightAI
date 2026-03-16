from openai import OpenAI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_response(context, query, api_key, sources=None):
    """
    Generate a response using the OpenAI GPT API.
    
    Args:
        context (str): The relevant context retrieved from the vector store
        query (str): The user's question
        api_key (str): The OpenAI API key
        sources (list): List of dictionaries containing source information (name, type, url)
        
    Returns:
        str: The generated response
    """
    client = None  # Initialize client variable for use in finally block
    try:
        # Initialize the OpenAI client with the API key
        client = OpenAI(api_key=api_key)
        
        # Prepare the message content
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
            
            system_prompt = f"""Please answer the following question using the context provided. Include relevant information from the sources when applicable.
            
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
5. If the question is about a specific topic or section that exists in the context, provide that information even if it's not detailed
6. If the question is a greeting or simple inquiry unrelated to the context, respond appropriately without using the context
7. Be consistent in your responses - if information existed in the context before, it still exists now
8. Always search for related keywords and concepts, not just exact phrase matches
9. Draw reasonable connections between the question and any relevant content in the context
10. If the question is COMPLETELY unrelated to the context (like games, jokes, or personal requests), DO NOT try to force connections to the context - just respond that you can only answer questions related to the provided documents


Answer:
"""
        else:
            # No relevant context found, instruct the model to decline answering
            system_prompt = """You are a retrieval-augmented AI assistant that only answers questions based on the retrieved documents."""
            query = f"""The user asked: "{query}"

However, no relevant information was found in the knowledge base for this query. 

Please inform the user that you cannot answer this question as it appears to be unrelated to the sources they provided. Suggest that they might want to try a different question related to the documents they've uploaded or to upload additional relevant documents if they want an answer to this specific question."""
        
        # Generate the response
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        
        # Extract and return the response
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        else:
            return "No response generated"
            
    except Exception as e:
        logger.error(f"Error generating response with GPT: {str(e)}")
        error_str = str(e)
        
        # Provide user-friendly error messages
        if "api key" in error_str.lower() or "invalid authentication" in error_str.lower():
            return "Error: Invalid API key. Please check your OpenAI API key and try again."
        elif "rate limit" in error_str.lower() or "requests per min" in error_str.lower():
            return "Error: API rate limit exceeded. Please try again later."
        elif "content policy" in error_str.lower() or "flagged" in error_str.lower():
            return "Error: The request was blocked by content filters. Please try a different query."
        else:
            # For other errors, provide a generic message but log the details
            return "Error: Could not generate a response. Please try again or check your API key."
    finally:
        # Ensure resources are cleaned up regardless of success or failure
        if client:
            if hasattr(client, 'close') and callable(client.close):
                client.close()
            elif hasattr(client, '_session') and hasattr(client._session, 'close'):
                client._session.close() 