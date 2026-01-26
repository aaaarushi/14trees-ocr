# card_preprocessor_fixed.py
"""
Fixed card preprocessing with robust border detection
"""

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pillow_heif
import cv2
import numpy as np
import os

pillow_heif.register_heif_opener()

class CardPreprocessor:
    """
    Preprocess card images with robust border detection
    """
    
    def __init__(self, work_dir="preprocessed_cards"):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)
        
        # Enhancement parameters
        self.contrast_factor = 1.3
        self.sharpness_factor = 1.5
        self.brightness_factor = 1.1
        self.target_size = 1600
    
    def preprocess(self, image_path, save_steps=False):
        """
        Complete preprocessing with card detection and cropping
        """
        
        print(f"\n{'='*60}")
        print(f"PREPROCESSING: {os.path.basename(image_path)}")
        print(f"{'='*60}\n")
        
        metadata = {
            'original_path': image_path,
            'steps_completed': [],
            'errors': []
        }
        
        try:
            # Step 1: Load image
            print("Step 1: Loading image...")
            img = self._load_image(image_path)
            if img is None:
                metadata['errors'].append("Failed to load image")
                return None, metadata
            
            metadata['original_size'] = img.size
            print(f"  ✓ Loaded: {img.size[0]}x{img.size[1]}")
            metadata['steps_completed'].append('load')
            
            if save_steps:
                self._save_step(img, "01_loaded.jpg")
            
            # Step 2: Convert to RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
                print("  ✓ Converted to RGB")
            
            # Step 3: Detect and crop card border (IMPROVED)
            print("\nStep 2: Detecting card border...")
            cropped_img = self._detect_card_border_v2(img, save_steps=save_steps)
            
            if cropped_img is None:
                print("  ⚠ Border detection failed, using original image")
                cropped_img = img
                metadata['cropped'] = False
            else:
                print(f"  ✓ Card cropped: {cropped_img.size[0]}x{cropped_img.size[1]}")
                metadata['cropped'] = True
                metadata['cropped_size'] = cropped_img.size
            
            metadata['steps_completed'].append('crop')
            
            if save_steps:
                self._save_step(cropped_img, "02_cropped.jpg")
            
            # Step 4: Enhance for OCR
            print("\nStep 3: Enhancing for OCR...")
            img_enhanced = self._enhance_image(cropped_img, save_steps)
            
            metadata['steps_completed'].append('enhance')
            
            # Step 5: Resize if needed
            print("\nStep 4: Resizing...")
            img_final = self._resize_image(img_enhanced)
            
            metadata['final_size'] = img_final.size
            metadata['steps_completed'].append('resize')
            
            # Step 6: Save final
            print("\nStep 5: Saving...")
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            final_path = os.path.join(self.work_dir, f"{base_name}_card.jpg")
            img_final.save(final_path, 'JPEG', quality=95)
            
            file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
            print(f"  ✓ Saved: {final_path}")
            print(f"  ✓ Size: {file_size_mb:.2f} MB")
            
            metadata['final_path'] = final_path
            metadata['success'] = True
            
            print(f"\n{'='*60}")
            print("✓ PREPROCESSING COMPLETE")
            print(f"{'='*60}\n")
            
            return final_path, metadata
            
        except Exception as e:
            print(f"\n✗ PREPROCESSING FAILED: {e}")
            import traceback
            traceback.print_exc()
            metadata['success'] = False
            metadata['errors'].append(str(e))
            return None, metadata
    
    def _load_image(self, image_path):
        """Load image with EXIF correction"""
        try:
            img = Image.open(image_path)
            img = ImageOps.exif_transpose(img)
            return img
        except Exception as e:
            print(f"  ✗ Load failed: {e}")
            return None
    
    def _detect_card_border_v2(self, img, save_steps=False):
        """
        IMPROVED border detection using multiple strategies
        
        Strategy:
        1. Look for strong rectangular contours
        2. Filter by aspect ratio (cards are roughly rectangular)
        3. Filter by size (not too small, not whole image)
        4. Try multiple threshold values
        """
        
        try:
            # Convert to OpenCV format
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            original_h, original_w = img_cv.shape[:2]
            
            print(f"  Original size: {original_w}x{original_h}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            if save_steps:
                cv2.imwrite(os.path.join(self.work_dir, "steps", "debug_01_gray.jpg"), gray)
            
            # Try adaptive thresholding (better for varied lighting)
            print("  Trying adaptive threshold method...")
            
            # Apply bilateral filter to reduce noise while keeping edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            if save_steps:
                cv2.imwrite(os.path.join(self.work_dir, "steps", "debug_02_filtered.jpg"), filtered)
            
            # Adaptive threshold
            thresh = cv2.adaptiveThreshold(
                filtered, 
                255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 
                11, 
                2
            )
            
            if save_steps:
                cv2.imwrite(os.path.join(self.work_dir, "steps", "debug_03_thresh.jpg"), thresh)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            print(f"  Found {len(contours)} contours")
            
            if not contours:
                print("  No contours found, trying Canny edge detection...")
                return self._detect_card_border_canny(img_cv, save_steps)
            
            # Filter contours by area and aspect ratio
            img_area = original_w * original_h
            valid_contours = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by area (20% to 95% of image)
                if area < 0.2 * img_area or area > 0.95 * img_area:
                    continue
                
                # Approximate contour to polygon
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                
                # Should have 4 corners (rectangle)
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = float(w) / h
                    
                    # Cards are roughly rectangular (aspect ratio between 0.6 and 1.5)
                    if 0.6 < aspect_ratio < 1.5:
                        valid_contours.append({
                            'contour': contour,
                            'area': area,
                            'bbox': (x, y, w, h),
                            'aspect_ratio': aspect_ratio
                        })
            
            print(f"  Valid rectangular contours: {len(valid_contours)}")
            
            if not valid_contours:
                print("  No valid rectangular contours, trying Canny...")
                return self._detect_card_border_canny(img_cv, save_steps)
            
            # Take the largest valid contour
            best_contour = max(valid_contours, key=lambda x: x['area'])
            x, y, w, h = best_contour['bbox']
            
            print(f"  Best contour: {w}x{h} at ({x}, {y})")
            print(f"  Aspect ratio: {best_contour['aspect_ratio']:.2f}")
            print(f"  Area: {best_contour['area']/img_area:.1%} of image")
            
            # Add small padding
            padding = 5
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(original_w - x, w + 2*padding)
            h = min(original_h - y, h + 2*padding)
            
            # Crop using PIL
            cropped = img.crop((x, y, x+w, y+h))
            
            return cropped
            
        except Exception as e:
            print(f"  ✗ Adaptive threshold method failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _detect_card_border_canny(self, img_cv, save_steps=False):
        """
        Fallback: Canny edge detection method
        """
        
        print("  Using Canny edge detection...")
        
        try:
            original_h, original_w = img_cv.shape[:2]
            
            # Convert to grayscale
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Canny edge detection
            edges = cv2.Canny(blurred, 30, 150)
            
            if save_steps:
                cv2.imwrite(os.path.join(self.work_dir, "steps", "debug_04_edges.jpg"), edges)
            
            # Dilate to connect broken edges
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)
            
            if save_steps:
                cv2.imwrite(os.path.join(self.work_dir, "steps", "debug_05_dilated.jpg"), dilated)
            
            # Find contours
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                print("  No contours found with Canny")
                return None
            
            # Filter and find best rectangular contour
            img_area = original_w * original_h
            valid_contours = []
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                if area < 0.2 * img_area or area > 0.95 * img_area:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(w) / h
                
                if 0.6 < aspect_ratio < 1.5:
                    valid_contours.append({
                        'contour': contour,
                        'area': area,
                        'bbox': (x, y, w, h)
                    })
            
            if not valid_contours:
                print("  No valid contours with Canny")
                return None
            
            # Get largest
            best = max(valid_contours, key=lambda x: x['area'])
            x, y, w, h = best['bbox']
            
            print(f"  Canny found contour: {w}x{h} at ({x}, {y})")
            
            # Crop
            from PIL import Image as PILImage
            img_pil = PILImage.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            cropped = img_pil.crop((x, y, x+w, y+h))
            
            return cropped
            
        except Exception as e:
            print(f"  ✗ Canny method failed: {e}")
            return None
    
    def _enhance_image(self, img, save_steps):
        """Apply enhancement steps"""
        
        # Contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(self.contrast_factor)
        print(f"  ✓ Contrast ({self.contrast_factor}x)")
        
        if save_steps:
            self._save_step(img, "03_contrast.jpg")
        
        # Sharpness
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(self.sharpness_factor)
        print(f"  ✓ Sharpness ({self.sharpness_factor}x)")
        
        if save_steps:
            self._save_step(img, "04_sharpness.jpg")
        
        # Brightness
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(self.brightness_factor)
        print(f"  ✓ Brightness ({self.brightness_factor}x)")
        
        # Unsharp mask
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
        print(f"  ✓ Unsharp mask")
        
        if save_steps:
            self._save_step(img, "05_enhanced.jpg")
        
        return img
    
    def _resize_image(self, img):
        """Resize if needed"""
        
        width, height = img.size
        longest = max(width, height)
        
        if longest > self.target_size:
            scale = self.target_size / longest
            new_w = int(width * scale)
            new_h = int(height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            print(f"  ✓ Resized to {new_w}x{new_h}")
        else:
            print(f"  ✓ No resize needed")
        
        return img
    
    def _save_step(self, img, filename):
        """Save intermediate step"""
        step_dir = os.path.join(self.work_dir, "steps")
        os.makedirs(step_dir, exist_ok=True)
        path = os.path.join(step_dir, filename)
        img.save(path, quality=95)


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("FIXED CARD PREPROCESSOR TEST")
    print("=" * 60)
    
    preprocessor = CardPreprocessor()
    
    test_images = os.listdir("test_images")
    test_images = ["test_images/" + img for img in test_images]
    
    results = []
    
    for img_path in test_images:
        if os.path.exists(img_path):
            final_path, metadata = preprocessor.preprocess(
                img_path,
                save_steps=True  # Save debug images
            )
            
            results.append({
                'original': img_path,
                'final': final_path,
                'success': metadata.get('success', False),
                'cropped': metadata.get('cropped', False)
            })
        else:
            print(f"\nSkipping (not found): {img_path}\n")
    
    # Summary
    print("\n" + "=" * 60)
    print("PREPROCESSING SUMMARY")
    print("=" * 60)
    
    successful = sum(1 for r in results if r['success'])
    cropped = sum(1 for r in results if r.get('cropped'))
    
    print(f"\nSuccessfully preprocessed: {successful}/{len(results)}")
    print(f"Successfully cropped: {cropped}/{len(results)}")
    
    for i, result in enumerate(results, 1):
        status = "✓" if result['success'] else "✗"
        crop_status = "✓ Cropped" if result.get('cropped') else "✗ Not cropped"
        
        print(f"\n{i}. {status} {os.path.basename(result['original'])}")
        print(f"   {crop_status}")
        
        if result['success']:
            print(f"   → {result['final']}")
    
    print("\n" + "=" * 60)
    print("Check 'preprocessed_cards/steps' for debug images")
    print("Look at debug_01_gray.jpg, debug_03_thresh.jpg, etc.")
    print("=" * 60)