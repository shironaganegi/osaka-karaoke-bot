import logging
import os
import requests
import sys
from dotenv import load_dotenv

# Common User-Agent to avoid being blocked
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def setup_logging(name=None):
    """
    Sets up a standardized logger.
    If name is None, configures the root logger.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Ensure stdout handles unicode if needed (mostly for Windows consoles)
    if sys.stdout.encoding:
        sys.stdout.reconfigure(encoding='utf-8')
        
    return logging.getLogger(name if name else __name__)

def load_config():
    """
    Loads environment variables from .env file.
    """
    load_dotenv()

def safe_requests_get(url, params=None, headers=None, timeout=15):
    """
    A wrapper around requests.get with error handling and default timeout.
    """
    if headers is None:
        headers = {}
    
    # Set default User-Agent if not provided
    if 'User-Agent' not in headers:
        headers['User-Agent'] = DEFAULT_USER_AGENT

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logger = logging.getLogger(__name__)
        logger.error(f"HTTP Request failed for URL: {url} | Error: {e}")
        return None

def safe_requests_post(url, json_data=None, headers=None, timeout=15):
    """
    A wrapper around requests.post with error handling and default timeout.
    """
    if headers is None:
        headers = {}
    
    if 'User-Agent' not in headers:
        headers['User-Agent'] = DEFAULT_USER_AGENT

    try:
        response = requests.post(url, json=json_data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        logger = logging.getLogger(__name__)
        logger.error(f"HTTP Request failed for URL: {url} | Error: {e}")
        return None
