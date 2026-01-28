import os
from notion_client import Client as NotionClient

from schema_config import build_notion_properties

def notion_client():
    """
    Returns a Notion client if env vars exist, else None.
    """
    api_key = os.environ.get("NOTION_API_KEY")
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not api_key or not db_id:
        return None, None
    return NotionClient(auth=api_key), db_id


def create_notion_row(notion, notion_db_id: str, fid: str, name: str, created_time: str, drive_link: str) -> str:
    page = notion.pages.create(
        parent={"database_id": notion_db_id},
        properties={
            "File Name": {"title": [{"text": {"content": name or ""}}]},
            "File ID": {"rich_text": [{"text": {"content": fid}}]},
            "Created Time": {"date": {"start": created_time}},
            "URL": {"url": drive_link},
        },
    )
    return page["id"]


def set_notion_cover_external(notion, page_id: str, image_url: str) -> None:
    notion.pages.update(
        page_id=page_id,
        cover={
            "type": "external",
            "external": {"url": image_url},
        },
    )
    
def create_notion_row_from_extraction(notion, notion_db_id: str, extracted_data: dict) -> str:
    """
    Create Notion page from Document AI extraction results.
    
    Args:
        notion: Notion client instance
        notion_db_id: Notion database ID
        extracted_data: Dict from Document AI with structure:
                       {field_name: {"value": ..., "confidence": ...}}
    
    Returns:
        Created page ID
    """
    
    properties = build_notion_properties(extracted_data)
    
    page = notion.pages.create(
        parent={"database_id": notion_db_id},
        properties=properties,
    )
    
    return page["id"]

def get_existing_notion_khadde_ids(notion, notion_db_id: str) -> dict:
    """
    Get existing Khadde values and their page IDs from Notion database.
    Returns dict: {khadde_value: page_id}
    """
    from schema_config import EXTRACTION_SCHEMA
    
    # Get the display name of the first field (Khadde)
    khadde_display_name = EXTRACTION_SCHEMA[0].display_name
    
    khadde_map = {}
    
    # Query all pages in the database
    has_more = True
    start_cursor = None
    
    while has_more:
        query_params = {"database_id": notion_db_id}
        if start_cursor:
            query_params["start_cursor"] = start_cursor
        
        results = notion.databases.query(**query_params)
        
        for page in results["results"]:
            properties = page["properties"]
            
            # Get Khadde value
            if khadde_display_name in properties:
                khadde_prop = properties[khadde_display_name]
                
                # Extract value based on property type (should be number)
                if khadde_prop["type"] == "number" and khadde_prop["number"] is not None:
                    khadde_value = str(int(khadde_prop["number"]))
                    page_id = page["id"]
                    khadde_map[khadde_value] = page_id
        
        has_more = results["has_more"]
        start_cursor = results.get("next_cursor")
    
    return khadde_map


def update_notion_page_from_extraction(notion, page_id: str, extracted_data: dict):
    """
    Update an existing Notion page with new extracted data.
    
    Args:
        notion: Notion client instance
        page_id: Notion page ID to update
        extracted_data: Dict from Document AI
    """
    from schema_config import build_notion_properties
    
    properties = build_notion_properties(extracted_data)
    
    notion.pages.update(
        page_id=page_id,
        properties=properties,
    )