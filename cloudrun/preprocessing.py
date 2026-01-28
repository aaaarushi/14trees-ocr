"""
Image preprocessing for card detection and enhancement
"""

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np
import io

# Try to import pillow_heif for HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False
    print("Warning: pillow_heif not installed, HEIC/HEIF files will not be supported")


def preprocess_card_image(image_bytes: bytes, mime_type: str = None) -> tuple:
    """
    Preprocess card image: convert to JPEG, detect border, crop, enhance for OCR.
    
    Args:
        image_bytes: Original image as bytes
        mime_type: MIME type of the image
    
    Returns:
        tuple: (preprocessed_bytes, "image/jpeg")
    """
    try:
        # Step 1: Load image
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)
        
        # Step 2: Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Step 3: Detect and crop card border (from your original script)
        cropped_img = _detect_card_border_adaptive(img)
        if cropped_img is None:
            cropped_img = img
        
        # Step 4: Enhance (from your original script)
        enhanced_img = _enhance_for_ocr(cropped_img)
        
        # Step 5: Resize if needed
        enhanced_img = _resize_if_needed(enhanced_img, target_size=1600)
        
        # Step 6: Convert to JPEG bytes
        output = io.BytesIO()
        enhanced_img.save(output, format='JPEG', quality=95)
        
        return output.getvalue(), "image/jpeg"
        
    except Exception as e:
        print(f"Preprocessing failed: {e}")
        return image_bytes, mime_type or "image/jpeg"


def _detect_card_border_adaptive(img):
    """
    Detect card border using adaptive thresholding.
    This is your original _detect_card_border_v2 logic.
    """
    try:
        # Convert to OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        original_h, original_w = img_cv.shape[:2]
        
        # Grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Bilateral filter
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Adaptive threshold
        thresh = cv2.adaptiveThreshold(
            filtered, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Filter valid rectangular contours
        img_area = original_w * original_h
        valid_contours = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Area filter (20% to 95%)
            if area < 0.2 * img_area or area > 0.95 * img_area:
                continue
            
            # Approximate to polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # Should be rectangle (4 corners)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(w) / h
                
                # Cards are roughly rectangular
                if 0.6 < aspect_ratio < 1.5:
                    valid_contours.append({
                        'area': area,
                        'bbox': (x, y, w, h)
                    })
        
        if not valid_contours:
            return None
        
        # Take largest
        best = max(valid_contours, key=lambda x: x['area'])
        x, y, w, h = best['bbox']
        
        # Add padding
        padding = 5
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(original_w - x, w + 2*padding)
        h = min(original_h - y, h + 2*padding)
        
        # Crop
        return img.crop((x, y, x+w, y+h))
        
    except Exception as e:
        return None


def _enhance_for_ocr(img):
    """
    Enhance image for OCR.
    This is your original enhancement logic.
    """
    # Contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)
    
    # Sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.5)
    
    # Brightness
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)
    
    # Unsharp mask
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
    
    return img


def _resize_if_needed(img, target_size=1600):
    """
    Resize if image is too large.
    This is your original resize logic.
    """
    width, height = img.size
    longest = max(width, height)
    
    if longest > target_size:
        scale = target_size / longest
        new_w = int(width * scale)
        new_h = int(height * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    return img