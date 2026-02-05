import os
import time
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_old_files(directory, days=30):
    """
    Deletes files in the specified directory that are older than the given number of days.
    """
    if not os.path.exists(directory):
        logging.info(f"Directory {directory} does not exist. Skipping cleanup.")
        return

    now = time.time()
    cutoff = now - (days * 86400) # 86400 seconds in a day
    
    deleted_count = 0
    logging.info(f"Starting cleanup in {directory} (Removing files older than {days} days)")

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
                logging.info(f"Deleted old file: {filename}")
                deleted_count += 1
            except Exception as e:
                logging.error(f"Failed to delete {filename}: {e}")

    logging.info(f"Cleanup finished. Deleted {deleted_count} files.")

if __name__ == "__main__":
    # Define directories to clean
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    drafts_dir = os.path.join(base_dir, "drafts")
    data_dir = os.path.join(base_dir, "data")
    images_dir = os.path.join(data_dir, "images")

    # Clean drafts and generated images older than 30 days
    clean_old_files(drafts_dir, days=30)
    clean_old_files(images_dir, days=30)
