import os

from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from google.auth import default

import io
from PIL import Image
from PIL import ImageOps
from googleapiclient.http import MediaIoBaseDownload, MediaInMemoryUpload

from document_ai_client import process_document_ai
from schema_config import build_sheets_row
from notion_utils import *
from sheets_utils import *

app = Flask(__name__)


def drive_client():
    creds, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


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

def open_image(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    return ImageOps.exif_transpose(img)

def compress_to_jpeg_under_kb(image_bytes: bytes, max_kb: int = 300, max_dim: int = 1600) -> bytes:
    img = open_image(image_bytes)

    # Convert to RGB for JPEG
    if img.mode != "RGB":
        img = img.convert("RGB")

    # --- Resize if too large ---
    w, h = img.size
    max_side = max(w, h)

    if max_side > max_dim:
        scale = max_dim / float(max_side)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # --- Quality loop ---
    quality = 85
    best = None

    while quality >= 30:
        buf = io.BytesIO()
        img.save(
            buf,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling=2,   # 4:2:0 chroma subsampling (smaller)
        )
        out = buf.getvalue()
        best = out

        if len(out) <= max_kb * 1024:
            return out

        quality -= 10

    return best if best is not None else image_bytes


def upload_thumbnail(drive, thumbnails_folder_id: str, original_name: str, jpeg_bytes: bytes) -> str:
    safe_name = original_name or "image"
    thumb_name = f"thumb_{safe_name}"
    if not thumb_name.lower().endswith((".jpg", ".jpeg")):
        thumb_name += ".jpg"

    media = MediaInMemoryUpload(jpeg_bytes, mimetype="image/jpeg", resumable=False)

    created = drive.files().create(
        body={"name": thumb_name, "parents": [thumbnails_folder_id]},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()


    return created["id"]

def make_file_public_reader(drive, file_id: str) -> None:
    # Let Notion fetch the image
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
        fields="id",
    ).execute()


def drive_direct_image_url(file_id: str) -> str:
    return f"https://lh3.googleusercontent.com/d/{file_id}"

def download_drive_file_bytes(drive, file_id: str) -> bytes:
    req = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()

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
    thumbnails_folder_id = os.environ.get("THUMBNAILS_FOLDER_ID")


    if not uploads_folder_id:
        return jsonify({"ok": False, "error": "UPLOADS_FOLDER_ID env var not set"}), 500
    if not sheet_id or not sheet_tab:
        return jsonify({"ok": False, "error": "SHEET_ID and/or SHEET_TAB env vars not set"}), 500
    if not processed_folder_id:
        return jsonify({"ok": False, "error": "PROCESSED_FOLDER_ID env var not set"}), 500
    
    # NEW: Document AI env vars
    docai_project_id = os.environ.get("DOCUMENT_AI_PROJECT_ID")
    docai_location = os.environ.get("DOCUMENT_AI_LOCATION", "us")
    docai_processor_id = os.environ.get("DOCUMENT_AI_PROCESSOR_ID")
    docai_version_id = os.environ.get("DOCUMENT_AI_PROCESSOR_VERSION_ID")  # Optional, can be None
    
    if not docai_project_id or not docai_processor_id:
        return jsonify({"ok": False, "error": "DOCUMENT_AI_PROJECT_ID and/or DOCUMENT_AI_PROCESSOR_ID env vars not set"}), 500

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
        fields="files(id,name,mimeType,size,createdTime,webViewLink)",
        pageSize=50,
    ).execute()

    files = resp.get("files", [])

