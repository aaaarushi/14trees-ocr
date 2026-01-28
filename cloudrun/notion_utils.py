import os
from notion_client import Client as NotionClient

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