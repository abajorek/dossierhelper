# Google Drive Integration Setup Guide

Dossier Helper can scan and process files from multiple Google Drive accounts in addition to local files. This guide will walk you through setting up Google Drive integration.

## Features

- ✅ **Multi-Drive Support**: Connect up to multiple Google Drive accounts
- ✅ **Selective Folder Scanning**: Scan specific folders or entire drives
- ✅ **Automatic Authentication**: OAuth 2.0 secure authentication with token caching
- ✅ **Real-Time Progress**: Individual file download and processing progress
- ✅ **Seamless Integration**: Works alongside local file scanning

## Quick Start

### 1. Install Google Drive Dependencies

```bash
# Activate your virtual environment first
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Install Google Drive support
pip install -e ".[gdrive]"

# Or install everything including macOS support
pip install -e ".[all]"
```

### 2. Set Up Google Cloud Project & OAuth Credentials

#### Step 2.1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Enter a project name (e.g., "Dossier Helper")
4. Click **"Create"**

#### Step 2.2: Enable Google Drive API

1. In your project, go to **"APIs & Services"** → **"Library"**
2. Search for **"Google Drive API"**
3. Click on it and press **"Enable"**

#### Step 2.3: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. If prompted, configure the OAuth consent screen:
   - Choose **"External"** (unless you have a Google Workspace account)
   - Fill in the required fields:
     - App name: "Dossier Helper"
     - User support email: Your email
     - Developer contact: Your email
   - Click **"Save and Continue"**
   - Skip "Scopes" and "Test users" for now
   - Click **"Save and Continue"** → **"Back to Dashboard"**

