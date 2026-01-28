from googleapiclient.discovery import build
from google.auth import default
from schema_config import get_sheets_headers

def sheets_client():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def ensure_header(sheets, sheet_id: str, tab_name: str):
    rng = f"{tab_name}!A1:D1"
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng
    ).execute()
    values = resp.get("values", [])
    if not values or not any(values[0]):
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=rng,
            valueInputOption="RAW",
            body={"values": [["file_id", "file_name", "created_time", "drive_link"]]},
        ).execute()


def get_existing_file_ids(sheets, sheet_id: str, tab_name: str) -> set:
    rng = f"{tab_name}!A2:A"
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng
    ).execute()
    values = resp.get("values", [])
    return {row[0] for row in values if row and row[0]}


def append_rows(sheets, sheet_id: str, tab_name: str, rows: list) -> int:
    if not rows:
        return 0
    
    # Dynamic range based on schema
    num_cols = len(get_sheets_headers())
    last_col = chr(64 + num_cols)
    rng = f"{tab_name}!A:{last_col}"
    
    sheets.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=rng,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(rows)

def ensure_header_with_schema(sheets, sheet_id: str, tab_name: str):
    """Ensure headers match the extraction schema"""
    
    headers = get_sheets_headers()
    num_cols = len(headers)
    last_col = chr(64 + num_cols)
    rng = f"{tab_name}!A1:{last_col}1"
    
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=rng
    ).execute()
    values = resp.get("values", [])
    
    if not values or not any(values[0]):
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=rng,
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()