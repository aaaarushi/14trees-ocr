# 14Trees OCR Extractor Pipeline

The goal of this project was to allow a user to upload an image via a Google Form, and then run a script on this file and input the information from the photo into a Google Sheets.

The general pipeline is Google Forms file upload -> triggers an App Script within Google Forms -> makes a post request to the Cloud Run which contains the Python script -> Python script analyzes the image, moves the image from an unprocessed to a processed folder, and updates the image's information in a Google Sheets.

This documentation allows you to update any of these steps.

## Architecture Overview

The system uses **Google Cloud Document AI** for OCR extraction with the following flow:

1. **Image Upload**: User uploads image via Google Form → stored in Drive uploads folder
2. **Preprocessing**: Image is cropped and enhanced for optimal OCR
3. **Extraction**: Document AI custom extractor pulls structured fields from the card
4. **Data Storage**: Extracted data written to both Google Sheets and Notion database
5. **File Management**: Processed images moved to processed folder, thumbnails generated

### Key Components

- **`preprocessing.py`**: Detects card border, crops, enhances contrast/sharpness for OCR
- **`document_ai_client.py`**: Calls Document AI API to extract fields from preprocessed image
- **`schema_config.py`**: Maps extracted fields to Sheets/Notion format
- **`fields.py`**: Single source of truth for all extraction fields (edit this to add/remove fields)
- **`main.py`**: Orchestrates the entire pipeline

## Document AI Extraction

The system uses a **custom Document AI extractor** to pull structured data from card images. The extractor is trained on labeled examples and returns confidence scores for each field.

### Preprocessing Pipeline

Before extraction, images go through:
1. **Border detection**: Adaptive thresholding finds card outline (handles various backgrounds)
2. **Cropping**: Removes background, focuses on card content
3. **Enhancement**: Boosts contrast (1.3x), sharpness (1.5x), brightness (1.1x)
4. **Resize**: Scales to max 1600px for optimal Document AI performance

All preprocessing happens in `preprocessing.py` using PIL and OpenCV. The preprocessed image (not the original) is sent to Document AI and used for thumbnails.

### Configuring Extraction Fields

**All fields are defined in `cloudrun/fields.py`**. This is the single source of truth—edit this file to add/remove/reorder fields across the entire system.

Example field definition:
```python
{
    "name": "serial_number",              # Must match Document AI extractor
    "type": "number",                     # text, number, or checkbox
    "display_name": "Khadde",             # Column name in Sheets/Notion
    "description": "Unique identifier"
}
```

Field types:
- `text`: String values (supports Devanagari script)
- `number`: Numeric values
- `checkbox`: Boolean indicators

Field order in `fields.py` determines column order in Sheets and property order in Notion.

### Managing the Document AI Extractor

The Document AI processor lives in Google Cloud Console at:
https://console.cloud.google.com/ai/document-ai/locations/us/processors/4fb4e11231940dd2

**To add/modify extracted fields:**
1. Go to Document AI processor → "Edit Schema" → Add/modify field labels
2. Upload labeled training examples showing new fields
3. Retrain the model version
4. Update `cloudrun/fields.py` to match new schema
5. Redeploy Cloud Run with new processor version ID (see environment variables section)

Current processor uses version `e826fbbfc14d8274`. You can create new versions without breaking production by training separately, then updating `DOCUMENT_AI_PROCESSOR_VERSION_ID` when ready.

## Google Sheets Integration

Extracted data automatically populates Google Sheets with deduplication:
- **Headers**: Generated from `fields.py` display names
- **New records**: Appended as new rows
- **Existing records**: Updated in-place (matched by Khadde/serial_number)

The system reads existing Khadde values, checks each new extraction, and either updates the matching row or appends a new one. Headers are auto-created if missing.

## Notion Integration

Data syncs to Notion database with the same deduplication logic:
- **Properties**: Auto-mapped from `fields.py` (text → rich_text, number → number, checkbox → checkbox)
- **Cover images**: Compressed thumbnails from preprocessed images (<300KB)
- **Title field**: `plot_name` is marked as `is_notion_title: True` in `fields.py`

Notion pages are created/updated based on Khadde matching. The first field in `fields.py` is used as the unique identifier.

**Setting up Notion:**
1. Create integration at https://www.notion.so/my-integrations
2. Copy API key to `NOTION_API_KEY` environment variable
3. Share your database with the integration
4. Copy database ID to `NOTION_DATABASE_ID`
5. Manually create properties in Notion matching your `fields.py` display names and types

## Quick Start for Common Tasks

### Adding a new extraction field
1. Add field to Document AI processor in Cloud Console
2. Add to `cloudrun/fields.py`:
   ```python
   {
       "name": "tree_species",           # Match Document AI exactly
       "type": "text",                   # text, number, or checkbox
       "display_name": "Species"         # Sheets/Notion column name
   }
   ```
3. Redeploy Cloud Run (see deployment section below)
4. Field automatically appears in Sheets and Notion on next upload

### Modifying preprocessing
Edit `cloudrun/preprocessing.py`:
- Adjust crop sensitivity: `_detect_card_border_adaptive()` parameters
- Change enhancement: `_enhance_for_ocr()` contrast/sharpness values
- Modify resize limit: `_resize_if_needed()` target_size parameter

### Testing Document AI locally
```bash
cd cloudrun
python document_ai_client.py  # Uses test image and prints extracted fields
```

## Updating the file in Cloud Run

Do this if you want to change the Python file that is being run in Cloud Run

### Open Terminal

### Install gcloud with Homebrew

```bash
brew install --cask google-cloud-sdk
```

Restart terminal

