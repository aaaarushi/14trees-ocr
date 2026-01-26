# Running scripts with Cloud Run

The goal of this project was to allow a user to upload an image via a Google Form, and then run a script on this file and input the information from the photo into a Google Sheets.

The general pipeline is Google Forms file upload -> triggers an App Script within Google Forms -> makes a post request to the Cloud Run which contains the Python script -> Python script analyzes the image, moves the image from an unprocessed to a processed folder, and updates the image's information in a Google Sheets.

This documentation allows you to update any of these steps.

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

This redeploys the code and keeps existing Cloud Run environment variables:

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
