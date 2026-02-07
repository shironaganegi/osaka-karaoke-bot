import google.generativeai as genai
import logging
from shared.config import config
import time
import re

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        if not config.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is missing!")
            raise ValueError("GEMINI_API_KEY is not set.")
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Priority list of models to try
        self.models_to_try = [
            'gemini-2.0-flash',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-1.0-pro'
        ]

    def generate_content(self, prompt: str) -> str:
        """
        Generates content using Gemini with exponential backoff and model fallback.
        """
        for model_name in self.models_to_try:
            logger.info(f"Attempting valid generation with model: {model_name}")
            model = genai.GenerativeModel(model_name)
            
            # Retry loop for a specific model
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = model.generate_content(prompt)
                    if response.text:
                        return response.text
                except Exception as e:
                    error_msg = str(e)
                    wait_time = 2 ** (attempt + 2) # Start at 4s, then 8s, 16s
                    
                    # Detect 429 Rate Limit
                    if "429" in error_msg or "Quota exceeded" in error_msg:
                        logger.warning(f"Rate Limit hit for {model_name}. Switching to next model...")
                        # If rate limited, don't spam retry this model, break and go to next model immediately
                        # But maybe we should sleep a bit before next model just in case it's account-wide
                        time.sleep(10) 
                        break 
                    
                    # Check if connection error or temporary server error
                    if "500" in error_msg or "503" in error_msg:
                         logger.warning(f"Server Error ({model_name}). Retrying in {wait_time}s...")
                         time.sleep(wait_time)
                         continue

                    logger.warning(f"Gemini API Error ({model_name} - Attempt {attempt+1}): {e}.")
                    time.sleep(wait_time)
            
            # If we exited the loop naturally (retries exhausted) or via break (rate limit), we try the next model.

        logger.error("All Gemini models and retries failed.")
        return ""

    def load_prompt(self, filename: str) -> str:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {filename}")
            return ""

# Singleton
llm_client = LLMClient()
