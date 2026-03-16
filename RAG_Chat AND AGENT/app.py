from flask import Flask, request, jsonify, render_template, send_from_directory, current_app, session
import os
import json
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
import sys
import pickle
from pathlib import Path
from dotenv import load_dotenv

# Import necessary modules from the app package
from utils import extractor, text_cleaner
from utils.vector_store import vector_store
from agent_routes import agent_bp
# Load environment variables from .env file
load_dotenv()

# Add a custom JSON encoder to handle circular references
class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            # If we can't serialize it, return a string representation
            return str(obj)

# Initialize Flask app
app = Flask(__name__)
app.register_blueprint(agent_bp)
# Set this encoder in your Flask app
app.json_encoder = SafeJSONEncoder

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['SOURCES_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_sources')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_73829174982174982174')  
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True

# Default API keys configuration
app.config['DEFAULT_API_KEYS'] = {
    'sarvam': os.environ.get('SARVAM_API_KEY', ''),
    'gpt': os.environ.get('OPENAI_API_KEY', ''),
    'gemini': os.environ.get('GEMINI_API_KEY', ''),
    'claude': os.environ.get('CLAUDE_API_KEY', '')
}

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SOURCES_FOLDER'], exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize models dict
models = {}

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'app/static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/')
def home():
    """Initial landing page for conversation."""
    return render_template('home.html')

@app.route('/conversation-upload')
def conversation_upload():
    """Upload page before conversation."""
    return render_template('upload_for_conversation.html')

@app.route('/conversation')
def conversation():
    """Direct conversation with AI assistant."""
    return render_template('conversation.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and return AI responses."""
    try:
        data = request.json
        message = data.get('message')
        model_type = data.get('model')
        api_key = data.get('api_key')
        use_default_key = data.get('use_default_key', False)
        selected_source_ids = data.get('selected_source_ids', [])
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
            
        if not model_type:
            return jsonify({'error': 'No model selected'}), 400
        
        # Use default API key if specified and available
        if use_default_key and model_type in app.config['DEFAULT_API_KEYS']:
            api_key = app.config['DEFAULT_API_KEYS'].get(model_type)
            if not api_key:
                return jsonify({'error': f'Default API key for {model_type} is not configured'}), 400
        
        # Get all sources from session for display purposes
        sources_metadata = session.get('sources_metadata', [])
        logger.info(f"Chat using {len(sources_metadata)} sources from session")
        
        # Filter sources based on selection if specified
        if selected_source_ids:
            filtered_sources = [s for s in sources_metadata if s['id'] in selected_source_ids]
            logger.info(f"Filtered to {len(filtered_sources)} selected sources")
            logger.info(f"Selected source IDs: {selected_source_ids}")
            logger.info(f"Selected sources: {[s['name'] for s in filtered_sources]}")
        else:
            filtered_sources = sources_metadata
        
        # Get relevant context from vector store with filtered sources
        context = vector_store.get_relevant_context(message, source_ids=selected_source_ids)
        
        # Process with appropriate model
        try:
            if model_type == 'ollama':
                from models.ollama.chat import generate_response
                response = generate_response(context, message, sources=filtered_sources)
            elif model_type == 'sarvam':
             from models.sarvam.chat import generate_response
             response = generate_response(context, message, api_key, sources=filtered_sources)
            elif model_type == 'gemini':
                from models.gemini.chat import generate_response
                response = generate_response(context, message, api_key, sources=filtered_sources)
            elif model_type == 'claude':
                from models.claude.chat import generate_response
                response = generate_response(context, message, api_key, sources=filtered_sources)
            elif model_type == 'gpt':
                from models.openai.chat import generate_response
                response = generate_response(context, message, api_key, sources=filtered_sources)
            else:
                return jsonify({'error': 'Invalid model type'}), 400
                
            # Check if the response indicates an error
            if response.startswith('Error:'):
                # Extract error message
                error_message = response.replace('Error:', '').strip()
                if 'timeout' in error_message.lower():
                    return jsonify({
                        'success': False,
                        'error': f"Request timed out. The model took too long to respond. For Ollama, please check that the service is running properly and not overloaded."
                    }), 500
                elif 'connection' in error_message.lower():
                    return jsonify({
                        'success': False,
                        'error': f"Could not connect to {model_type.capitalize()}. Please ensure the service is running and accessible."
                    }), 500
                else:
                    return jsonify({
                        'success': False,
                        'error': error_message
                    }), 500
            
            # Generate a unique ID for this conversation exchange
            conversation_id = str(uuid.uuid4())
            
            # Response passed validation
            return jsonify({
                'success': True,
                'response': response,
                'context': context,  # Include the raw context data
                'conversation_id': conversation_id
            })
            
        except Exception as model_error:
            logging.error(f"Model error in chat endpoint: {str(model_error)}")
            error_msg = str(model_error)
            
            if 'timeout' in error_msg.lower():
                return jsonify({
                    'success': False,
                    'error': f"The {model_type.capitalize()} model took too long to respond. Please try again later."
                }), 500
            elif 'connection' in error_msg.lower() or 'connect' in error_msg.lower():
                return jsonify({
                    'success': False,
                    'error': f"Failed to connect to {model_type.capitalize()}. Please check that the service is running properly."
                }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': f"Error with {model_type.capitalize()} model: {error_msg}"
                }), 500
            
    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/process-url', methods=['POST'])
