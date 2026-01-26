# card_ocr_simple.py
"""
Simple OCR extraction - just read top to bottom
Extract numbers and text, ignore checkboxes
"""

from google.cloud import vision
import os
import glob

CREDENTIALS_PATH = 'credentials.json'

class SimpleCardExtractor:
    """
    Dead simple extraction:
    1. Get all text elements
    2. Sort top to bottom
    3. Extract numbers and words
    4. Ignore checkbox symbols
    5. Output 4 lines
    """
    
    def __init__(self):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = CREDENTIALS_PATH
        self.client = vision.ImageAnnotatorClient()
        
        # What to ignore
        self.ignore_words = ['गायरान', 'क्रमांक', 'नाव']
        self.ignore_symbols = ['○', '●', 'O', '०', 'o', '◯', '⊙', '@', 'Q', '⦿', '◉', '☐', 'ооо', '이', '。', 'อ']
    
    def extract_all_cards(self, input_dir="preprocessed_cards", output_dir="extraction_results"):
        """Process all images in a folder"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Get all image files
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            image_files.extend(glob.glob(os.path.join(input_dir, ext)))
        
        # Filter out the 'steps' subdirectory files
        image_files = [f for f in image_files if 'steps' not in f]
        
        print(f"Found {len(image_files)} images to process\n")
        
        results = []
        
        for img_path in sorted(image_files):
            print("=" * 70)
            print(f"Processing: {os.path.basename(img_path)}")
            print("=" * 70)
            
            data = self.extract(img_path)
            
            if data:
                # Save output
                base_name = os.path.splitext(os.path.basename(img_path))[0]
                txt_path = os.path.join(output_dir, f"{base_name}.txt")
                
                with open(txt_path, 'w', encoding='utf-8') as f:
                    for line in data['lines']:
                        f.write(line + '\n')
                
                print(f"✓ Saved: {txt_path}")
                
                results.append({
                    'file': img_path,
                    'success': True,
                    'lines': data['lines']
                })
            else:
                results.append({
                    'file': img_path,
                    'success': False
                })
            
            print()
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        successful = sum(1 for r in results if r['success'])
        print(f"\nProcessed: {successful}/{len(results)}")
        
        for i, result in enumerate(results, 1):
            status = "✓" if result['success'] else "✗"
            print(f"\n{i}. {status} {os.path.basename(result['file'])}")
            
            if result['success']:
                for j, line in enumerate(result['lines'], 1):
                    print(f"   Line {j}: {line}")
        
        print("\n" + "=" * 70)
        
        return results
    
    def extract(self, image_path):
        """Extract text from one image"""
        
        # Call Vision API
        try:
            with open(image_path, 'rb') as f:
                content = f.read()
            
            image = vision.Image(content=content)
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                print(f"✗ API Error: {response.error.message}")
                return None
            
            if not response.full_text_annotation:
                print("✗ No text detected")
                return None
            
        except Exception as e:
            print(f"✗ Failed to call API: {e}")
            return None
        
        # Get page dimensions for Y-axis cutoff (ignore bottom half with checkboxes)
        pages = response.full_text_annotation.pages
        if not pages:
            print("✗ No page info")
            return None
        
        img_height = pages[0].height
        img_width = pages[0].width
        
        # Cutoff: ignore bottom half (where checkboxes are)
        y_cutoff = img_height * 0.50  # Ignore anything below 50% height
        
        print(f"Image: {img_width}x{img_height}, ignoring below Y={y_cutoff:.0f}")
        
        # Get all text annotations
        annotations = response.text_annotations[1:]  # Skip first (full text)
        
        # Extract elements with positions
        elements = []
        
        for annotation in annotations:
            vertices = annotation.bounding_poly.vertices
            y_center = sum(v.y for v in vertices) / len(vertices)
            x_center = sum(v.x for v in vertices) / len(vertices)
            
            # Skip if in bottom half (checkboxes)
            if y_center > y_cutoff:
                continue
            
            text = annotation.description
            
            # Skip ignored symbols
            if len(text) == 1 and text in self.ignore_symbols:
                continue
            
            # Skip label words
            if text in self.ignore_words:
                continue
            
            elements.append({
                'text': text,
                'x': x_center,
                'y': y_center
            })
        
        if not elements:
            print("✗ No text elements found in top half")
            return None
        
        # Sort by Y (top to bottom), then X (left to right)
        elements.sort(key=lambda e: (e['y'], e['x']))
        
        print(f"\nText elements (top to bottom):")
        for i, elem in enumerate(elements, 1):
            print(f"  {i:2d}. '{elem['text']}'")
        
        # Group into lines (elements on same Y-level)
        lines = []
        current_line = []
        last_y = None
        Y_TOLERANCE = 20  # pixels
        
        for elem in elements:
            if last_y is None or abs(elem['y'] - last_y) < Y_TOLERANCE:
                # Same line
                current_line.append(elem)
                last_y = elem['y']
            else:
                # New line - save previous
                if current_line:
                    # Sort by X (left to right)
                    current_line.sort(key=lambda e: e['x'])
                    line_text = ''.join(e['text'] for e in current_line)
                    lines.append(line_text)
                
                # Start new line
                current_line = [elem]
                last_y = elem['y']
        
        # Don't forget last line
        if current_line:
            current_line.sort(key=lambda e: e['x'])
            line_text = ''.join(e['text'] for e in current_line)
            lines.append(line_text)
        
        print(f"\nExtracted lines:")
        for i, line in enumerate(lines, 1):
            print(f"  Line {i}: {line}")
        
        return {
            'lines': lines,
            'element_count': len(elements)
        }


if __name__ == "__main__":
    print("=" * 70)
    print("SIMPLE CARD OCR EXTRACTOR")
    print("Process all images in preprocessed_cards/")
    print("=" * 70)
    print()
    
    extractor = SimpleCardExtractor()
    results = extractor.extract_all_cards(
        input_dir="preprocessed_cards",
        output_dir="extraction_results"
    )
    
    print("\n✓ Done! Check 'extraction_results' folder for .txt files")