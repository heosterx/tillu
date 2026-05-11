"""
Enhanced Logging with Sanitization
Removes sensitive data from logs
"""
import logging
import re
from typing import Optional

# Patterns to sanitize
SENSITIVE_PATTERNS = [
    (r'redis://[^@]*@', 'redis://***@'),
    (r'postgresql://[^@]*@', 'postgresql://***@'),
    (r'Bearer\s+[^\s]+', 'Bearer ***'),
    (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+', 'api_key=***'),
    (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', 'password=***'),
    (r'token["\']?\s*[:=]\s*["\']?[^\s"\']+', 'token=***'),
    (r'secret["\']?\s*[:=]\s*["\']?[^\s"\']+', 'secret=***'),
    (r'Authorization:\s*Bearer\s+[^\s]+', 'Authorization: Bearer ***'),
]


class SanitizedFormatter(logging.Formatter):
    """Formatter that removes sensitive data from logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with sanitization"""
        msg = super().format(record)
        
        # Sanitize message
        for pattern, replacement in SENSITIVE_PATTERNS:
            msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
        
        # Sanitize exception info
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            for pattern, replacement in SENSITIVE_PATTERNS:
                exc_text = re.sub(pattern, replacement, exc_text, flags=re.IGNORECASE)
            record.exc_text = exc_text
        
        return msg


def configure_logging(log_level: str = "INFO"):
    """Configure logging with sanitization"""
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    
    # Create formatter
    formatter = SanitizedFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)


def sanitize_error(error: Exception) -> str:
    """Sanitize error message"""
    error_str = str(error)
    
    for pattern, replacement in SENSITIVE_PATTERNS:
        error_str = re.sub(pattern, replacement, error_str, flags=re.IGNORECASE)
    
    return error_str
