import os
from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from google.auth import default

app = Flask(__name__)


def drive_client():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


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
    rng = f"{tab_name}!A:D"
    sheets.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=rng,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(rows)


def move_file_to_folder(drive, file_id: str, processed_folder_id: str) -> bool:
    meta = drive.files().get(fileId=file_id, fields="parents").execute()
    parents = meta.get("parents", [])

    # Idempotent: already in processed folder
    if processed_folder_id in parents:
        return False

    remove_parents = ",".join(parents) if parents else None

    drive.files().update(
        fileId=file_id,
        addParents=processed_folder_id,
        removeParents=remove_parents,
        fields="id,parents",
    ).execute()
    return True


@app.post("/")
def handle():
    # --- Secret protection (PUBLIC + SECRET MODEL) ---
    expected = os.environ.get("WEBHOOK_SECRET")
    if not expected:
        return jsonify({"ok": False, "error": "WEBHOOK_SECRET env var not set"}), 500

    got = request.headers.get("X-Webhook-Secret")
    if got != expected:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    # --- Required env vars ---
    uploads_folder_id = os.environ.get("UPLOADS_FOLDER_ID")
    sheet_id = os.environ.get("SHEET_ID")
    sheet_tab = os.environ.get("SHEET_TAB")
    processed_folder_id = os.environ.get("PROCESSED_FOLDER_ID")

    if not uploads_folder_id:
        return jsonify({"ok": False, "error": "UPLOADS_FOLDER_ID env var not set"}), 500
    if not sheet_id or not sheet_tab:
        return jsonify({"ok": False, "error": "SHEET_ID and/or SHEET_TAB env vars not set"}), 500
    if not processed_folder_id:
        return jsonify({"ok": False, "error": "PROCESSED_FOLDER_ID env var not set"}), 500

    drive = drive_client()

    # --- List new uploads ---
    q = (
        f"'{uploads_folder_id}' in parents and trashed = false and ("
        "mimeType='image/jpeg' or mimeType='image/png' or "
        "mimeType='image/heic' or mimeType='image/heif'"
        ")"
    )

    resp = drive.files().list(
        q=q,
        fields="files(id,name,createdTime,webViewLink)",
        pageSize=50,
    ).execute()

    files = resp.get("files", [])

    # --- Sheets de-dup + append ---
    sheets = sheets_client()
    ensure_header(sheets, sheet_id, sheet_tab)
    existing_ids = get_existing_file_ids(sheets, sheet_id, sheet_tab)

    new_rows = []
    new_file_ids = []
    skipped_existing = 0

    for f in files:
        fid = f.get("id", "")
        if not fid:
            continue
        if fid in existing_ids:
            skipped_existing += 1
            continue

        new_rows.append([
            fid,
            f.get("name", ""),
            f.get("createdTime", ""),
            f.get("webViewLink", ""),
        ])
        new_file_ids.append(fid)

    appended = append_rows(sheets, sheet_id, sheet_tab, new_rows)

    # --- Move processed files ---
    moved = 0
    move_errors = []

    for fid in new_file_ids[:appended]:
        try:
            did_move = move_file_to_folder(drive, fid, processed_folder_id)
            if did_move:
                moved += 1
        except Exception as e:
            move_errors.append({"file_id": fid, "error": str(e)})

    return jsonify({
        "ok": True,
        "drive_count": len(files),
        "new_appended": appended,
        "skipped_existing": skipped_existing,
        "moved_to_processed": moved,
        "move_errors_sample": move_errors[:5],
        "files_sample": files[:5],
        "appended_rows_sample": new_rows[:5],
    }), 200