### Install gcloud if you don't have Homebrew

Use the installer https://cloud.google.com/sdk/docs/install

Restart terminal

### Initialize GCloud

```bash
gcloud init
```

Follow the browser login with

user: tech1@14trees.org
pw: 14TreesPune

Select the project: artful-lane-485410-j1


### Confirm you are in the correct Google Cloud project

```bash
gcloud auth list
gcloud config get-value project
```

If the project is not `artful-lane-485410-j1`, set it:

```bash
gcloud config set project artful-lane-485410-j1
```

### Go to the Cloud Run service directory

The deployable service lives in the `cloudrun/` folder of the repo:

(`cd` to that your location’s `cloudrun/` folder)

### Pull the latest code from GitHub

Do this if someone else may have pushed changes:

```bash
git pull
```

### Redeploy the service (code-only redeploy)

This redeploys the code and keeps existing Cloud Run environment variables. Note you must be in the directory your main.py file is in:

```bash
gcloud run deploy site-processor \
  --source . \
  --region us-central1 \
  --concurrency 1
```

### Confirm deploy succeeded and get the service URL

```bash
gcloud run services describe site-processor \
  --region us-central1 \
  --format="value(status.url)"
```

At this point, your code is successfuly in the Cloud Run!


## Linking the existing Cloud Run code to a new spreadsheet or folder

Do this if you want to change the Google files that are being edited by the Python script

### Redeploy with new environment variables

If you want to link your code to a new spreadsheet or folder, go to that file and share it with:

cloudrun-site-processor@artful-lane-485410-j1.iam.gserviceaccount.com

Then, copy the "ID" of that folder, file, or spreadsheet, and redeploy the Cloud Run with new environment variables. 

You can get the ID of a Google Drive file by looking in the URL when you open it in a browser and the ID will be after /d/ or /folders/.

The environment variables that are already preloaded include:

- UPLOADS_FOLDER_ID: 1PFDx20k8cZQm_y0fV7Zdr8kPctZLXG7U1_JoFHGYWEgR_AbfZfnapdxdU--pk--11YH-l1HN
- PROCESSED_FOLDER_ID: 1RyX7IsrhLQy0IvswpQxNftH4M_klNgOF
- SHEET_ID: 1q2P1NMU-32EnVptP62-FRcptAMaB6PioqsAUO8FtQPY
- SHEET_TAB: Locations
- WEBHOOK_SECRET: 14trees-6f3f1c9a8d8a4c1bb9c0a2e6a4d2f7c1

- NOTION_API_KEY: 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
- NOTION_DATABASE_ID: 2f4ff57a145180899b0de237882eb53f
- THUMBNAILS_FOLDER_ID: 1gGR0fRMiqZ-3X2Kzsvs1cIdHCR3kcqo_

- DOCUMENT_AI_PROJECT_ID: artful-lane-485410-j1
- DOCUMENT_AI_LOCATION: us
- DOCUMENT_AI_PROCESSOR_ID: 4fb4e11231940dd2
- DOCUMENT_AI_PROCESSOR_VERSION_ID: e826fbbfc14d8274

You will have to change the DOCUMENT_AI variables if you create a new Google Cloud Document AI Custom Extractor, and you can find the IDs in the Web UI: https://console.cloud.google.com/ai/document-ai/locations/us/processors/4fb4e11231940dd2/v2/overview?authuser=2&hl=en&project=artful-lane-485410-j1

You only have to redeploy with enviroment variables if you want to change them or add an environment variable.

```bash
gcloud run deploy site-processor \
  --source . \
  --region us-central1 \
  --concurrency 1 \
  --set-env-vars \
UPLOADS_FOLDER_ID=...,PROCESSED_FOLDER_ID=...,SHEET_ID=...,SHEET_TAB=...,WEBHOOK_SECRET=...
```

This only applies to files in Google Drive. Other systems may need further API authentification. 

### Test the deployed code

Replace `<WEBHOOK_SECRET>` with the current secret value:

```bash
curl -s -X POST "https://site-processor-579264721246.us-central1.run.app" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: <WEBHOOK_SECRET>" \
  | python3 -m json.tool
```

Current secret value: 14trees-6f3f1c9a8d8a4c1bb9c0a2e6a4d2f7c1

## Deploying Cloud Run code automatically

Generally, you can always send the POST request to Cloud Run from your terminal. If you want the Python script to run automatically, you can create a trigger from a Google Form submission

### Google Form submission trigger

Currently the service is deployed from a trigger created by a Google Form submission.

This occurs by writing code in the Apps Script imbeded in the Google Form.

The Google Form's Apps Script currently has the following code:

```
const CLOUD_RUN_URL = "https://site-processor-579264721246.us-central1.run.app";
const WEBHOOK_SECRET = "14trees-6f3f1c9a8d8a4c1bb9c0a2e6a4d2f7c1";

function onFormSubmit(e) {
  const payload = {
    source: "apps_script_onFormSubmit",
    submittedAt: new Date().toISOString(),
  };

  const resp = UrlFetchApp.fetch(CLOUD_RUN_URL, {
    method: "post",
    contentType: "application/json",
    headers: {
      "X-Webhook-Secret": WEBHOOK_SECRET,
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  console.log("Cloud Run status:", resp.getResponseCode());
  console.log(resp.getContentText());
}
```

Paste this same code into the Google Form that you are using.

# Common issues

* “Reauthentication required / Please enter your password”

  * This is your Mac login password (Keychain). Enter it and rerun the deploy.

* Permission denied

  * You need Cloud Run deploy permissions in the project (Project Owner/Editor or equivalent Cloud Run roles).
