# schema_config.py

from enum import Enum
from typing import List, Dict, Any
from fields import FIELDS  # Import from the simple config file

class FieldType(Enum):
    """Field types that map to Document AI, Sheets, and Notion"""
    TEXT = "text"
    NUMBER = "number"
    CHECKBOX = "checkbox"

class SchemaField:
    """Represents a single field in the extraction schema"""
    def __init__(
        self,
        name: str,
        field_type: FieldType,
        display_name: str = None,
        description: str = None
    ):
        self.name = name  # Document AI field name (snake_case)
        self.field_type = field_type
        self.display_name = display_name or name.replace("_", " ").title()
        self.description = description
    
    def to_notion_property(self) -> Dict[str, Any]:
        """Convert to Notion property format"""
        if self.field_type == FieldType.TEXT:
            return {"rich_text": [{"text": {"content": ""}}]}
        elif self.field_type == FieldType.NUMBER:
            return {"number": None}
        elif self.field_type == FieldType.CHECKBOX:
            return {"checkbox": False}
    
    def to_sheets_header(self) -> str:
        """Convert to Google Sheets column header"""
        return self.display_name
    
    def format_value_for_notion(self, value: Any) -> Dict[str, Any]:
        """Format extracted value for Notion API"""
        if value is None:
            return self.to_notion_property()
        
        if self.field_type == FieldType.TEXT:
            return {"rich_text": [{"text": {"content": str(value)}}]}
        elif self.field_type == FieldType.NUMBER:
            try:
                return {"number": float(value) if value else None}
            except (ValueError, TypeError):
                return {"number": None}
        elif self.field_type == FieldType.CHECKBOX:
            # Handle various checkbox representations
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                value_lower = value.lower().strip()
                if value_lower in ("true", "yes", "1", "checked", "✓", "✔", "x"):
                    return True
                if value_lower in ("false", "no", "0", "unchecked", ""):
                    return False
                # If it's any other non-empty string, consider it checked
                return True
            return bool(value)
    
    def format_value_for_sheets(self, value: Any) -> Any:
        """Format extracted value for Google Sheets"""
        if value is None:
            return ""
        
        if self.field_type == FieldType.TEXT:
            return str(value)
        elif self.field_type == FieldType.NUMBER:
            try:
                return float(value) if value else ""
            except (ValueError, TypeError):
                return ""
        elif self.field_type == FieldType.CHECKBOX:
            # Sheets checkboxes: TRUE/FALSE
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1", "checked")
            return bool(value)


# ============================================================================
# BUILD EXTRACTION SCHEMA FROM FIELDS CONFIG
# ============================================================================

def _build_schema() -> List[SchemaField]:
    """Internal: Build schema objects from fields.py configuration"""
    schema = []
    for field_def in FIELDS:
        schema.append(SchemaField(
            name=field_def["name"],
            field_type=FieldType(field_def["type"]),
            display_name=field_def.get("display_name"),
            description=field_def.get("description")
        ))
    return schema

EXTRACTION_SCHEMA: List[SchemaField] = _build_schema()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_field_names() -> List[str]:
    """Get ordered list of field names for Document AI"""
    return [field.name for field in EXTRACTION_SCHEMA]

def get_sheets_headers() -> List[str]:
    """Get ordered list of column headers for Google Sheets"""
    return [field.to_sheets_header() for field in EXTRACTION_SCHEMA]

def get_notion_properties_schema() -> Dict[str, Dict[str, Any]]:
    """
    Get Notion database schema (for reference/setup).
    You'll need to create these properties in your Notion database manually.
    """
    schema = {}
    for field in EXTRACTION_SCHEMA:
        if field.field_type == FieldType.TEXT:
            schema[field.display_name] = {"rich_text": {}}
        elif field.field_type == FieldType.NUMBER:
            schema[field.display_name] = {"number": {}}
        elif field.field_type == FieldType.CHECKBOX:
            schema[field.display_name] = {"checkbox": {}}
    return schema

def build_notion_properties(extracted_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build Notion properties dict from Document AI extraction results.
    
    Args:
        extracted_data: Dict from Document AI with structure:
                       {field_name: {"value": ..., "confidence": ...}}
    
    Returns:
        Notion-formatted properties dict
    """
    properties = {}
    for field in EXTRACTION_SCHEMA:
        data = extracted_data.get(field.name, {"value": None, "confidence": None})
        value = data["value"]
        properties[field.display_name] = field.format_value_for_notion(value)
    
    return properties

def build_sheets_row(extracted_data: Dict[str, Dict[str, Any]]) -> List[Any]:
    """
    Build Google Sheets row from Document AI extraction results.
    
    Args:
        extracted_data: Dict from Document AI with structure:
                       {field_name: {"value": ..., "confidence": ...}}
    
    Returns:
        List of values in correct column order
    """
    row = []
    for field in EXTRACTION_SCHEMA:
        data = extracted_data.get(field.name, {"value": None, "confidence": None})
        value = data["value"]
        row.append(field.format_value_for_sheets(value))
    
    return row

def get_field_by_name(name: str) -> SchemaField:
    """Get field definition by name"""
    for field in EXTRACTION_SCHEMA:
        if field.name == name:
            return field
    return None


# ============================================================================
# USAGE EXAMPLES (for testing)
# ============================================================================

if __name__ == "__main__":
    print("=== Field Names (for Document AI) ===")
    print(get_field_names())
    
    print("\n=== Sheets Headers ===")
    print(get_sheets_headers())
    
    print("\n=== Notion Schema (for reference) ===")
    import json
    print(json.dumps(get_notion_properties_schema(), indent=2))
    
    print("\n=== Test: Build Notion Properties ===")
    test_extraction = {
        "serial_number": {"value": "123", "confidence": 0.95},
        "plot_name": {"value": "वृक्ष उद्यान", "confidence": 0.88},
        "number_of_trees": {"value": "45", "confidence": 0.92},
        "number_of_pits": {"value": None, "confidence": None},
        "road_access_top_left": {"value": "true", "confidence": 0.99},
        "photo_album_top_right": {"value": "false", "confidence": 0.87},
        "maps_bottom_left": {"value": None, "confidence": None},
        "komoot_bottom_right": {"value": "yes", "confidence": 0.91},
    }
    
    notion_props = build_notion_properties(test_extraction)
    print(json.dumps(notion_props, indent=2, ensure_ascii=False))
    
    print("\n=== Test: Build Sheets Row ===")
    sheets_row = build_sheets_row(test_extraction)
    print(sheets_row)