4. Back in **"Credentials"**, click **"Create Credentials"** → **"OAuth client ID"** again
5. Select **"Desktop app"** as the application type
6. Give it a name (e.g., "Dossier Helper Desktop")
7. Click **"Create"**
8. Click **"Download JSON"** to download your credentials file
9. Save it somewhere safe (you'll reference this file in your config)

### 3. Configure Dossier Helper

#### Step 3.1: Create Credentials Directory

```bash
mkdir -p ~/.dossierhelper
```

#### Step 3.2: Move Credentials Files

Move your downloaded OAuth credentials file(s) to the credentials directory:

```bash
# For personal Google Drive
mv ~/Downloads/client_secret_*.json ~/.dossierhelper/personal_credentials.json

# For work/school Google Drive (if you have a second one)
mv ~/Downloads/client_secret_*.json ~/.dossierhelper/work_credentials.json
```

#### Step 3.3: Update example_config.yaml

Edit your `example_config.yaml` (or your custom config file):

```yaml
google_drives:
  # Personal Google Drive
  - name: "personal"
    enabled: true  # Set to true to enable
    folder_id: null  # null = scan entire drive
    client_secrets_file: "~/.dossierhelper/personal_credentials.json"
  
  # Work/School Google Drive
  - name: "work"
    enabled: true  # Set to true to enable
    folder_id: "1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT"  # Optional: specific folder
    client_secrets_file: "~/.dossierhelper/work_credentials.json"
```

**Finding a Folder ID:**
To scan only a specific folder instead of the entire drive:
1. Open Google Drive in your browser
2. Navigate to the folder you want to scan
3. Look at the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
4. Copy the `FOLDER_ID_HERE` part and use it as `folder_id` in your config

### 4. First Run - Authorization

When you run Dossier Helper for the first time with Google Drive enabled:

1. The app will open your default web browser
2. Sign in to your Google account (if not already signed in)
3. Review the permissions:
   - **"See and download all your Google Drive files"**
   - This is read-only access for scanning your files
4. Click **"Allow"**
5. You'll see a success message
6. Return to Dossier Helper - it's now connected!

The authorization is saved, so you won't need to do this again unless you revoke access.

## Usage

Once configured, Google Drive integration works automatically:

### In the GUI

1. Launch Dossier Helper: `python run_dossierhelper.py`
2. You'll see Google Drive status messages in the log:
   ```
   ☁️ Google Drive integration enabled for: personal, work
   🚀 Preparing to scan both local files AND cloud storage
   ```
3. When you click **"Run All"** or individual passes:
   - Local files are scanned first
   - Then each enabled Google Drive is scanned
   - Progress shows: `Scanning personal: Document.pdf`
   - Files are downloaded temporarily for processing
   - Individual file progress shows download progress

### File Processing Steps (with Progress)

For each Google Drive file, you'll see real-time progress:

1. **Loading file (0%)** - Initiating download
2. **Downloading from Google Drive (10-30%)** - Download progress with byte counts
3. **Reading metadata (30-45%)** - Extracting file information
4. **Extracting text content (45-70%)** - Reading document contents
5. **Classifying document (70-85%)** - Pattern matching and categorization
6. **Estimating effort (85-90%)** - Calculating time spent
7. **Complete (100%)** - Processing finished

Note: Finder tags are NOT applied to Google Drive files (only local files).

## Multiple Google Drives

You can connect as many Google Drives as you need:

```yaml
google_drives:
  - name: "personal"
    enabled: true
    folder_id: null
    client_secrets_file: "~/.dossierhelper/personal_credentials.json"
  
  - name: "university"
    enabled: true
    folder_id: "folder_id_for_teaching"
    client_secrets_file: "~/.dossierhelper/university_credentials.json"
  
  - name: "research_collab"
    enabled: true
    folder_id: "folder_id_for_research"
    client_secrets_file: "~/.dossierhelper/research_credentials.json"
```

**Important:** Each Google Drive needs its own set of OAuth credentials if they're different Google accounts. If multiple drives use the same Google account, you can reuse the same credentials file.

## Troubleshooting

### "Google Drive support not available"

**Solution:** Install the Google Drive dependencies:
```bash
pip install -e ".[gdrive]"
```

### "Failed to authenticate Google Drive"

**Causes:**
1. Credentials file not found at the specified path
2. Credentials file is invalid or corrupted
3. OAuth consent screen not properly configured

**Solutions:**
- Verify the path to your credentials file
- Re-download credentials from Google Cloud Console
- Make sure you completed the OAuth consent screen setup

### "Error scanning Google Drive: 403"

**Cause:** Google Drive API not enabled for your project

**Solution:** 
1. Go to Google Cloud Console
2. Navigate to "APIs & Services" → "Library"
3. Search for "Google Drive API"
4. Click "Enable"

### Slow download speeds

**Solutions:**
- Google Drive downloads can be slow for large files
- Consider using `folder_id` to scan only relevant folders
- Process Google Drive files in smaller batches

### Token expired or invalid

**Cause:** Cached authentication tokens can expire

**Solution:**
Delete the token file to force re-authentication:
```bash
rm ~/.dossierhelper/gdrive_credentials/token_personal.pickle
rm ~/.dossierhelper/gdrive_credentials/token_work.pickle
```

Then run Dossier Helper again to re-authenticate.

## Privacy & Security

### What access does Dossier Helper have?

- **Read-only access** to your Google Drive files
- Dossier Helper can:
  ✅ List your files
  ✅ Download file contents
  ✅ Read file metadata
- Dossier Helper cannot:
  ❌ Modify or delete your files
  ❌ Create new files
  ❌ Share your files with others

### Where are credentials stored?

- **OAuth credentials**: `~/.dossierhelper/personal_credentials.json` (or your specified path)
- **Access tokens**: `~/.dossierhelper/gdrive_credentials/token_*.pickle`

These files contain sensitive information. Keep them secure:
```bash
chmod 600 ~/.dossierhelper/*.json
chmod 600 ~/.dossierhelper/gdrive_credentials/*.pickle
```

### Revoking access

To revoke Dossier Helper's access to your Google Drive:

1. Go to [Google Account Permissions](https://myaccount.google.com/permissions)
2. Find "Dossier Helper" in the list
3. Click "Remove Access"

Then delete the local token files:
```bash
rm -rf ~/.dossierhelper/gdrive_credentials/
```

## Advanced Configuration

### Scanning specific folders only

Instead of scanning your entire drive, you can specify folder IDs:

```yaml
google_drives:
  - name: "teaching_materials"
    enabled: true
    folder_id: "1aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT"  # Your "Teaching" folder
    client_secrets_file: "~/.dossierhelper/credentials.json"
  
  - name: "research_papers"
    enabled: true
    folder_id: "9xY8wV7uT6sR5qP4oN3mL2kJ1iH0gF"  # Your "Research" folder
    client_secrets_file: "~/.dossierhelper/credentials.json"
```

### Temporarily disabling Google Drive

Set `enabled: false` to skip a Google Drive without removing the configuration:

```yaml
google_drives:
  - name: "personal"
    enabled: false  # Temporarily disabled
    folder_id: null
    client_secrets_file: "~/.dossierhelper/personal_credentials.json"
```

## Performance Considerations

- **First scan**: Scanning an entire Google Drive can take time, especially with many files
- **Subsequent scans**: Much faster since files are cached based on modification dates
- **Download overhead**: Each Google Drive file needs to be downloaded temporarily
- **Recommended**: Use `folder_id` to limit scanning to relevant folders

## Rate Limits

Google Drive API has usage quotas:
- **Queries per day**: 1,000,000,000
- **Queries per 100 seconds per user**: 1,000

Dossier Helper stays well within these limits for normal use. If you hit rate limits:
- Wait a few minutes and try again
- Scan smaller folder sets
- Use `folder_id` to be more selective

## Support

For issues specific to Google Drive integration:
1. Check this guide's Troubleshooting section
2. Verify your Google Cloud project setup
3. Test with a small folder first
4. Check the console output for error messages

For general Dossier Helper issues, see the main README.
