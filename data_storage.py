"""
This file contains functions for handling data storage and retrieval.
For simplicity, we're using JSON files for storage, but in a production environment,
you might want to use a proper database.
"""

import os
import json
import logging
import time
import fcntl
import errno
from typing import Dict, Any, Optional, IO

logger = logging.getLogger(__name__)

# File lock timeout in seconds
LOCK_TIMEOUT = 5

def ensure_data_directory_exists() -> None:
    """Ensure that the data directory and subdirectories exist"""
    # Create main data directory
    if not os.path.exists("data"):
        logger.info("Creating main data directory")
        os.makedirs("data")
        
    # Create backup directory for data exports
    backup_dir = os.path.join("data", "backups")
    if not os.path.exists(backup_dir):
        logger.info(f"Creating backup directory: {backup_dir}")
        os.makedirs(backup_dir)
        
    # Set appropriate permissions
    try:
        os.chmod("data", 0o755)  # rwxr-xr-x
        os.chmod(backup_dir, 0o755)  # rwxr-xr-x
    except Exception as e:
        logger.warning(f"Could not set directory permissions: {e}")

def acquire_lock(file_handle: IO, exclusive: bool = False) -> bool:
    """
    Acquire a lock on a file handle
    
    Args:
        file_handle: The file handle to lock
        exclusive: Whether to acquire an exclusive (write) lock or shared (read) lock
        
    Returns:
        True if lock was acquired, False if timed out or error
    """
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    
    # Try to acquire the lock with a timeout
    start_time = time.time()
    while True:
        try:
            fcntl.flock(file_handle, lock_type | fcntl.LOCK_NB)
            return True
        except IOError as e:
            # Retry if resource temporarily unavailable
            if e.errno == errno.EAGAIN or e.errno == errno.EACCES:
                if time.time() - start_time < LOCK_TIMEOUT:
                    time.sleep(0.1)  # Short sleep before retry
                    continue
                else:
                    logger.error(f"Timed out waiting for file lock ({LOCK_TIMEOUT}s)")
                    return False
            # Otherwise, it's an unhandled error
            logger.error(f"Error acquiring file lock: {e}")
            return False
    
    return False

def release_lock(file_handle: IO) -> bool:
    """Release a lock on a file handle"""
    try:
        fcntl.flock(file_handle, fcntl.LOCK_UN)
        return True
    except IOError as e:
        logger.error(f"Error releasing file lock: {e}")
        return False

def load_json_file(file_path: str, default_value: Any = None) -> Any:
    """Load data from a JSON file with file locking for safe concurrent access"""
    if default_value is None:
        default_value = {}
    
    try:
        # Create parent directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        if os.path.exists(file_path):
            # Open the file with read access
            with open(file_path, 'r', encoding='utf-8') as f:
                # Acquire a shared lock for reading
                if acquire_lock(f, exclusive=False):
                    try:
                        data = json.load(f)
                        return data
                    finally:
                        # Always release the lock
                        release_lock(f)
                else:
                    logger.warning(f"Failed to acquire lock for reading {file_path}, returning default")
                    return default_value
        else:
            return default_value
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON file {file_path}: {e}")
        return default_value
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        return default_value

def save_json_file(file_path: str, data: Any) -> bool:
    """Save data to a JSON file with file locking for safe concurrent access"""
    # Use a temporary file for safe atomic writes
    temp_file = f"{file_path}.tmp"
    
    try:
        # Create parent directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        # Write to the temporary file first
        with open(temp_file, 'w', encoding='utf-8') as f:
            # Acquire an exclusive lock for writing
            if acquire_lock(f, exclusive=True):
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()  # Ensure all data is written to disk
                    os.fsync(f.fileno())  # Flush OS file buffers
                finally:
                    # Always release the lock
                    release_lock(f)
            else:
                logger.error(f"Failed to acquire lock for writing {file_path}")
                return False
                
        # Rename the temporary file to the actual file
        # This is atomic on most filesystems
        os.rename(temp_file, file_path)
        
        return True
    except Exception as e:
        logger.error(f"Error saving file {file_path}: {e}")
        # Clean up the temporary file if it exists
        try:
            # Only attempt cleanup if temp_file exists and is a file
            if os.path.isfile(temp_file):
                os.remove(temp_file)
                logger.info(f"Cleaned up temporary file: {temp_file}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
        return False

def get_user_data(user_id: int) -> Dict[str, Any]:
    """Get data for a specific user"""
    ensure_data_directory_exists()
    
    user_data_file = f"data/user_{user_id}.json"
    return load_json_file(user_data_file, {"selected_character": None, "custom_characters": []})

def save_user_data(user_id: int, data: Dict[str, Any]) -> bool:
    """Save data for a specific user"""
    ensure_data_directory_exists()
    
    user_data_file = f"data/user_{user_id}.json"
    return save_json_file(user_data_file, data)

def get_custom_characters() -> Dict[str, Dict[str, Any]]:
    """Get all custom characters"""
    ensure_data_directory_exists()
    
    custom_characters_file = "data/custom_characters.json"
    return load_json_file(custom_characters_file)

def save_custom_characters(custom_characters: Dict[str, Dict[str, Any]]) -> bool:
    """Save all custom characters"""
    ensure_data_directory_exists()
    
    custom_characters_file = "data/custom_characters.json"
    return save_json_file(custom_characters_file, custom_characters)
