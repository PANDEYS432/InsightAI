from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import uuid
from pathlib import Path
import logging
import shutil
import math
import os
from dotenv import load_dotenv
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.embeddings import HuggingFaceEmbeddings

# Load environment variables
load_dotenv()

class VectorStore:
    def __init__(self, persist_directory: str = "data/chroma_db_new"):
        self.logger = logging.getLogger(__name__)
        
        # Set up ChromaDB
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize HuggingFace embeddings for ChromaDB
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name='all-MiniLM-L6-v2'
        )
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize HuggingFaceEmbeddings for SemanticChunker
        # Using the same model as ChromaDB for consistency
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Initialize SemanticChunker with embeddings
        self.text_splitter = SemanticChunker(
            embeddings=self.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=90
        )
        
        # Fallback text splitter in case SemanticChunker fails
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            self.fallback_text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
        except ImportError:
            self.fallback_text_splitter = None
            self.logger.warning("Could not import RecursiveCharacterTextSplitter as fallback")
        
        # Check if collection exists, create only if it doesn't
        collection_name = "extracted_content"
        try:
            # Get existing collections - in ChromaDB v0.6.0, list_collections returns string names
            existing_collections = self.client.list_collections()
            
            # In v0.6.0, we simply check if the name is in the list of collection names
            collection_exists = collection_name in [coll for coll in existing_collections]
            
            if collection_exists:
                # Retrieve the existing collection
                self.collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                self.logger.info(f"Retrieved existing collection: {collection_name}")
                
                # Log the number of documents in the collection
                try:
                    doc_count = self.collection.count()
                    self.logger.info(f"Collection has {doc_count} documents")
                except Exception as e:
                    self.logger.warning(f"Could not count documents: {str(e)}")
            else:
                # Create a new collection if it doesn't exist
                self.collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                self.logger.info(f"Created new collection: {collection_name}")
        except Exception as e:
            self.logger.error(f"Error accessing collection: {str(e)}")
            # Fallback: try to get the collection first, create only if that fails
            try:
                self.collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                self.logger.info(f"Retrieved existing collection in fallback: {collection_name}")
            except Exception:
                # Create a new collection only if get_collection fails
                self.collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                self.logger.info(f"Created new collection in fallback: {collection_name}")

    def store_document(self, text: str, metadata: Dict[str, str]) -> bool:
        """
        Store document in vector database, splitting it into chunks.
        
        Args:
            text (str): The text content to store
            metadata (Dict[str, str]): Metadata about the document including:
                - type: 'document', 'url', or 'text'
                - name: filename or identifier
                - url: (optional) URL if source is a webpage
                - timestamp: (optional) when the content was added
                
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure metadata has required fields
            if 'type' not in metadata:
                metadata['type'] = 'document'
            if 'name' not in metadata:
                metadata['name'] = f"document_{str(uuid.uuid4())[:8]}"
            
            # Ensure there's an ID field for source filtering
            if 'id' not in metadata:
                metadata['id'] = str(uuid.uuid4())
            
            # Try to split text using SemanticChunker
            try:
                chunks = self.text_splitter.create_documents([text])
                chunks = [chunk.page_content for chunk in chunks]
                self.logger.info(f"Split document '{metadata['name']}' into {len(chunks)} chunks using SemanticChunker")
            except Exception as semantic_error:
                self.logger.warning(f"SemanticChunker failed: {semantic_error}. Falling back to RecursiveCharacterTextSplitter.")
                # Fall back to RecursiveCharacterTextSplitter if SemanticChunker fails
                if self.fallback_text_splitter:
                    chunks = self.fallback_text_splitter.split_text(text)
                    self.logger.info(f"Split document '{metadata['name']}' into {len(chunks)} chunks using fallback splitter")
                else:
                    # If no fallback, create a single chunk
                    chunks = [text]
                    self.logger.warning("No fallback splitter available. Using entire text as a single chunk.")
            
            # Store each chunk with the same metadata but unique ID
            ids = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                # Create a copy of metadata for each chunk
                chunk_metadata = metadata.copy()
                # Add chunk info to metadata
                chunk_metadata['chunk'] = i
                chunk_metadata['total_chunks'] = len(chunks)
                
                # Generate unique ID for each chunk
                chunk_id = f"{metadata.get('name', 'doc')}_{i}_{str(uuid.uuid4())}"
                
                ids.append(chunk_id)
                metadatas.append(chunk_metadata)
            
            # Add chunks to the database in smaller batches to avoid batch size limits
            # ChromaDB typically has a limit of around 100-200 items per batch
            MAX_BATCH_SIZE = 100  # Conservative batch size to avoid errors
            
            # Process in batches
            for i in range(0, len(chunks), MAX_BATCH_SIZE):
                end_idx = min(i + MAX_BATCH_SIZE, len(chunks))
                self.logger.info(f"Adding batch {i//MAX_BATCH_SIZE + 1} of {math.ceil(len(chunks)/MAX_BATCH_SIZE)}")
                
                # Add this batch to the collection
                self.collection.add(
                    documents=chunks[i:end_idx],
                    ids=ids[i:end_idx],
                    metadatas=metadatas[i:end_idx]
                )
            
            return True
        except Exception as e:
            self.logger.error(f"Error storing document: {str(e)}")
            return False

    def store_text(self, text: str, title: str = None) -> bool:
        """
        Store copy-pasted text in vector database.
        
        Args:
            text (str): The text content to store
            title (str, optional): A title or identifier for the text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate a title if not provided
            if not title:
                # Use first 50 characters of text as title
                title = text[:50] + "..." if len(text) > 50 else text
            
            # Create metadata for the text
            metadata = {
                'type': 'text',
                'name': title,
                'timestamp': str(uuid.uuid1())  # Using UUID1 for timestamp-based ordering
            }
            
            # Store the text using the general store_document method
            return self.store_document(text, metadata)
            
        except Exception as e:
            self.logger.error(f"Error storing text: {str(e)}")
            return False

    def similarity_search(self, 
                        query: str, 
                        n_results: int = 5,
                        metadata_filter: Optional[Dict] = None) -> List[Dict]:
        """Perform similarity search using ChromaDB's built-in functionality."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=metadata_filter
            )
            
            retrieved_chunks = []
            for i in range(len(results['documents'][0])):
                chunk = {
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i]
                }
                retrieved_chunks.append(chunk)
            
            return retrieved_chunks
            
        except Exception as e:
            self.logger.error(f"Error performing similarity search: {str(e)}")
            return []

    def get_relevant_context(self, query: str, max_tokens: int = 8000, source_ids=None) -> str:
        """Get relevant context using ChromaDB's similarity search."""
        try:
            # Check if query is a greeting, small talk, or system command
            if self._is_greeting_or_smalltalk(query):
                self.logger.info(f"Query '{query}' detected as greeting or small talk - no context needed")
                return ""
                
            # Create a metadata filter if source_ids is provided
            metadata_filter = None
            if source_ids and len(source_ids) > 0:
                # Use the 'id' field which is stored in the metadata
                metadata_filter = {"id": {"$in": source_ids}}
                self.logger.info(f"Filtering context by source IDs: {source_ids}")
                self.logger.info(f"Using metadata filter: {metadata_filter}")
            else:
                self.logger.info("No source IDs provided for filtering")
            
            # Start with high number of results to ensure we get something relevant
            # We'll filter and sort later
            initial_n_results = 20 if metadata_filter else 30
            
            # Pass the filter to similarity_search
            chunks = self.similarity_search(query, n_results=initial_n_results, metadata_filter=metadata_filter)
            
            if not chunks:
                # For topic search, try again without metadata filter if we got no results with filter
                if metadata_filter and 'topic' in query.lower():
                    self.logger.warning(f"No chunks found with source filter. Trying again without filter for topic: {query}")
                    chunks = self.similarity_search(query, n_results=initial_n_results)
                
                # If still no chunks, log and return empty
                if not chunks:
                    self.logger.warning(f"No chunks found for query: {query}")
                    # Get collection stats to help diagnose
                    try:
                        collection_stats = self.collection.count()
                        self.logger.info(f"Collection has {collection_stats} documents")
                    except:
                        self.logger.info("Could not get collection stats")
                    return ""
            
            # Filter chunks based on relevance threshold
            # ChromaDB distances range from 0 to 2, with lower being better (0 = perfect match)
            relevance_threshold = 1.8  # Increased from 0.6 to be more permissive
            
            # Filter chunks by relevance score
            relevant_chunks = []
            # Log some distances for debugging
            distance_stats = []
            
            for chunk in chunks:
                distance = chunk.get('distance', 1.0)
                distance_stats.append(distance)
                if distance <= relevance_threshold:
                    relevant_chunks.append(chunk)
            
            # Log relevance filtering results with distance statistics
            avg_distance = sum(distance_stats) / len(distance_stats) if distance_stats else 0
            min_distance = min(distance_stats) if distance_stats else 0
            self.logger.info(f"Distance stats - Min: {min_distance:.4f}, Avg: {avg_distance:.4f}, Threshold: {relevance_threshold}")
            self.logger.info(f"Relevance filtering: {len(relevant_chunks)}/{len(chunks)} chunks passed threshold {relevance_threshold}")
            
            # Add special case for queries directly about document topics
            if not relevant_chunks:
                # Get all document names for topic matching
                doc_names = []
                for chunk in chunks:
                    if isinstance(chunk, dict) and 'metadata' in chunk:
                        name = chunk['metadata'].get('name', '').lower()
                        if name and name not in doc_names:
                            doc_names.append(name)
                
                # Check if query mentions any document name directly
                query_lower = query.lower()
                for name in doc_names:
                    # Clean up name (remove file extensions, etc.)
                    clean_name = name.split('.')[0].strip()
                    if clean_name and (clean_name in query_lower or query_lower in clean_name):
                        self.logger.info(f"Query mentions document name '{clean_name}' - using chunks despite threshold")
                        # Use the closest chunks when direct topic match is detected
                        sorted_chunks = sorted(chunks, key=lambda x: x.get('distance', 1.0))
                        relevant_chunks = sorted_chunks[:5]  # Use top 5 closest chunks
                        break
                        
                # If we still have no relevant chunks, return empty string
                if not relevant_chunks:
                    self.logger.info(f"No chunks passed relevance threshold for query: '{query}'")
                    return ""
            
            chunks = relevant_chunks  # Continue with only the relevant chunks
            
            # Analyze content relevance using text overlap
            if not self._is_query_related_to_chunks(query, chunks):
                self.logger.info(f"Query '{query}' does not appear related to retrieved chunks")
                return ""
            
            # Special handling for URL queries
            if "url" in query.lower():
                urls = []
                for chunk in chunks:
                    if isinstance(chunk, dict) and 'metadata' in chunk:
                        metadata = chunk['metadata']
                        if isinstance(metadata, dict) and 'url' in metadata:
                            urls.append(metadata['url'])
                if urls:
                    # Remove duplicates while preserving order
                    unique_urls = []
                    for url in urls:
                        if url not in unique_urls:
                            unique_urls.append(url)
                    return "\n".join(f"- {url}" for url in unique_urls)
                return "No URLs found in the stored documents."
                
            # Regular context retrieval
            try:
                # Group chunks by source name and try to order them correctly
                source_groups = {}
                for chunk in chunks:
                    if isinstance(chunk, dict) and 'text' in chunk and chunk['text']:
                        metadata = chunk.get('metadata', {})
                        source_name = metadata.get('name', 'Unknown Source')
                        chunk_info = {
                            'text': chunk['text'],
                            'chunk_index': metadata.get('chunk', 0),
                            'distance': chunk.get('distance', 1.0)  # Lower distance is better
                        }
                        
                        if source_name not in source_groups:
                            source_groups[source_name] = []
                        
                        source_groups[source_name].append(chunk_info)
                
                # Log the number of chunks found for each source
                for source_name, chunks_info in source_groups.items():
                    self.logger.info(f"Found {len(chunks_info)} chunks for source: {source_name}")
                
                # Format each source's content separately
                formatted_sources = []
                for source_name, chunks_info in source_groups.items():
                    # First sort by similarity for best content
                    sorted_by_relevance = sorted(chunks_info, key=lambda x: x['distance'])
                    
                    # Then re-sort by chunk index within the top N most relevant chunks
                    # to maintain document coherence while prioritizing relevant content
                    top_n = min(10, len(sorted_by_relevance))
                    top_chunks = sorted_by_relevance[:top_n]
                    ordered_chunks = sorted(top_chunks, key=lambda x: x['chunk_index'])
                    
                    # Get texts in sorted order
                    texts = [chunk['text'] for chunk in ordered_chunks]
                    
                    # Remove duplicate chunks (might happen with overlapping content)
                    unique_texts = []
                    for text in texts:
                        if not any(text in t for t in unique_texts):
                            unique_texts.append(text)
                    
                    # Join chunks with proper spacing
                    source_content = "\n\n".join(unique_texts)
                    
                    # Limit each source's content length 
                    max_source_length = max_tokens // len(source_groups)
                    if len(source_content) > max_source_length:
                        source_content = source_content[:max_source_length] + "..."
                    
                    # Add source heading
                    formatted_sources.append(f"### {source_name}\n\n{source_content}")
                
                # Join all sources with clear separation
                context = "\n\n---\n\n".join(formatted_sources)
                
                # Final length check
                if len(context) > max_tokens:
                    context = context[:max_tokens] + "..."
                
                # Log some statistics about the returned context
                word_count = len(context.split())
                self.logger.info(f"Returning context with {word_count} words from {len(source_groups)} sources")
                
                return context
                    
            except Exception as join_error:
                self.logger.error(f"Error joining chunks: {str(join_error)}")
                # Fallback to a simpler approach
                context = "\n\n".join(str(chunk.get('text', '')) for chunk in chunks if isinstance(chunk, dict))
                if not context:
                    return ""
                
                # Limit context length
                if len(context) > max_tokens:
                    context = context[:max_tokens] + "..."
                
                return context
            
        except Exception as e:
            self.logger.error(f"Error retrieving documents: {str(e)}")
            return ""
            
    def _is_greeting_or_smalltalk(self, text: str) -> bool:
        """
        Check if the input is a greeting, small talk, or system command.
        
        Args:
            text (str): The text to check
            
        Returns:
            bool: True if the text is a greeting or small talk, False otherwise
        """
        # Convert to lowercase for case-insensitive matching
        text = text.lower().strip()
        
        # Check if text is empty or too short (likely not a content query)
        if not text or len(text) < 4:
            return True
            
        # Common greetings and small talk phrases
        greetings = [
            'hi', 'hello', 'hey', 'hii', 'hiii', 'hiiii',
            'hi there', 'hello there', 'hey there',
            'good morning', 'good afternoon', 'good evening',
            'how are you', 'how\'s it going', 'what\'s up',
            'nice to meet you', 'pleased to meet you',
            'thanks', 'thank you', 'ty', 'thx', 'bye', 'goodbye'
        ]
        
        # Check for exact matches with greetings
        for greeting in greetings:
            if text == greeting or text.startswith(greeting + ' '):
                return True
                
        # If text ends with ? and is short, likely a small talk question
        if text.endswith('?') and len(text) < 15:
            questions = ['how are you', 'what is your name', 'who are you']
            for q in questions:
                if q in text:
                    return True
                    
        return False
        
    def _is_query_related_to_chunks(self, query: str, chunks: List[Dict]) -> bool:
        """
        Check if the query is related to the retrieved chunks.
        
        Args:
            query (str): The user's query
            chunks (List[Dict]): List of retrieved chunks with text and metadata
            
        Returns:
            bool: True if the query appears related to the chunks, False otherwise
        """
        # Skip this check for long queries (they're likely not greetings/small talk)
        if len(query) > 25:
            return True
            
        # Extract all chunk texts
        all_chunk_text = " ".join([chunk.get('text', '') for chunk in chunks if isinstance(chunk, dict)])
        
        # Normalize query for comparison
        query_words = set(query.lower().split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'like'}
        query_words = query_words - stop_words
        
        # Query is too short after removing stop words
        if len(query_words) < 1:
            return False
            
        # Check if any significant query word appears in the chunks
        found_match = False
        for word in query_words:
            if len(word) > 3 and word in all_chunk_text.lower():  # Only check words with 4+ chars
                found_match = True
                break
                
        return found_match

    def clear_collection(self) -> bool:
        """Clear all documents from collection."""
        try:
            # Try first approach - using where parameter with None
            try:
                self.collection.delete(where=None)
            except Exception:
                # If that fails, try the second approach - getting all IDs and deleting them
                try:
                    # Get all document IDs
                    results = self.collection.get()
                    if results and 'ids' in results and results['ids']:
                        self.collection.delete(ids=results['ids'])
                    else:
                        # Collection might be empty already
                        pass
                except Exception as inner_e:
                    # Third approach - recreate the collection
                    self.logger.warning(f"Falling back to collection recreation: {inner_e}")
                    try:
                        self.client.delete_collection("extracted_content")
                        self.collection = self.client.create_collection(
                            name="extracted_content",
                            embedding_function=self.embedding_function
                        )
                    except Exception as recreate_error:
                        self.logger.error(f"Failed to recreate collection: {recreate_error}")
                        return False
                
            self.logger.info("Successfully cleared the collection")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing collection: {str(e)}")
            return False

# Create singleton instance
vector_store = VectorStore()