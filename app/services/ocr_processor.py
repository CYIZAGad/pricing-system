"""
OCR Processing Service
Handles image and PDF scanning with OCR, including handwritten text
"""

import io
import logging
from typing import List, Dict, Tuple, Optional
import base64
from PIL import Image
import numpy as np
import ssl
import urllib.request
import os

logger = logging.getLogger(__name__)

# Compatibility shim for Pillow 10.0.0+ (ANTIALIAS was removed)
# This helps with dependencies that might still use the old constant
try:
    # Try to access Resampling (Pillow 10.0.0+)
    if not hasattr(Image, 'Resampling'):
        # For older Pillow versions, create a compatibility shim
        Image.Resampling = type('Resampling', (), {'LANCZOS': Image.LANCZOS})()
    # Add ANTIALIAS alias for backward compatibility with dependencies
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
except AttributeError:
    # Fallback for very old Pillow versions
    try:
        Image.ANTIALIAS = Image.LANCZOS
    except:
        pass

# --- SSL workaround scoped to EasyOCR model downloads only ---
# We temporarily disable SSL verification ONLY while importing/initializing
# EasyOCR (which downloads models from GitHub on first run).
# After import, we restore the original urllib.request.urlopen.
_original_urlopen = urllib.request.urlopen

def _urlopen_with_unverified_ssl(*args, **kwargs):
    """URL open with unverified SSL context (for EasyOCR model downloads)"""
    if 'context' not in kwargs:
        ctx = ssl._create_unverified_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['context'] = ctx
    return _original_urlopen(*args, **kwargs)

# Temporarily patch for EasyOCR import
urllib.request.urlopen = _urlopen_with_unverified_ssl
_prev_env = {k: os.environ.get(k) for k in ('PYTHONHTTPSVERIFY', 'CURL_CA_BUNDLE', 'REQUESTS_CA_BUNDLE')}
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not available. Install with: pip install easyocr")
finally:
    # Restore original SSL behaviour
    urllib.request.urlopen = _original_urlopen
    for k, v in _prev_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

try:
    from pdf2image import convert_from_bytes
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
    # Try to set poppler path if it's in a common location (Windows)
    if os.name == 'nt':  # Windows
        # Common poppler installation paths
        common_paths = [
            r'C:\poppler\Library\bin',  # Standard Windows installation location
            r'C:\poppler\bin',
            r'C:\Program Files\poppler\bin',
            r'C:\Program Files (x86)\poppler\bin',
            os.path.join(os.environ.get('USERPROFILE', ''), 'poppler', 'Library', 'bin'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'poppler', 'bin'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'poppler', 'Library', 'bin'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'poppler', 'bin'),
        ]
        # Check if poppler_path is not already set
        if not hasattr(pdf2image, 'poppler_path') or not pdf2image.poppler_path:
            for path in common_paths:
                if os.path.exists(path) and os.path.exists(os.path.join(path, 'pdftoppm.exe')):
                    pdf2image.poppler_path = path
                    logger.info(f"Found Poppler at: {path}")
                    break
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available. Install with: pip install pdf2image")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Install with: pip install opencv-python")


# Singleton instance for OCRProcessor
_ocr_processor_instance = None

def get_ocr_processor():
    """Get singleton OCR processor instance (reuses initialized reader)"""
    global _ocr_processor_instance
    if _ocr_processor_instance is None:
        _ocr_processor_instance = OCRProcessor()
    return _ocr_processor_instance


