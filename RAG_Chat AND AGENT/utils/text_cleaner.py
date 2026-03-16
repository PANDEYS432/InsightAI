import re
import unicodedata
from typing import List, Dict
from pathlib import Path
import html
from bs4 import BeautifulSoup
import logging

class TextCleaner:
    def __init__(self):
        # Initialize script-specific patterns
        self.script_patterns = {
            'devanagari': {
                'script_range': r'[\u0900-\u097F\u1CD0-\u1CFF]',
                'vowel_signs': r'\u093E-\u094C\u094E\u0955\u0962\u0963',
                'combining_marks': r'\u0900-\u0903\u093C\u094D'
            },
            'latin': {
                'script_range': r'[A-Za-z]',
                'combining_marks': r'\u0300-\u036F'
            },
            'chinese': {
                'script_range': r'[\u4E00-\u9FFF]',
                'combining_marks': r''
            },
            'arabic': {
                'script_range': r'[\u0600-\u06FF\u0750-\u077F]',
                'combining_marks': r'\u064B-\u065F'
            }
        }
        
        # Common patterns to clean
        self.cleanup_patterns = [
            (r'\s+', ' '),                    # Multiple spaces to single space
            (r'[\r\n]+', '\n'),              # Multiple newlines to single newline
            (r'\n\s+\n', '\n\n'),           # Remove extra space between paragraphs
            (r'\t', ' '),                    # Replace tabs with spaces
            (r'[^\S\n]+', ' '),             # Multiple horizontal spaces to single space
            (r' +(?=\n)', ''),              # Remove spaces before newlines
            (r'(?<=\n) +', '')              # Remove spaces after newlines
        ]

    def clean_text(self, text: str) -> str:
        """
        Clean and format extracted text while preserving language-specific characteristics.
        """
        try:
            if not text or not isinstance(text, str):
                return ""

            # Step 1: Normalize Unicode
            text = unicodedata.normalize('NFKC', text)
            
            # Step 2: Convert HTML entities
            text = html.unescape(text)
            
            # Step 3: Remove invisible characters while preserving legitimate spaces
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
            
            # Step 4: Detect script and apply appropriate cleaning
            script = self._detect_script(text)
            text = self._clean_script_specific(text, script)
            
            # Step 5: Apply common cleanup patterns
            for pattern, replacement in self.cleanup_patterns:
                text = re.sub(pattern, replacement, text)
            
            # Step 6: Fix broken words and spacing
            text = self._fix_word_breaks(text)
            
            # Step 7: Format paragraphs and structure
            text = self._format_structure(text)
            
            return text.strip()
            
        except Exception as e:
            logging.error(f"Error cleaning text: {str(e)}")
            return text

    def _detect_script(self, text: str) -> str:
        """
        Detect the dominant script in the text.
        """
        script_counts = {}
        
        for script, patterns in self.script_patterns.items():
            count = len(re.findall(patterns['script_range'], text))
            script_counts[script] = count
            
        return max(script_counts.items(), key=lambda x: x[1])[0]

    def _clean_script_specific(self, text: str, script: str) -> str:
        """
        Apply script-specific cleaning rules.
        """
        patterns = self.script_patterns.get(script, self.script_patterns['latin'])
        
        # Preserve combining marks and vowel signs
        if patterns['combining_marks']:
            text = re.sub(
                f"({patterns['script_range']})[{patterns['combining_marks']}]*",
                lambda m: ''.join(sorted(m.group(0), key=lambda x: unicodedata.combining(x))),
                text
            )
            
        return text

    def _fix_word_breaks(self, text: str) -> str:
        """
        Fix incorrectly broken or merged words.
        """
        # Fix hyphenated word breaks
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
        
        # Fix merged words (based on camelCase)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        
        # Fix missing spaces after punctuation
        text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
        
        return text

    def _format_structure(self, text: str) -> str:
        """
        Maintain document structure and formatting.
        """
        # Preserve paragraph breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Preserve list formatting
        text = re.sub(r'(?<=\n)[-•*]\s*', '• ', text)
        
        # Preserve heading structure
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Detect possible headings (shorter lines followed by blank lines)
            if (len(line.strip()) > 0 and len(line.strip()) < 100 and
                (i == 0 or not lines[i-1].strip()) and
                (i == len(lines)-1 or not lines[i+1].strip())):
                formatted_lines.append(line.strip().title())
                formatted_lines.append('')
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    def clean_pdf_text(self, text: str) -> str:
        """
        Specific cleaning for PDF-extracted text.
        """
        # Remove PDF artifacts
        text = re.sub(r'(?:\f|\u000C)', '\n\n', text)  # Form feed characters
        text = re.sub(r'(?:\r|\u000D)', '', text)      # Carriage returns
        
        # Clean and format
        return self.clean_text(text)

    def clean_web_text(self, text: str) -> str:
        """
        Specific cleaning for web-extracted text.
        """
        # Remove common web artifacts
        text = BeautifulSoup(text, 'html.parser').get_text()
        
        # Clean and format
        return self.clean_text(text)

# Create singleton instance
text_cleaner = TextCleaner()