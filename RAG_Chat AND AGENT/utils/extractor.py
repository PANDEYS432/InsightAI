import requests
from bs4 import BeautifulSoup
import pdfplumber
from PyPDF2 import PdfReader
import os
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse
from pathlib import Path
import logging
import fitz  # PyMuPDF
from .text_cleaner import text_cleaner
import urllib.robotparser

class ContentExtractor:
    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.supported_extensions = {'.pdf', '.txt', '.md'}

    def check_robots_txt(self, url: str) -> Tuple[bool, str]:
        """
        Check robots.txt to see if we have permission to scrape the URL.
        
        Args:
            url: The URL to check
            
        Returns:
            Tuple of (allowed, reason)
        """
        try:
            parsed_url = urlparse(url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                return False, "Invalid URL format"
                
            # Create a robots parser
            rp = urllib.robotparser.RobotFileParser()
            
            # Set the URL for the robots.txt file
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            self.logger.info(f"Checking robots.txt at {robots_url}")
            
            # Read the robots.txt file
            rp.set_url(robots_url)
            rp.read()
            
            # Check if our user agent is allowed to fetch the URL
            user_agent = "Mozilla/5.0"  # Using a common user agent
            can_fetch = rp.can_fetch(user_agent, url)
            
            if not can_fetch:
                return False, f"Access to {url} is disallowed by the website's robots.txt rules"
                
            return True, "Access is allowed by robots.txt"
            
        except Exception as e:
            self.logger.warning(f"Error checking robots.txt: {str(e)}")
            # If we can't check robots.txt, we proceed but log the error
            return True, f"Unable to check robots.txt: {str(e)}"

    def extract_website_content(self, url: str) -> str:
        """Extract and clean text content from a website URL or a direct link to a document."""
        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("Invalid URL format")
                
            # Check robots.txt first
            allowed, reason = self.check_robots_txt(url)
            if not allowed:
                raise ValueError(reason)

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': '*',
                'Accept-Charset': 'UTF-8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Check if the URL points to a supported document type
            content_type = response.headers.get('Content-Type', '').lower()
            url_path = parsed_url.path.lower()
            
            # Determine if this is a direct document link by content type or file extension
            is_pdf = 'application/pdf' in content_type or url_path.endswith('.pdf')
            is_txt = 'text/plain' in content_type or url_path.endswith('.txt')
            is_md = 'text/markdown' in content_type or url_path.endswith('.md')
            
            # Handle document file types
            if is_pdf or is_txt or is_md:
                import tempfile
                
                # Determine file extension
                if is_pdf:
                    suffix = '.pdf'
                elif is_txt:
                    suffix = '.txt'
                elif is_md:
                    suffix = '.md'
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_path = temp_file.name
                
                self.logger.info(f"Downloaded document to temporary file: {temp_path}")
                
                try:
                    # Process according to file type
                    if is_pdf:
                        result = self.extract_pdf_text(temp_path)
                    elif is_txt:
                        result = self.extract_txt_text(temp_path)
                    elif is_md:
                        result = self.extract_md_text(temp_path)
                    
                    # Clean up the temporary file
                    os.remove(temp_path)
                    self.logger.info(f"Processed document from URL: {url}")
                    return result
                    
                except Exception as doc_err:
                    # Clean up the temporary file even if processing fails
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise ValueError(f"Error processing document from URL: {str(doc_err)}")
            
            # If not a document, process as a regular web page
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check if this is a Wikipedia page
            is_wikipedia = 'wikipedia.org' in parsed_url.netloc
            
            if is_wikipedia:
                return self._extract_wikipedia_content(soup, url)
            
            # For regular (non-Wikipedia) web pages
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'meta', 'link', 'iframe']):
                element.decompose()
            
            # Extract text with structure preservation
            content_elements = []
            
            # Process headings
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = heading.get_text(strip=True)
                if text:
                    level = int(heading.name[1])
                    prefix = '#' * level
                    content_elements.append(f"\n{prefix} {text}\n")
            
            # Process paragraphs and lists
            for element in soup.find_all(['p', 'li', 'div']):
                text = element.get_text(strip=True)
                if text:
                    if element.name == 'li':
                        content_elements.append(f"• {text}")
                    else:
                        content_elements.append(text)
            
            # Join and clean the extracted text
            raw_text = '\n'.join(content_elements)
            cleaned_text = text_cleaner.clean_web_text(raw_text)
            
            if not cleaned_text:
                raise ValueError("No content could be extracted from the URL")
            
            return cleaned_text
            
        except Exception as e:
            self.logger.error(f"Error extracting website content: {str(e)}")
            raise ValueError(f"Error extracting website content: {str(e)}")
        
    def _extract_wikipedia_content(self, soup, url):
        """Extract content from Wikipedia pages with special handling."""
        self.logger.info(f"Extracting content from Wikipedia page: {url}")
        
        # Find the main content container
        content_div = soup.find('div', class_='mw-parser-output')
        if not content_div:
            self.logger.warning("Could not find Wikipedia main content container")
            # Fall back to the body if main container isn't found
            content_div = soup.find('body')
        
        if not content_div:
            raise ValueError("Could not extract Wikipedia content structure")
        
        # Remove edit section links, references, navigation boxes, and other irrelevant elements
        elements_to_remove = [
            '.mw-editsection',  # Edit section links
            '.reference',  # Citations
            '.reflist',  # Reference lists
            '.navbox',  # Navigation boxes
            '.vertical-navbox',  # Vertical navigation boxes
            '.noprint',  # Non-printable elements
            '.metadata',  # Metadata boxes
            '.tmulti',  # Multiple-image templates
            '#catlinks',  # Category links
            '.portal',  # Portal links
            '.hatnote',  # Hatnotes (disambiguation notes)
            '.error',  # Error messages
            '.mbox-small',  # Small message boxes
            '#coordinates',  # Geographical coordinates
        ]
        
        for selector in elements_to_remove:
            for element in content_div.select(selector):
                element.decompose()
        
        # Extract structured content
        extracted_content = []
        
        # Add the page title
        title = soup.find('h1', id='firstHeading')
        if title:
            title_text = title.get_text(strip=True)
            extracted_content.append(f"# {title_text}\n")
        
        # Process content sections
        for element in content_div.find_all(['p', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'dl', 'dt', 'dd', 'table']):
            if element.name.startswith('h'):
                # Process headings
                level = int(element.name[1])
                heading_text = element.get_text(strip=True)
                if heading_text and not heading_text.lower() in ['contents', 'references', 'see also', 'external links']:
                    prefix = '#' * level
                    extracted_content.append(f"\n{prefix} {heading_text}\n")
            
            elif element.name == 'table':
                # Process tables (simplified extraction)
                caption = element.find('caption')
                if caption:
                    extracted_content.append(f"\nTable: {caption.get_text(strip=True)}\n")
                
                # Extract table data
                for row in element.find_all('tr'):
                    row_cells = []
                    # Include both th and td cells
                    for cell in row.find_all(['th', 'td']):
                        cell_text = cell.get_text(strip=True).replace('\n', ' ')
                        if cell_text:
                            row_cells.append(cell_text)
                    
                    if row_cells:
                        extracted_content.append(' | '.join(row_cells))
            
            elif element.name == 'li':
                # Process list items
                text = element.get_text(strip=True)
                if text:
                    extracted_content.append(f"• {text}")
            
            elif element.name in ['dt', 'dd']:
                # Process definition lists
                text = element.get_text(strip=True)
                if text:
                    prefix = '   ' if element.name == 'dd' else ''
                    extracted_content.append(f"{prefix}{text}")
            
            else:
                # Process paragraphs and other text elements
                text = element.get_text(strip=True)
                if text:
                    extracted_content.append(text)
        
        # Join with appropriate spacing
        raw_text = '\n'.join(extracted_content)
        
        # Process infobox data if present
        infobox = soup.find('table', class_='infobox')
        if infobox:
            infobox_data = ["## Infobox"]
            for row in infobox.find_all('tr'):
                head = row.find('th')
                data = row.find('td')
                if head and data:
                    head_text = head.get_text(strip=True)
                    data_text = data.get_text(strip=True)
                    if head_text and data_text:
                        infobox_data.append(f"{head_text}: {data_text}")
            
            # Insert infobox after title
            if len(infobox_data) > 1:
                raw_text = raw_text.split('\n', 1)[0] + '\n' + '\n'.join(infobox_data) + '\n\n' + raw_text.split('\n', 1)[1]
        
        # Clean the text
        cleaned_text = text_cleaner.clean_text(raw_text)
        
        # Log extraction stats
        word_count = len(cleaned_text.split())
        self.logger.info(f"Extracted {word_count} words from Wikipedia page")
        
        return cleaned_text

    def extract_pdf_text(self, file_path: str) -> str:
        """Extract and clean text from PDF file using multiple methods."""
        try:
            text_content = []
            
            # Method 1: PyMuPDF (best for PDFs with complex layouts)
            try:
                doc = fitz.open(file_path)
                for page in doc:
                    text = page.get_text()
                    if text.strip():
                        text_content.append(text.strip())
                doc.close()
            except Exception as e:
                self.logger.warning(f"PyMuPDF extraction failed: {str(e)}")
            
            # Method 2: pdfplumber (good for tables and structured content)
            if not text_content:
                try:
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                text_content.append(text.strip())
                except Exception as e:
                    self.logger.warning(f"pdfplumber extraction failed: {str(e)}")
            
            # Method 3: PyPDF2 (fallback)
            if not text_content:
                try:
                    with open(file_path, 'rb') as file:
                        reader = PdfReader(file)
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                text_content.append(text.strip())
                except Exception as e:
                    self.logger.warning(f"PyPDF2 extraction failed: {str(e)}")
            
            # Method 4: OCR (last resort for scanned documents)
            
            
            if not text_content:
                raise ValueError("No text could be extracted from the PDF using any method")
            
            # Join and clean the extracted text
            raw_text = '\n\n'.join(text_content)
            cleaned_text = text_cleaner.clean_pdf_text(raw_text)
            
            return cleaned_text
            
        except Exception as e:
            self.logger.error(f"Error extracting PDF text: {str(e)}")
            raise ValueError(f"Error extracting PDF text: {str(e)}")

    def extract_txt_text(self, file_path: str) -> str:
        """Extract and clean text from TXT file with encoding detection."""
        encodings = [
            'utf-8', 'utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be',
            'latin-1', 'iso-8859-1', 'cp1252', 'ascii'
        ]
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    raw_text = file.read().strip()
                    if raw_text:
                        # Clean the extracted text
                        cleaned_text = text_cleaner.clean_text(raw_text)
                        return cleaned_text
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.warning(f"Error with {encoding}: {str(e)}")
                continue
        
        raise ValueError("Could not read the text file with any supported encoding")

    def extract_md_text(self, file_path: str) -> str:
        """Extract and clean text from MD file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                raw_text = file.read().strip()
                if raw_text:
                    # Clean the extracted text while preserving markdown formatting
                    cleaned_text = text_cleaner.clean_text(raw_text)
                    return cleaned_text
                else:
                    raise ValueError("Empty markdown file")
        except UnicodeDecodeError:
            # Try with a different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='latin-1') as file:
                raw_text = file.read().strip()
                if raw_text:
                    cleaned_text = text_cleaner.clean_text(raw_text)
                    return cleaned_text
                else:
                    raise ValueError("Empty markdown file")
        except Exception as e:
            self.logger.error(f"Error extracting MD text: {str(e)}")
            raise ValueError(f"Error extracting MD text: {str(e)}")

    def process_document(self, file_path: str) -> str:
        """Process uploaded document and extract clean text."""
        if not os.path.exists(file_path):
            raise ValueError("File not found")
        
        try:
            extension = Path(file_path).suffix.lower()
            if extension not in self.supported_extensions:
                raise ValueError(f"Unsupported file format. Supported formats: {', '.join(self.supported_extensions)}")
            
            if extension == '.pdf':
                return self.extract_pdf_text(file_path)
            elif extension == '.txt':
                return self.extract_txt_text(file_path)
            elif extension == '.md':
                return self.extract_md_text(file_path)
            
        except Exception as e:
            self.logger.error(f"Error processing document: {str(e)}")
            raise ValueError(f"Error processing document: {str(e)}")

# Create singleton instance
extractor = ContentExtractor()