import threading
import subprocess
import sys
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_app():
    """Run the Flask application (app.py)"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_dir)  # Change to script directory
        subprocess.run([sys.executable, 'app.py'])
    except Exception as e:
        logger.error(f"Error running app.py: {e}")

def run_custom_db2():
    """Run the database management script (custom_db2.py)"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_dir)  # Change to script directory
        subprocess.run([sys.executable, 'custom_db2.py'])
    except Exception as e:
        logger.error(f"Error running custom_db2.py: {e}")

def main():
    try:
        # Create threads for both applications
        app_thread = threading.Thread(target=run_app, name='AppThread')
        db_thread = threading.Thread(target=run_custom_db2, name='DBThread')

        # Start both threads
        logger.info("Starting application threads...")
        app_thread.start()
        db_thread.start()

        # Wait for both threads to complete
        app_thread.join()
        db_thread.join()

    except KeyboardInterrupt:
        logger.info("Shutting down threads...")
    except Exception as e:
        logger.error(f"Error in main thread: {e}")

if __name__ == "__main__":
    main()