import os
import requests
import json
from shared.utils import load_config

# Load configuration to ensure env vars are available
load_config()

import time

def get_gemini_response(prompt, model_name, generation_config=None):
    """
    Sends a direct REST API request to Google Gemini.
    Handles authentication, JSON payload construction, and retries for 429 errors.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return None

    # Ensure model name has 'models/' prefix
    if not model_name.startswith("models/"):
        model_path = f"models/{model_name}"
    else:
        model_path = model_name
        
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    if generation_config:
        payload["generationConfig"] = generation_config

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json()
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                wait_time = (attempt + 1) * 20 # Aggressive Backoff: 20s, 40s, 60s, 80s, 100s
                print(f"Rate limited (429) for {model_name}. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
                
            # Truncate error message to avoid logging sensitive data reflected in response
            error_msg = response.text[:200] + "..." if len(response.text) > 200 else response.text
            print(f"API Error ({response.status_code}): {error_msg}")
            return None
            
        except Exception as e:
            print(f"Request failed: {e}")
            return None
            
    return None