def process_url():
    """Handle URL content extraction."""
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
            
        url = data['url']
        
        # Check robots.txt first
        allowed, reason = extractor.check_robots_txt(url)
        if not allowed:
            return jsonify({
                'error': 'Access restricted by robots.txt',
                'message': reason,
                'robots_txt_error': True
            }), 403
            
        # Extract content from URL using BeautifulSoup-based extractor
        try:
            content = extractor.extract_website_content(url)
            
            # Count words
            word_count = len(content.split())
            
            return jsonify({
                'success': True,
                'content': content,
                'word_count': word_count,
                'robots_txt_status': reason
            })
        except ValueError as ve:
            # Handle specific extraction errors
            return jsonify({
                'error': str(ve),
                'robots_txt_status': reason
            }), 400
            
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error processing URL: {str(e)}"}), 500

@app.route('/process-text', methods=['POST'])
def process_text():
    """Handle direct text input processing."""
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
            
        text = data['text']
        
        # Clean the text using the text cleaner
        cleaned_text = text_cleaner.clean_text(text)
        
        # Count words
        word_count = len(cleaned_text.split())
        
        return jsonify({
            'success': True,
            'content': cleaned_text,
            'word_count': word_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload-document', methods=['POST'])
def upload_document():
    """Handle document upload and extraction."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Extract content from the file
                content = extractor.process_document(filepath)
                
                # Count words
                word_count = len(content.split())
                
                # Clean up the file after processing
                os.remove(filepath)
                
                return jsonify({
                    'success': True,
                    'content': content,
                    'word_count': word_count
                })
            except Exception as e:
                # Clean up file if extraction fails
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise e
        else:
            return jsonify({'error': 'File type not supported'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-sources')
def get_sources():
    """
    Retrieve the sources that have been uploaded and processed
    """
    try:
        # Get metadata from the session instead of full sources
        sources_metadata = session.get('sources_metadata', [])
        conversation_id = session.get('conversation_id')
        conversation_ready = session.get('conversation_ready', False)
        
        logger.info(f"GET /get-sources: Found metadata for {len(sources_metadata)} sources in session")
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"Session ready state: {conversation_ready}")
        
        # If we have metadata, return it
        if sources_metadata:
            return jsonify({'sources': sources_metadata})
        
        # If no sources found in session metadata, check if we have a backup in files
        if conversation_id:
            sources_file = os.path.join(app.config['SOURCES_FOLDER'], f'{conversation_id}.pkl')
            if os.path.exists(sources_file):
                try:
                    with open(sources_file, 'rb') as f:
                        sources = pickle.load(f)
                    
                    # Create metadata from the full sources
                    sources_metadata = []
                    for source in sources:
                        sources_metadata.append({
                            'id': str(uuid.uuid4()),
                            'type': source['type'],
                            'name': source['name'],
                            'wordCount': source.get('wordCount', 0)
                        })
                    
                    # Save metadata back to session
                    session['sources_metadata'] = sources_metadata
                    session.modified = True
                    
                    logger.info(f"Recovered {len(sources_metadata)} sources from file")
                    return jsonify({'sources': sources_metadata})
                except Exception as file_error:
                    logger.error(f"Error loading sources file: {str(file_error)}")
            else:
                logger.warning(f"Sources file not found: {sources_file}")
        
        # No sources found
        return jsonify({'sources': [], 'message': 'No sources found in session'})
            
    except Exception as e:
        logger.error(f"Error retrieving sources: {str(e)}", exc_info=True)
        return jsonify({'sources': [], 'error': str(e)})

@app.route('/process-sources', methods=['POST'])
def process_sources():
    """Handle processing of all sources for conversation."""
    try:
        data = request.json
        if not data or 'sources' not in data:
            return jsonify({'error': 'No sources provided'}), 400

        sources = data['sources']
        if not sources:
            return jsonify({'error': 'No sources to process'}), 400

        # Generate a unique ID for this conversation's sources
        conversation_id = str(uuid.uuid4())
        
        # Store the FULL sources in a file instead of the session
        sources_file = os.path.join(app.config['SOURCES_FOLDER'], f'{conversation_id}.pkl')
        with open(sources_file, 'wb') as f:
            pickle.dump(sources, f)
            
        # Store only metadata in the session (not the full content)
        sources_metadata = []
        for source in sources:
            sources_metadata.append({
                'id': str(uuid.uuid4()),
                'type': source['type'],
                'name': source['name'],
                'wordCount': source.get('wordCount', 0)
            })
            
        # Store only metadata and ID in the session
        session['sources_metadata'] = sources_metadata
        session['conversation_id'] = conversation_id
        session.modified = True
        
        # Debug logging for session state
        logger.info(f"Stored metadata for {len(sources_metadata)} sources in session")
        logger.info(f"Full sources saved to file: {sources_file}")
        
        # Process each source
        processed_sources = []
        for source in sources:
            try:
                if source['type'] == 'file':
                    # Handle file content
                    content = source['content']
                    metadata = {
                        'type': 'file',
                        'name': source['name'],
                        'source': 'document',
                        'id': next((s['id'] for s in sources_metadata if s['name'] == source['name']), str(uuid.uuid4()))
                    }
                elif source['type'] == 'link':
                    # Handle URL content
                    content = source['content']
                    url = source.get('url', source['name'])  # Get URL from source or use name as fallback
                    metadata = {
                        'type': 'url',
                        'name': source['name'],
                        'source': 'url',
                        'url': url,  # Store the actual URL for citation
                        'id': next((s['id'] for s in sources_metadata if s['name'] == source['name']), str(uuid.uuid4()))
                    }
                elif source['type'] == 'text':
                    # Handle pasted text
                    content = source['content']
                    metadata = {
                        'type': 'text',
                        'name': source['name'],
                        'source': 'text',
                        'id': next((s['id'] for s in sources_metadata if s['name'] == source['name']), str(uuid.uuid4()))
                    }
                else:
                    continue  # Skip unsupported source types

                # Store in vector database
                success = vector_store.store_document(content, metadata)
                print("Storing content length:", len(content))
                if success:
                    processed_sources.append({
                        'type': source['type'],
                        'name': source['name'],
                        'status': 'success'
                    })
                else:
                    processed_sources.append({
                        'type': source['type'],
                        'name': source['name'],
                        'status': 'failed',
                        'error': 'Failed to store in vector database'
                    })

            except Exception as e:
                processed_sources.append({
                    'type': source['type'],
                    'name': source['name'],
                    'status': 'failed',
                    'error': str(e)
                })

        # Check if any sources were successfully processed
        if not any(s['status'] == 'success' for s in processed_sources):
            return jsonify({
                'success': False,
                'error': 'Failed to process any sources',
                'details': processed_sources
            }), 500

        return jsonify({
            'success': True,
            'processed_sources': processed_sources
        })

    except Exception as e:
        logger.error(f"Error in process_sources: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/clear-sources', methods=['POST'])
def clear_sources():
    """
    Clear all sources from the session and vector database
    """
    try:
        # Get the conversation ID before clearing
        conversation_id = session.get('conversation_id')
        
        # Clear sources from session
        session.pop('sources_metadata', None)
        session.pop('conversation_id', None)
        session.pop('conversation_ready', None)
        
        # Clean up file if it exists
        if conversation_id:
            sources_file = os.path.join(app.config['SOURCES_FOLDER'], f'{conversation_id}.pkl')
            if os.path.exists(sources_file):
                try:
                    os.remove(sources_file)
                    logger.info(f"Removed sources file: {sources_file}")
                except Exception as file_error:
                    logger.warning(f"Could not remove sources file: {str(file_error)}")
        
        # Clear vector database
        if hasattr(vector_store, 'clear_documents'):
            vector_store.clear_documents()
        elif hasattr(vector_store, 'clear_collection'):
            vector_store.clear_collection()
        else:
            # Log warning if no clear method is available
            logger.warning("No method available to clear vector store")
            
        return jsonify({'success': True, 'message': 'All sources cleared'})
    except Exception as e:
        logger.error(f"Error clearing sources: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/ready-for-conversation', methods=['POST'])
def ready_for_conversation():
    """
    Prepare session for conversation by setting a flag
    """
    try:
        # Get current sources metadata
        sources_metadata = session.get('sources_metadata', [])
        conversation_id = session.get('conversation_id')
        
        if not sources_metadata and conversation_id:
            # Try to recover from file if metadata is missing
            sources_file = os.path.join(app.config['SOURCES_FOLDER'], f'{conversation_id}.pkl')
            if os.path.exists(sources_file):
                try:
                    with open(sources_file, 'rb') as f:
                        sources = pickle.load(f)
                    
                    # Create metadata from the full sources
                    sources_metadata = []
                    for source in sources:
                        sources_metadata.append({
                            'id': str(uuid.uuid4()),
                            'type': source['type'],
                            'name': source['name'],
                            'wordCount': source.get('wordCount', 0)
                        })
                    
                    # Save metadata back to session
                    session['sources_metadata'] = sources_metadata
                    session.modified = True
                    logger.info(f"Recovered {len(sources_metadata)} sources from file for conversation")
                except Exception as file_error:
                    logger.error(f"Error loading sources file: {str(file_error)}")
        
        if not sources_metadata:
            return jsonify({
                'success': False, 
                'error': 'No sources found in session'
            }), 400
            
        # Set a ready flag to ensure session is maintained
        session['conversation_ready'] = True
        
        # Force session to be saved
        session.modified = True
        
        logger.info(f"Session prepared for conversation with {len(sources_metadata)} sources")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error preparing conversation: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate-qa-dataset', methods=['POST'])
def generate_qa_dataset():
    """Generate QA pairs from provided sources."""
    try:
        data = request.json
        if not data or 'sources' not in data:
            return jsonify({'success': False, 'error': 'No sources provided'}), 400
            
        sources = data.get('sources', [])
        qa_count = int(data.get('qaCount', 10))
        difficulty = data.get('difficulty', 'intermediate')
        model_type = data.get('model')
        api_key = data.get('api_key')
        use_default_key = data.get('use_default_key', False)
        custom_queries = data.get('customQueries', [])
        include_auto_queries = data.get('includeAutoQueries', True)
        
        # Validate model type
        if not model_type:
            return jsonify({'success': False, 'error': 'No model selected'}), 400
            
        # Validate inputs
        if not sources:
            return jsonify({'success': False, 'error': 'No sources to process'}), 400
            
        # Use default API key if specified and available
        if use_default_key and model_type in app.config['DEFAULT_API_KEYS']:
            api_key = app.config['DEFAULT_API_KEYS'].get(model_type)
            if not api_key:
                return jsonify({'success': False, 'error': f'Default API key for {model_type} is not configured'}), 400
            
        # Check if API key is required but not provided
        if model_type in ['sarvam','gpt', 'claude', 'gemini'] and not api_key:
            return jsonify({'success': False, 'error': f'API key is required for {model_type}'}), 400
        
        # Process each source to extract content
        processed_sources = []
        
        # Get current session sources from database
        session_sources = get_session_sources()
        if not session_sources:
            return jsonify({'success': False, 'error': 'No source content available in session'}), 400
            
        # Create mapping of source IDs to content
        source_content_map = {s.get('id'): s.get('content', '') for s in session_sources}
        
        # Also create a mapping by source name as fallback
        source_name_map = {s.get('name'): s.get('content', '') for s in session_sources}
        logger.info(f"Requested source IDs: {[s.get('id') for s in sources]}")
        
        # Process each source from the request
        for source in sources:
            source_id = source.get('id')
            source_name = source.get('name')
            
            # First try to match by name
            if source_name in source_name_map:
                processed_sources.append({
                    'id': source_id,
                    'type': source.get('type'),
                    'name': source_name,
                    'content': source_name_map[source_name]
                })
            # If name matching fails, try to match by ID
            elif source_id in source_content_map:
                logger.info(f"Name match failed for {source_name}, using ID match for {source_id}")
                processed_sources.append({
                    'id': source_id,
                    'type': source.get('type'),
                    'name': source.get('name'),
                    'content': source_content_map[source_id]
                })
        
        if not processed_sources:
            logger.error("Could not match any sources by ID or name")
            return jsonify({'success': False, 'error': 'Could not find content for the provided sources. Please try re-processing your sources.'}), 400
        
        # Generate QA pairs using the appropriate model
        qa_pairs = []
        
        try:
            # Import the appropriate model module based on model_type
            if model_type == 'ollama':
                from models.ollama.model import generate_qa_dataset as model_generate_qa
                
            elif model_type == 'sarvam':
                from models.sarvam.model import generate_qa_dataset as model_generate_qa
            elif model_type == 'gpt':
                from models.openai.model import generate_qa_dataset as model_generate_qa    
            elif model_type == 'claude':
                from models.claude.model import generate_qa_dataset as model_generate_qa
                
            elif model_type == 'gemini':
                from models.gemini.model import generate_qa_dataset as model_generate_qa
                
            else:
                return jsonify({'success': False, 'error': 'Invalid model type'}), 400
            
            # Determine how to distribute QA pairs
            remaining_pairs = qa_count
            pairs_to_generate = []
            
            # Calculate allocation between auto-generated and custom queries
            if include_auto_queries and custom_queries:
                # Split QA pairs between auto-generated and custom queries if both are enabled
                # Auto-generated queries: 60%, Custom queries: 40%
                auto_query_count = int(remaining_pairs * 0.6)
                custom_query_count = remaining_pairs - auto_query_count
                auto_query_count = max(auto_query_count, 1) if include_auto_queries else 0
                custom_query_count = max(custom_query_count, 1) if custom_queries else 0
            elif include_auto_queries:
                # All pairs for auto-generated queries
                auto_query_count = remaining_pairs
                custom_query_count = 0
            elif custom_queries:
                # All pairs for custom queries
                auto_query_count = 0
                custom_query_count = remaining_pairs
            else:
                # No queries specified (shouldn't happen based on UI)
                return jsonify({'success': False, 'error': 'No query method selected'}), 400
                
            # Process auto-generated queries if enabled
            if include_auto_queries and auto_query_count > 0:
                source_count = len(processed_sources)
                # Calculate pairs per source, ensuring the total is exactly auto_query_count
                base_pairs_per_source = auto_query_count // source_count
                remainder = auto_query_count % source_count
                
                for i, source in enumerate(processed_sources):
                    # Distribute remainder evenly
                    source_pairs = base_pairs_per_source + (1 if i < remainder else 0)
                    if source_pairs > 0:
                        pairs_to_generate.append({
                            'type': 'source',
                            'source': source,
                            'query': None,
                            'pairs': source_pairs
                        })
            
            # Process custom queries if any
            if custom_queries and custom_query_count > 0:
                query_count = len(custom_queries)
                # Calculate pairs per query, ensuring the total is exactly custom_query_count
                base_pairs_per_query = custom_query_count // query_count
                remainder = custom_query_count % query_count
                
                for i, query in enumerate(custom_queries):
                    topic = query.strip()
                    if topic:
                        # Distribute remainder evenly
                        query_pairs = base_pairs_per_query + (1 if i < remainder else 0)
                        if query_pairs > 0:
                            pairs_to_generate.append({
                                'type': 'custom',
                                'topic': topic,
                                'pairs': query_pairs
                            })
            
            # Now generate all QA pairs based on allocation
            for item in pairs_to_generate:
                try:
                    if item['type'] == 'source':
                        source = item['source']
                        logger.info(f"Generating {item['pairs']} QA pairs for source: {source['name']}")
                        
                        # Generate QA pairs using the model
                        source_pairs = model_generate_qa(
                            context=source['content'],
                            query=None,
                            num_pairs=item['pairs'],
                            difficulty=difficulty,
                            api_key=api_key
                        )
                        
                        # Add source information to each pair
                        for pair in source_pairs:
                            pair['source'] = source['name']
                            pair['sourceId'] = source['id']
                            qa_pairs.append(pair)
                            
                    elif item['type'] == 'custom':
                        topic = item['topic']
                        logger.info(f"Generating {item['pairs']} QA pairs for topic: {topic}")
                        
                        # Use vector store to get relevant context
                        from utils.vector_store import vector_store
                        
                        # Try a more targeted search query format to improve results
                        search_query = f"information about {topic}"
                        
                        # First, use the vector store to search for relevant content
                        topic_context = vector_store.get_relevant_context(
                            query=search_query, 
                            max_tokens=8000,
                            source_ids=[s['id'] for s in processed_sources]
                        )
                        
                        # Check if we got meaningful results
                        if not topic_context or len(topic_context.strip()) < 200:
                            # Try a different query format
                            logger.warning(f"Insufficient results with first query. Trying direct topic search: {topic}")
                            topic_context = vector_store.get_relevant_context(
                                query=topic,
                                max_tokens=8000,
                                source_ids=[s['id'] for s in processed_sources]
                            )
                            
                        # If still insufficient, use full content
                        if not topic_context or len(topic_context.strip()) < 200:
                            logger.warning(f"Vector search returned insufficient content for topic: {topic}")
                            # Fall back to using combined content
                            logger.info("Using combined content from all sources as fallback")
                            topic_context = "\n\n".join([
                                f"### {s['name']}\n\n{s['content'][:2000]}" 
                                for s in processed_sources
                            ])
                        
                        # Generate QA pairs for this topic
                        topic_pairs = model_generate_qa(
                            context=topic_context,
                            query=topic,
                            num_pairs=item['pairs'],
                            difficulty=difficulty,
                            api_key=api_key
                        )
                        
                        # Add topic information to each pair
                        for pair in topic_pairs:
                            pair['source'] = f"Topic: {topic}"
                            pair['sourceId'] = "custom"
                            pair['topic'] = topic
                            qa_pairs.append(pair)
                        
                except Exception as model_error:
                    error_msg = str(model_error)
                    logger.error(f"Error generating QA pairs: {error_msg}")
                    raise ValueError(f"Error with model {model_type}: {error_msg}")
            
            # Final check if we got any QA pairs at all
            if not qa_pairs:
                raise ValueError(f"No QA pairs were generated. There may be an issue with the model or API key.")
                
            # Ensure we have exactly qa_count pairs (trim if we have too many)
            if len(qa_pairs) > qa_count:
                qa_pairs = qa_pairs[:qa_count]
            
            return jsonify({
                'success': True,
                'qa_pairs': qa_pairs
            })
            
        except ImportError as e:
            logger.error(f"Error importing model module: {str(e)}")
            return jsonify({'success': False, 'error': f"Model {model_type} is not properly configured"}), 500
            
        except Exception as e:
            logger.error(f"Error generating QA pairs: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
        
    except Exception as e:
        logger.error(f"Error generating QA dataset: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dataset')
def dataset():
    """Generate QA dataset from documents."""
    return render_template('dataset.html')

@app.route('/check-default-key', methods=['POST'])
def check_default_key():
    """Check if a default API key is configured for a specific model."""
    try:
        data = request.json
        model_type = data.get('model')
        
        if not model_type:
            return jsonify({'error': 'No model specified'}), 400
            
        has_default_key = False
        if model_type in app.config['DEFAULT_API_KEYS']:
            has_default_key = bool(app.config['DEFAULT_API_KEYS'].get(model_type))
        
        return jsonify({
            'has_default_key': has_default_key
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def allowed_file(filename):
    """Check if the file extension is allowed."""
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_session_sources():
    """
    Retrieve source content from the session or backup files.
    
    Returns:
        list: List of source objects with content and metadata
    """
    try:
        # Get conversation ID from session
        conversation_id = session.get('conversation_id')
        
        # Check if we have a conversation ID
        if not conversation_id:
            logger.warning("No conversation ID found in session")
            return []
            
        # Try to get sources from backup file
        sources_file = os.path.join(app.config['SOURCES_FOLDER'], f'{conversation_id}.pkl')
        if os.path.exists(sources_file):
            try:
                with open(sources_file, 'rb') as f:
                    sources = pickle.load(f)
                logger.info(f"Retrieved {len(sources)} sources from file")
                return sources
            except Exception as e:
                logger.error(f"Error loading sources from file: {str(e)}")
                
        logger.warning("No source content available")
        return []
        
    except Exception as e:
        logger.error(f"Error in get_session_sources: {str(e)}")
        return []

if __name__ == '__main__':
    # Get configuration from environment variables with defaults
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    host = os.environ.get('FLASK_HOST', '127.0.0.1')  # Default to localhost for security
    port = int(os.environ.get('FLASK_PORT', '8000'))
    
    # Log the configuration
    logger.info(f"Starting Flask app with: debug={debug_mode}, host={host}, port={port}")
    
    app.run(debug=debug_mode, host=host, port=port) 