class OCRProcessor:
    """Processes images and PDFs with OCR, optimized for handwritten text"""
    
    def __init__(self):
        self.easyocr_reader = None
        self._initialization_attempted = False
        self.progress_callback = None  # Callback function for progress updates
    
    def _initialize_easyocr(self):
        """Lazy initialization of EasyOCR reader"""
        if self._initialization_attempted:
            return self.easyocr_reader is not None
        
        self._initialization_attempted = True
        
        if not EASYOCR_AVAILABLE:
            logger.warning("EasyOCR is not installed")
            return False
        
        if self.easyocr_reader is not None:
            return True
        
        try:
            # SSL is already patched at module level
            # Note: First run will download model files (~100MB)
            logger.info("Initializing EasyOCR reader (this may take a moment on first run)...")
            self._update_progress(40, "Loading OCR models...")
            logger.info("Downloading model files if needed (this may take several minutes)...")
            # Settings optimized for accuracy (especially for typed/spreadsheet text)
            self.easyocr_reader = easyocr.Reader(
                ['en'], 
                gpu=False, 
                verbose=False,
                quantize=False  # Use full precision models for better accuracy
            )
            logger.info("EasyOCR initialized successfully")
            self._update_progress(45, "OCR engine ready")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            # Try to provide helpful error message
            error_msg = str(e)
            if 'SSL' in error_msg or 'certificate' in error_msg.lower():
                logger.warning("SSL certificate issue detected. EasyOCR may need internet connection to download models.")
            self.easyocr_reader = None
            return False
    
    def process_file(self, file_content: bytes, filename: str, progress_callback=None) -> Dict:
        """
        Process image or PDF file with OCR
        Returns extracted text and structured data
        progress_callback: function(percentage, message) called with progress updates
        """
        self.progress_callback = progress_callback
        try:
            # Detect file type
            filename_lower = filename.lower()
            
            if filename_lower.endswith('.pdf'):
                return self._process_pdf(file_content)
            elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')):
                return self._process_image(file_content)
            else:
                raise ValueError(f"Unsupported file type: {filename}")
        
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            raise ValueError(f"Failed to process file: {str(e)}")
        finally:
            self.progress_callback = None
    
    def _update_progress(self, percentage: int, message: str = ""):
        """Update progress if callback is set"""
        if self.progress_callback:
            try:
                self.progress_callback(percentage, message)
            except:
                pass  # Ignore callback errors
    
    def _process_pdf(self, file_content: bytes) -> Dict:
        """Process PDF file - convert to images then OCR"""
        if not PDF2IMAGE_AVAILABLE:
            raise ValueError("PDF processing requires pdf2image. Install with: pip install pdf2image")
        
        try:
            self._update_progress(5, "Converting PDF to images...")
            # Convert PDF to images
            try:
                images = convert_from_bytes(file_content, dpi=300)
            except Exception as pdf_error:
                error_msg = str(pdf_error).lower()
                if 'poppler' in error_msg or 'path' in error_msg or 'page count' in error_msg:
                    raise ValueError(
                        "PDF processing requires Poppler to be installed.\n\n"
                        "Windows Installation:\n"
                        "1. Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases/\n"
                        "2. Extract the zip file\n"
                        "3. Add the 'bin' folder to your system PATH\n"
                        "   OR set the path in code: pdf2image.pdf2image.poppler_path = r'C:\\path\\to\\poppler\\bin'\n\n"
                        "Alternative: Convert PDF to images manually and upload the images instead."
                    )
                else:
                    raise ValueError(f"Failed to process PDF: {str(pdf_error)}")
            
            total_pages = len(images)
            
            self._update_progress(10, f"Processing {total_pages} page(s)...")
            
            all_text = []
            all_structured_data = []
            
            for page_num, img in enumerate(images, 1):
                # Convert PIL image to numpy array
                img_array = np.array(img)
                
                # Resize if too large (speeds up OCR significantly)
                img_array = self._resize_image_if_needed(img_array)
                
                # Calculate progress (10% for setup, 80% for OCR, 10% for finalization)
                page_progress = 10 + int((page_num / total_pages) * 80)
                self._update_progress(page_progress, f"Scanning page {page_num} of {total_pages}...")
                
                # Extract text from this page
                page_result = self._extract_text_from_image(img_array)
                all_text.append(page_result['text'])
                all_structured_data.extend(page_result.get('structured_data', []))
            
            self._update_progress(95, "Finalizing results...")
            
            result = {
                'text': '\n'.join(all_text),
                'structured_data': all_structured_data,
                'pages': len(images),
                'success': True
            }
            
            self._update_progress(100, "Complete!")
            return result
        
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            raise
    
    def _process_image(self, file_content: bytes) -> Dict:
        """Process image file with OCR"""
        try:
            self._update_progress(5, "Loading image...")
            # Load image
            image = Image.open(io.BytesIO(file_content))
            img_array = np.array(image)
            
            self._update_progress(10, "Preparing image...")
            # Resize if too large (speeds up OCR significantly)
            img_array = self._resize_image_if_needed(img_array)
            
            self._update_progress(20, "Scanning text...")
            # Extract text
            result = self._extract_text_from_image(img_array)
            
            self._update_progress(95, "Processing results...")
            
            final_result = {
                'text': result['text'],
                'structured_data': result.get('structured_data', []),
                'pages': 1,
                'success': True
            }
            
            self._update_progress(100, "Complete!")
            return final_result
        
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            raise
    
    def _resize_image_if_needed(self, img_array: np.ndarray, max_dimension=3000) -> np.ndarray:
        """Resize image if it's too large to speed up OCR (increased limit for better accuracy)"""
        if len(img_array.shape) < 2:
            return img_array  # Can't resize 1D array
        
        height, width = img_array.shape[:2]
        
        # Only resize if really large to preserve quality
        if height > max_dimension or width > max_dimension:
            # Calculate scaling factor
            scale = max_dimension / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height} for faster OCR")
            
            if CV2_AVAILABLE:
                img_array = cv2.resize(img_array, (new_width, new_height), interpolation=cv2.INTER_AREA)
            else:
                img = Image.fromarray(img_array)
                # Use compatibility-safe resize method
                try:
                    # Try new Pillow 10.0.0+ method
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Fallback to old method for older Pillow versions
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                img_array = np.array(img)
        
        return img_array
    
    def _extract_text_from_image(self, img_array: np.ndarray) -> Dict:
        """Extract text from image using OCR"""
        # Initialize EasyOCR if not already done (lazy initialization)
        if not self._initialization_attempted:
            self._update_progress(40, "Initializing OCR engine...")
            self._initialize_easyocr()
        
        # Use EasyOCR (better for handwritten, doesn't require external system dependencies)
        if self.easyocr_reader:
            try:
                current_progress = self._get_current_progress()
                if current_progress < 50:
                    self._update_progress(50, "Detecting text regions...")
                
                # Try with original image first (often better for clean typed text)
                original_result = self._extract_with_easyocr(img_array)
                
                # Check if we got reasonable results (not too many single characters or gibberish)
                reasonable_results = sum(1 for item in original_result.get('structured_data', []) 
                                       if item.get('medicine_name') and len(item.get('medicine_name', '')) > 2)
                
                # If we got few reasonable results, try with preprocessing
                if reasonable_results < 3 and CV2_AVAILABLE:
                    self._update_progress(55, "Trying enhanced image processing...")
                    processed_img = self._preprocess_image(img_array, fast_mode=True)
                    processed_result = self._extract_with_easyocr(processed_img)
                    
                    # Use the result with more reasonable data
                    processed_reasonable = sum(1 for item in processed_result.get('structured_data', []) 
                                             if item.get('medicine_name') and len(item.get('medicine_name', '')) > 2)
                    
                    if processed_reasonable > reasonable_results:
                        result = processed_result
                    else:
                        result = original_result
                else:
                    result = original_result
                
                current_progress = self._get_current_progress()
                if current_progress < 90:
                    self._update_progress(90, "Extracting text...")
                
                return result
            except Exception as e:
                logger.error(f"EasyOCR extraction failed: {e}")
                raise ValueError(f"OCR extraction failed: {e}")
        
        # EasyOCR not available or failed to initialize
        if EASYOCR_AVAILABLE:
            raise ValueError("EasyOCR is installed but failed to initialize. This may be due to network/SSL issues when downloading model files. Please check your internet connection and try again.")
        else:
            raise ValueError("EasyOCR is not available. Please install with: pip install easyocr")
    
    def _get_current_progress(self) -> int:
        """Get current progress percentage from callback state"""
        # This is a simple implementation - in a real scenario, you'd track this in the callback
        return 0
    
    def _preprocess_image(self, img_array: np.ndarray, fast_mode=True) -> np.ndarray:
        """Preprocess image to improve OCR accuracy - optimized for spreadsheets/tables"""
        if not CV2_AVAILABLE:
            return img_array
        
        try:
            # Convert to grayscale if needed
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # For typed/spreadsheet images, minimal preprocessing often works better
            # EasyOCR handles clean images well, so we'll do light enhancement only
            if fast_mode:
                # Light preprocessing: just enhance contrast slightly
                # Don't over-process as it can degrade quality
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                return enhanced
            else:
                # More aggressive preprocessing for difficult images
                # First, denoise if needed
                denoised = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)
                # Enhance contrast
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                enhanced = clahe.apply(denoised)
                return enhanced
        
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return img_array
    
    def _extract_with_easyocr(self, img_array: np.ndarray) -> Dict:
        """Extract text using EasyOCR (optimized for typed and handwritten text)"""
        # Use better parameters for accuracy, especially for typed/spreadsheet text
        # paragraph=False: Don't group into paragraphs (better for tables)
        # width_ths and height_ths: Adjust thresholds for better text detection
        try:
            results = self.easyocr_reader.readtext(
                img_array,
                paragraph=False,  # Better for table structures
                width_ths=0.7,    # Lower threshold for detecting text blocks
                height_ths=0.7,   # Lower threshold for detecting text blocks
                detail=1          # Get detailed results with bounding boxes
            )
        except Exception as e:
            logger.warning(f"EasyOCR readtext with parameters failed: {e}, trying default")
            # Fallback to default if custom parameters fail
            results = self.easyocr_reader.readtext(img_array)
        
        # Filter results by confidence (remove very low confidence detections)
        filtered_results = []
        for result in results:
            if len(result) >= 3:
                bbox, text, confidence = result[0], result[1], result[2]
                # Only keep results with reasonable confidence
                # Lower threshold (0.3) to catch more text, but still filter obvious noise
                if confidence > 0.3:
                    # Clean up text: remove common OCR artifacts
                    cleaned_text = text.strip()
                    # Remove single characters that are likely OCR errors
                    if len(cleaned_text) > 1 or cleaned_text.isalnum():
                        filtered_results.append(result)
            else:
                filtered_results.append(result)
        
        # Combine all text
        full_text = '\n'.join([result[1] for result in filtered_results])
        
        # Try to structure the data (medicine name and price)
        structured_data = self._structure_ocr_data(filtered_results)
        
        return {
            'text': full_text,
            'structured_data': structured_data,
            'raw_results': filtered_results
        }
    
    def _structure_ocr_data(self, ocr_results: List) -> List[Dict]:
        """
        Structure OCR results into medicine name and price pairs
        Uses heuristics to identify medicine names and prices
        Improved to handle table/spreadsheet structures
        """
        structured = []
        
        if not ocr_results:
            return structured
        
        # Group text by lines (similar y-coordinates) - more flexible grouping
        lines = {}
        for result in ocr_results:
            bbox, text, confidence = result
            if not text or not text.strip():
                continue
            
            # Get average y-coordinate of bounding box
            y_avg = sum([point[1] for point in bbox]) / len(bbox)
            # More flexible grouping - use 15-pixel intervals for better line detection
            line_key = int(y_avg / 15) * 15
            
            if line_key not in lines:
                lines[line_key] = []
            # Store text, x-coordinate (for column detection), and confidence
            x_avg = sum([point[0] for point in bbox]) / len(bbox)
            lines[line_key].append((text.strip(), x_avg, confidence, bbox))
        
        # Always try table structure first if we have multiple lines (common for spreadsheets)
        # Then fallback to line-based parsing if table parsing yields poor results
        if len(lines) >= 2:
            # Try table structure parsing first
            structured = self._parse_table_structure(lines)
            
            # If table parsing didn't yield good results, try line-based parsing
            # Good results = at least some entries with both name and price
            good_results = sum(1 for item in structured 
                             if item.get('medicine_name') and item.get('unit_price'))
            
            if good_results < len(structured) * 0.3:  # Less than 30% have both fields
                # Try line-based parsing as fallback
                line_based = []
                for line_key in sorted(lines.keys()):
                    line_items = lines[line_key]
                    # Sort by x-coordinate to maintain left-to-right order
                    line_items.sort(key=lambda x: x[1])
                    line_text = ' '.join([item[0] for item in line_items])
                    
                    # Try to extract medicine name and price from this line
                    parsed = self.parse_line(line_text)
                    if parsed:
                        line_based.append(parsed)
                
                # Use whichever method gave better results
                line_based_good = sum(1 for item in line_based 
                                     if item.get('medicine_name') and item.get('unit_price'))
                if line_based_good > good_results:
                    structured = line_based
        else:
            # Single line or very few lines - use line-based parsing
            for line_key in sorted(lines.keys()):
                line_items = lines[line_key]
                # Sort by x-coordinate to maintain left-to-right order
                line_items.sort(key=lambda x: x[1])
                line_text = ' '.join([item[0] for item in line_items])
                
                # Try to extract medicine name and price from this line
                parsed = self.parse_line(line_text)
                if parsed:
                    structured.append(parsed)
        
        return structured
    
    def _detect_table_structure(self, lines: Dict) -> bool:
        """Detect if OCR results form a table structure"""
        if len(lines) < 3:  # Need at least a few rows
            return False
        
        # Check if we have consistent column-like structure
        # Look for patterns where items are aligned in columns
        x_positions = []
        for line_items in lines.values():
            for item in line_items:
                x_positions.append(item[1])  # x-coordinate
        
        if len(x_positions) < 6:
            return False
        
        # Check if there are distinct column positions
        # Sort x positions and look for clusters
        x_positions.sort()
        clusters = []
        current_cluster = [x_positions[0]]
        
        for x in x_positions[1:]:
            if x - current_cluster[-1] < 50:  # Items within 50 pixels are in same column
                current_cluster.append(x)
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [x]
        
        if len(current_cluster) >= 2:
            clusters.append(current_cluster)
        
        # If we have 2+ distinct column clusters, it's likely a table
        return len(clusters) >= 2
    
    def _parse_table_structure(self, lines: Dict) -> List[Dict]:
        """Parse OCR results as a two-column table (Medicine Name | Unit Price)"""
        import re
        structured = []
        
        # Find column boundaries by analyzing x-coordinates
        all_x_positions = []
        for line_items in lines.values():
            for item in line_items:
                all_x_positions.append(item[1])  # x-coordinate
        
        if not all_x_positions:
            return structured
        
        # Find the median x-position to split into left and right columns
        all_x_positions.sort()
        median_x = all_x_positions[len(all_x_positions) // 2]
        
        # More sophisticated: find the gap between columns
        # Look for the largest gap in x-positions (this is likely the column separator)
        gaps = []
        for i in range(len(all_x_positions) - 1):
            gap = all_x_positions[i + 1] - all_x_positions[i]
            if gap > 50:  # Significant gap (likely column separator)
                gaps.append((gap, (all_x_positions[i] + all_x_positions[i + 1]) / 2))
        
        # Use the largest gap as the column separator, or median if no clear gap
        if gaps:
            gaps.sort(reverse=True, key=lambda x: x[0])
            column_separator_x = gaps[0][1]
        else:
            column_separator_x = median_x
        
        # Process each line
        for line_key in sorted(lines.keys()):
            line_items = lines[line_key]
            if len(line_items) < 1:
                continue
            
            # Sort items by x-coordinate (left to right)
            line_items.sort(key=lambda x: x[1])
            
            # Split items into left column (medicine name) and right column (price)
            left_column_items = []  # Medicine name
            right_column_items = []  # Price
            
            for text, x_pos, confidence, bbox in line_items:
                if x_pos < column_separator_x:
                    left_column_items.append(text)
                else:
                    right_column_items.append(text)
            
            # Combine left column items as medicine name
            medicine_name = ' '.join(left_column_items).strip()
            
            # Extract price from right column
            price_value = None
            right_column_text = ' '.join(right_column_items).strip()
            
            # Pattern for prices: numbers with optional commas and decimals
            price_patterns = [
                r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # 1,100.00 or 1,100
                r'\d+\.\d{2}',  # 1100.00
                r'\d{4,}',  # Large numbers (4+ digits, likely prices)
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, right_column_text)
                if price_match:
                    try:
                        # Remove commas and convert to float
                        price_str = price_match.group(0).replace(',', '')
                        test_price = float(price_str)
                        if test_price > 0:
                            price_value = test_price
                            break
                    except:
                        continue
            
            # If no price in right column, check if medicine name contains price
            if not price_value:
                for pattern in price_patterns:
                    price_match = re.search(pattern, medicine_name)
                    if price_match:
                        try:
                            price_str = price_match.group(0).replace(',', '')
                            test_price = float(price_str)
                            if test_price > 0:
                                price_value = test_price
                                # Remove price from medicine name
                                medicine_name = medicine_name[:price_match.start()].strip()
                                break
                        except:
                            continue
            
            # Clean up medicine name
            if medicine_name:
                # Remove common OCR artifacts and trailing numbers
                medicine_name = re.sub(r'[\d\s,\.]+$', '', medicine_name).strip()
                medicine_name = re.sub(r'[^\w\s-]+$', '', medicine_name).strip()
                
                # Only add if we have a valid medicine name (more than 1 character, contains letters)
                if medicine_name and len(medicine_name) > 1 and re.search(r'[a-zA-Z]', medicine_name):
                    structured.append({
                        'medicine_name': medicine_name,
                        'unit_price': price_value if price_value and price_value > 0 else None
                    })
        
        return structured
    
    def _structure_text_data(self, text: str) -> List[Dict]:
        """Structure plain text into medicine name and price pairs"""
        structured = []
        lines = text.split('\n')
        
        for line in lines:
            parsed = self.parse_line(line)
            if parsed:
                structured.append(parsed)
        
        return structured
    
    def parse_line(self, line: str) -> Optional[Dict]:
        """
        Parse a line of text to extract medicine name and price
        Returns dict with 'medicine_name' and 'unit_price' or None
        Improved to handle comma-separated numbers and better price detection
        """
        import re
        
        line = line.strip()
        if not line:
            return None
        
        # Skip lines that are just numbers or very short
        if len(line) < 2 or re.match(r'^[\d\s,\.]+$', line):
            return None
        
        # Pattern to find prices: numbers with optional commas and decimals
        # Look for patterns like: 1,100.00 or 1100.00 or 1100
        price_patterns = [
            r'\d{1,3}(?:,\d{3})*(?:\.\d{2})?',  # 1,100.00 or 1,100
            r'\d+\.\d{2}',  # 1100.00
            r'\d{4,}',  # Large numbers (likely prices)
        ]
        
        price_value = None
        price_match = None
        best_match_pos = -1
        
        # Try to find the best price match (usually at the end of the line)
        for pattern in price_patterns:
            matches = list(re.finditer(pattern, line))
            for match in matches:
                try:
                    # Remove commas and convert to float
                    price_str = match.group(0).replace(',', '')
                    test_price = float(price_str)
                    if test_price > 0:
                        # Prefer matches at the end of the line
                        if match.end() > best_match_pos:
                            price_value = test_price
                            price_match = match
                            best_match_pos = match.end()
                except ValueError:
                    continue
        
        if price_value and price_match:
            # Extract medicine name (everything before the price)
            medicine_name = line[:price_match.start()].strip()
            
            # Clean up medicine name
            # Remove trailing special characters, numbers at the end
            medicine_name = re.sub(r'[\d\s,\.]+$', '', medicine_name).strip()
            medicine_name = re.sub(r'[^\w\s-]+$', '', medicine_name).strip()
            
            if medicine_name and len(medicine_name) > 1:
                return {
                    'medicine_name': medicine_name,
                    'unit_price': price_value
                }
        
        # If no price found, check if it's a valid medicine name
        # (contains letters, not just numbers)
        if re.search(r'[a-zA-Z]', line) and len(line) > 2:
            return {
                'medicine_name': line,
                'unit_price': None  # User will need to fill this
            }
        
        return None