# --- Sheets de-dup + append/update ---
    sheets = sheets_client()
    ensure_header_with_schema(sheets, sheet_id, sheet_tab)
    existing_khadde = get_existing_khadde_ids(sheets, sheet_id, sheet_tab)

    new_rows = []
    updated_rows = []
    new_files_for_rows = []
    skipped_existing = 0

    for f in files:
        fid = f.get("id", "")
        if not fid:
            continue

        # Process with Document AI
        try:
            file_bytes = download_drive_file_bytes(drive, fid)
            extracted_data = process_document_ai(
                file_bytes=file_bytes,
                project_id=docai_project_id,
                location=docai_location,
                processor_id=docai_processor_id,
                processor_version_id=docai_version_id
            )
            
            # Build row from extracted data
            row = build_sheets_row(extracted_data)
            
            # Get Khadde value (first field in schema)
            khadde_value = str(int(row[0])) if row[0] is not None else ""
            
            # ADD THESE DEBUG LINES:
            print(f"DEBUG - Khadde value extracted: '{khadde_value}'")
            print(f"DEBUG - Existing Khadde map: {existing_khadde}")
            print(f"DEBUG - Is in existing? {khadde_value in existing_khadde}")
            
            # Check if this Khadde already exists
            if khadde_value and khadde_value in existing_khadde:
                # Update existing row
                row_number = existing_khadde[khadde_value]
                print(f"DEBUG - UPDATING row {row_number}")
                update_row(sheets, sheet_id, sheet_tab, row_number, row)
                updated_rows.append(khadde_value)
            else:
                # Append new row
                print(f"DEBUG - APPENDING new row")
                new_rows.append(row)
            
            # Store file metadata + extracted data for Notion
            new_files_for_rows.append({
                "id": fid,
                "name": f.get("name", ""),
                "mimeType": f.get("mimeType", ""),
                "size": f.get("size", ""),
                "createdTime": f.get("createdTime", ""),
                "webViewLink": f.get("webViewLink", ""),
                "extracted_data": extracted_data,
            })
            
        except Exception as e:
            print(f"Document AI processing failed for {fid}: {e}")
            # Skip this file if extraction fails
            continue


    appended = append_rows(sheets, sheet_id, sheet_tab, new_rows)

