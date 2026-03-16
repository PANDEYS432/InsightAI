from .extractor import ContentExtractor
from .text_cleaner import TextCleaner
# Create singleton instances
text_cleaner = TextCleaner()
extractor = ContentExtractor()
file_handler = None  # Will be initialized with app config

__all__ = [
    'ContentExtractor',
    'FileHandler',
    'extractor',
    'file_handler',
    'text_cleaner'
]

