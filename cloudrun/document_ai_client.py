"""
Document AI processing utilities
"""

from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from schema_config import EXTRACTION_SCHEMA

# ==================== CONFIGURATION ====================
PROJECT_ID = "artful-lane-485410-j1"
LOCATION = "us"  # or "eu"
PROCESSOR_ID = "4fb4e11231940dd2"
PROCESSOR_VERSION_ID = "79cab3e5ff622e31"
TEST_IMAGE_PATH = "test.jpg"  # Path to test image
FILE_TYPE = "image/jpeg"
# =======================================================


def process_document_ai(
    file_bytes: bytes,
    project_id: str,
    location: str,
    processor_id: str,
    processor_version_id: str,
    mime_type: str = "image/jpeg"
) -> dict:
    """
    Process document with Document AI custom extractor.
    
    Args:
        file_bytes: File content as bytes
        project_id: GCP project ID
        location: Processor location (e.g., "us" or "eu")
        processor_id: Document AI processor ID
        mime_type: MIME type of document
    
    Returns:
        Dict mapping field names to {"value": ..., "confidence": ...}
        Missing fields will have {"value": None, "confidence": None}
    """
    # Setup Document AI client
    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    
    # Build processor name
    name = client.processor_version_path(project_id, location, processor_id, processor_version_id)
    
    # Create request
    raw_document = documentai.RawDocument(content=file_bytes, mime_type=mime_type)
    
    request = documentai.ProcessRequest(
        name=name,
        raw_document=raw_document,
        field_mask="text,entities",
    )
    
    # Process document
    result = client.process_document(request=request)
    
    # Initialize with all expected fields as None
    extracted_fields = {}
    for field in EXTRACTION_SCHEMA:
        extracted_fields[field.name] = {
            "value": None,
            "confidence": None
        }
    
    # Populate with actual extracted entities
    for entity in result.document.entities:
        field_name = entity.type_
        value = entity.mention_text
        confidence = entity.confidence
        
        # Use normalized_value if available (better for dates/numbers)
        if entity.normalized_value and entity.normalized_value.text:
            value = entity.normalized_value.text
        
        extracted_fields[field_name] = {
            "value": value,
            "confidence": confidence
        }
    
    return extracted_fields


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Document AI Extraction")
    print("=" * 80)
    
    # Read test image
    print(f"\nReading: {TEST_IMAGE_PATH}")
    with open(TEST_IMAGE_PATH, "rb") as f:
        file_bytes = f.read()
    print(f"✓ File size: {len(file_bytes)} bytes")
    
    # Process with Document AI
    print("\nCalling Document AI API...")
    try:
        results = process_document_ai(
            file_bytes=file_bytes,
            project_id=PROJECT_ID,
            location=LOCATION,
            processor_id=PROCESSOR_ID,
            processor_version_id=PROCESSOR_VERSION_ID,
            mime_type=FILE_TYPE
        )
        print("✓ API call successful")
    except Exception as e:
        print(f"✗ API call failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # Display results
    print("\n" + "=" * 80)
    print("EXTRACTED FIELDS:")
    print("=" * 80)
    
    for field in EXTRACTION_SCHEMA:
        field_name = field.name
        display_name = field.display_name
        data = results[field_name]
        value = data["value"]
        confidence = data["confidence"]
        
        if value is not None:
            print(f"✓ {display_name:35} = {str(value):20} (conf: {confidence:.2f})")
        else:
            print(f"✗ {display_name:35} = NOT FOUND")
    
    print("=" * 80)

        # ============ NEW: Test Google Sheets formatting ============
    print("\nTesting Google Sheets formatting...")
    from schema_config import build_sheets_row, get_sheets_headers
    
    headers = get_sheets_headers()
    row = build_sheets_row(results)
    
    print("\nHeaders:")
    print(headers)
    print("\nRow:")
    print(row)
    
    print("\n✓ Sheets formatting works!")
    print("=" * 80)