# --- Notion write/update ---
    notion_written = 0
    notion_updated = 0
    notion_failed = 0
    notion_errors = []

    notion, notion_db_id = notion_client()
    
    # Get existing Notion pages by Khadde
    existing_notion_khadde = {}
    if notion is not None:
        try:
            existing_notion_khadde = get_existing_notion_khadde_ids(notion, notion_db_id)
            print(f"DEBUG - Existing Notion Khadde map: {existing_notion_khadde}")
        except Exception as e:
            print(f"Failed to get existing Notion pages: {e}")
    
    to_write = new_files_for_rows# --- Notion write/update ---
    notion_written = 0
    notion_updated = 0
    notion_failed = 0
    notion_errors = []

    notion, notion_db_id = notion_client()
    
    # Get existing Notion pages by Khadde
    existing_notion_khadde = {}
    if notion is not None:
        try:
            existing_notion_khadde = get_existing_notion_khadde_ids(notion, notion_db_id)
            print(f"DEBUG - Existing Notion Khadde map: {existing_notion_khadde}")
        except Exception as e:
            print(f"Failed to get existing Notion pages: {e}")
    
    to_write = new_files_for_rows

    thumb_created = 0
    thumb_failed = 0
    thumb_errors = []
    thumb_file_ids = []

    cover_set = 0
    cover_failed = 0
    cover_errors = []
    cover_debug = []

    if notion is not None:
        for f in to_write:
            fid = f["id"]
            name = f.get("name", "")
            extracted_data = f.get("extracted_data", {})
            
            if not extracted_data:
                continue

            try:
                # Get Khadde value from extracted data
                khadde_data = extracted_data.get("serial_number", {})
                khadde_value = khadde_data.get("value")
                
                if khadde_value is not None:
                    # Normalize to string without decimal
                    if isinstance(khadde_value, float) and khadde_value == int(khadde_value):
                        khadde_value = str(int(khadde_value))
                    else:
                        khadde_value = str(khadde_value)
                else:
                    khadde_value = ""
                
                print(f"DEBUG - Notion Khadde value: '{khadde_value}'")
                
                # Check if page exists
                if khadde_value and khadde_value in existing_notion_khadde:
                    # Update existing page
                    page_id = existing_notion_khadde[khadde_value]
                    print(f"DEBUG - UPDATING Notion page {page_id}")
                    update_notion_page_from_extraction(notion, page_id, extracted_data)
                    notion_updated += 1
                else:
                    # Create new page
                    print(f"DEBUG - CREATING new Notion page")
                    page_id = create_notion_row_from_extraction(
                        notion,
                        notion_db_id,
                        extracted_data
                    )
                    notion_written += 1

                if thumbnails_folder_id:
                    try:
                        mime = (f.get("mimeType") or "").lower()
                        name_lower = (name or "").lower()
                        is_heic = mime in ("image/heic", "image/heif") or name_lower.endswith((".heic", ".heif"))

                        if is_heic:
                            cover_failed += 1
                            cover_errors.append({
                                "file_id": fid,
                                "page_id": page_id,
                                "error": "HEIC files do not support Notion cover in this pipeline. Upload JPEG to enable cover.",
                                "mimeType": mime,
                                "file_name": name,
                            })
                            # Skip thumbnail + cover for HEIC
                            continue
                        source_bytes = download_drive_file_bytes(drive, fid)

                        # 2) Compress + upload thumbnail
                        thumb_jpeg = compress_to_jpeg_under_kb(source_bytes, max_kb=300)
                        thumb_id = upload_thumbnail(drive, thumbnails_folder_id, name, thumb_jpeg)

                        # 3) Make thumbnail fetchable by Notion + set cover
                        make_file_public_reader(drive, thumb_id)
                        thumb_url = drive_direct_image_url(thumb_id)

                        try:
                            set_notion_cover_external(notion, page_id, thumb_url)

                            page_after = notion.pages.retrieve(page_id=page_id)
                            cover_after = page_after.get("cover")

                            cover_debug.append({
                                "file_id": fid,
                                "page_id": page_id,
                                "thumb_id": thumb_id,
                                "thumb_url": thumb_url,
                                "cover_after": cover_after,
                            })

                            if cover_after:
                                cover_set += 1
                            else:
                                cover_failed += 1
                                cover_errors.append({
                                    "file_id": fid,
                                    "page_id": page_id,
                                    "error": "Cover missing after update (Notion stored no cover).",
                                    "thumb_url": thumb_url,
                                })

                        except Exception as e:
                            cover_failed += 1
                            cover_errors.append({
                                "file_id": fid,
                                "page_id": page_id,
                                "error": str(e),
                                "thumb_url": thumb_url,
                            })

                        thumb_file_ids.append(thumb_id)
                        thumb_created += 1

                    except Exception as e:
                        thumb_failed += 1
                        thumb_errors.append({
                            "file_id": fid,
                            "error": str(e),
                            "name": name,
                        })
            except Exception as e:
                notion_failed += 1
                notion_errors.append({"file_id": fid, "error": str(e)})



    # --- Move processed files ---
    moved = 0
    move_errors = []

    for f in to_write:
        fid = f["id"]
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
        "updated_existing": len(updated_rows),
        "updated_khadde_values": updated_rows[:5],
        "notion_enabled": notion is not None,
        "notion_written": notion_written,
        "notion_updated": notion_updated,
        "notion_failed": notion_failed,
        "notion_errors_sample": notion_errors[:5],
        "moved_to_processed": moved,
        "move_errors_sample": move_errors[:5],
        "files_sample": files[:5],
        "appended_rows_sample": new_rows[:5],
        "thumbnails_enabled": bool(thumbnails_folder_id),
        "thumbnails_created": thumb_created,
        "thumbnails_failed": thumb_failed,
        "thumbnail_errors_sample": thumb_errors[:5],
        "thumbnail_file_ids_sample": thumb_file_ids[:5],
        "cover_set": cover_set,
        "cover_failed": cover_failed,
        "cover_errors_sample": cover_errors[:5],
        "cover_debug_sample": cover_debug[:2],
    }), 200
