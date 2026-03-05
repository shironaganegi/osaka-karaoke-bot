import os
import time
import logging
from datetime import datetime, timedelta
from src.shared.config import config
from src.shared.utils import setup_logging

# Setup logging
logger = setup_logging(__name__)

def clean_old_files(directory, days=30):
    """
    Deletes files in the specified directory that are older than the given number of days.
    """
    if not os.path.exists(directory):
        logger.info(f"Directory {directory} does not exist. Skipping cleanup.")
        return

    now = time.time()
    cutoff = now - (days * 86400) # 86400 seconds in a day
    
    deleted_count = 0
    logger.info(f"Starting cleanup in {directory} (Removing files older than {days} days)")

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        # Skip directories
        if os.path.isdir(filepath):
            continue
            
        # Check modification time
        file_mtime = os.path.getmtime(filepath)
        
        if file_mtime < cutoff:
            try:
                os.remove(filepath)
                logger.info(f"Deleted old file: {filename}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {filename}: {e}")

    logger.info(f"Cleanup finished. Deleted {deleted_count} files.")

def clean_error_files(directory):
    """
    Deletes files that contain error messages indicating generation failure.
    """
    if not os.path.exists(directory): return
    
    logger.info(f"Checking for failed articles in {directory}...")
    deleted = 0
    for filename in os.listdir(directory):
        if not filename.endswith(".md"): continue
        filepath = os.path.join(directory, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for error signature
            if "記事生成に失敗しました" in content or "ModelError" in content or "Quota exceeded" in content:
                os.remove(filepath)
                logger.warning(f"Deleted failed article: {filename}")
                deleted += 1
        except Exception as e:
            logger.error(f"Error checking file {filename}: {e}")
            
    logger.info(f"Error cleanup finished. Deleted {deleted} failed files.")

if __name__ == "__main__":
    # Clean articles and generated images older than 30 days
    clean_old_files(config.ARTICLES_DIR, days=30)
    # Use config.DATA_DIR + images manually or extend config later if 'images' becomes standard
    images_dir = os.path.join(config.DATA_DIR, "images")
    clean_old_files(images_dir, days=30)
    
    # Clean failed articles (both in internal storage and Hugo site)
    clean_error_files(config.ARTICLES_DIR)
    
    # Clean English articles directory
    clean_old_files(config.EN_ARTICLES_DIR, days=30)
    clean_error_files(config.EN_ARTICLES_DIR)

    clean_error_files(config.WEBSITE_CONTENT_DIR)
