"""
Helper script to set up EasyOCR models
This script helps download EasyOCR models if automatic download fails
"""

import os
import ssl
import urllib.request

def setup_easyocr_models():
    """Download EasyOCR models manually if needed"""
    try:
        print("Attempting to initialize EasyOCR...")
        import easyocr
        
        # Try to create reader - this will download models if needed
        print("Initializing EasyOCR reader (this may take several minutes on first run)...")
        print("EasyOCR will download model files (~100MB) if not already present.")
        
        # Create SSL context that doesn't verify certificates (for problematic networks)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Monkey patch urllib to use our SSL context
        original_urlopen = urllib.request.urlopen
        def urlopen_with_ssl(*args, **kwargs):
            kwargs.setdefault('context', ssl_context)
            return original_urlopen(*args, **kwargs)
        urllib.request.urlopen = urlopen_with_ssl
        
        reader = easyocr.Reader(['en'], gpu=False, verbose=True)
        print("✅ EasyOCR initialized successfully!")
        print("Models are now downloaded and ready to use.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure you have internet connection")
        print("2. Check if firewall is blocking downloads")
        print("3. Try running: pip install --upgrade easyocr")
        print("4. Models will be stored in: ~/.EasyOCR/")
        return False

if __name__ == "__main__":
    setup_easyocr_models()
