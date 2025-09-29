# Dossier Helper - Quick Start Guide

Get up and running with Dossier Helper in 5 minutes!

## 🚀 Basic Setup (Local Files Only)

### Step 1: Install
```bash
cd /Users/andrewbajorek/Documents/GitHub/dossierhelper
source .venv/bin/activate  # If you already have a venv
# OR
python3 -m venv .venv && source .venv/bin/activate

pip install -e '.[mac]'  # With macOS Finder tags support
```

### Step 2: Run
```bash
python run_dossierhelper.py
# or
dossierhelper
```

### Step 3: Use
1. Click **"Run All"** to scan, classify, and report on all files
2. Watch the progress bars:
   - Overall progress with ASCII duck animation 🦆
   - Individual file progress (0-100%) with step-by-step updates
3. Get your report: `~/Documents/DossierReports/dossier_report_all.csv`

**That's it!** Your files in ~/Documents and ~/Desktop are now classified and tagged.

---

## ☁️ Advanced Setup (with Google Drive)

Want to also scan Google Drive files? Follow these steps:

### Step 1: Install Google Drive Support
```bash
source .venv/bin/activate
pip install -e '.[gdrive]'
```

### Step 2: Get OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Dossier Helper")
3. Enable **Google Drive API**
4. Create **OAuth 2.0 credentials** (Desktop app)
5. Download the JSON file

### Step 3: Save Credentials
```bash
mkdir -p ~/.dossierhelper
mv ~/Downloads/client_secret_*.json ~/.dossierhelper/personal_credentials.json
```

### Step 4: Configure
Edit `example_config.yaml`:

```yaml
google_drives:
  - name: "personal"
    enabled: true  # Change to true
    folder_id: null
    client_secrets_file: "~/.dossierhelper/personal_credentials.json"
```

### Step 5: Run & Authenticate
```bash
python run_dossierhelper.py
```

On first run:
- Your browser will open
- Sign in to Google
- Click "Allow"
- Return to Dossier Helper ✅

**Done!** Now scanning both local files AND Google Drive.

---

## 📊 What to Expect

### Progress Display

**Overall Progress Bar:**
```
[LS] ████████████> o)░░░░░░░░ [52.3%]
```
Duck swims from Lemonade Stand [LS] to Grape [GR]!

**Individual File Progress:**
```
Current File Progress: ██████████░░░░░ 65%
☁️ Downloading from Google Drive (512KB/1MB) (30%)
📄 Extracting text content (65%)
```

### Processing Steps

Each file goes through:
1. 📂 **Loading** (0-30%) - Local access or cloud download
2. 📋 **Metadata** (30-45%) - File properties
3. 📄 **Text Extraction** (45-70%) - Document parsing
4. 🔍 **Classification** (70-85%) - Pattern matching
5. ⏱️ **Effort Estimation** (85-90%) - Time metrics
6. 🏷️ **Finder Tags** (90-100%) - Color coding (local only)
7. 🎉 **Complete!** (100%)

### Output

**CSV Report** (`~/Documents/DossierReports/dossier_report_all.csv`):
- Path to each file
- Primary category (Teaching, Scholarship, Service, etc.)
- All matching categories
- Subcategories
- Portfolio destination
- Classification score
- Rationale
- Estimated hours spent

**Finder Tags** (local files only):
- 🟢 Green = Teaching
- 🔵 Blue = Scholarship
- 🟡 Yellow = Service
- 🟣 Purple = Research
- 🟠 Orange = Administration

---

## 🎮 Tips & Tricks

### Scan Specific Years
```
Limit to calendar years: [2023] [2024]
```
Only processes files from the selected years.

### Run Individual Passes
- **Pass 1**: Fast surface scan (discover files)
- **Pass 2**: Deep analysis (classify & tag)
- **Pass 3**: Generate report

### Entertainment Mode
Watch for:
- "How embarrassing!" - Unclassified files
- "OH MY GAAAWD!" - Large files
- "JORB WELL DONE!" - Completion
- "The Cheat is grounded!" - Random commentary

### Google Drive Optimization
```yaml
google_drives:
  - name: "teaching_only"
    enabled: true
    folder_id: "1aB2cD3eF..."  # Specific folder ID
```
Scan just one folder instead of entire drive for faster processing.

---

## 🔧 Troubleshooting

### "No files found"
- Check that `search_roots` in config points to directories with files
- Verify file extensions are in `file_filters.include_extensions`
- Make sure directories aren't in `file_filters.exclude_dirs`

### "Google Drive support not available"
```bash
pip install -e '.[gdrive]'
```

### "Failed to authenticate Google Drive"
- Verify credentials file exists at specified path
- Check Google Drive API is enabled in Cloud Console
- Try deleting token: `rm ~/.dossierhelper/gdrive_credentials/token_*.pickle`

### Slow Processing
- Use `folder_id` for Google Drive to scan specific folders
- Limit scan to specific years
- Process in smaller batches

---

## 📚 Next Steps

- **Learn More**: Read [docs/NEW_FEATURES.md](docs/NEW_FEATURES.md)
- **Google Drive Details**: See [docs/GOOGLE_DRIVE_SETUP.md](docs/GOOGLE_DRIVE_SETUP.md)
- **Configuration**: Explore [example_config.yaml](example_config.yaml)
- **Customize**: Add your own classification patterns
- **Organize**: Use Finder tags to sort files visually

---

## 💡 Common Use Cases

### Academic Dossier Building
```yaml
search_roots:
  - ~/Documents
  - ~/Desktop
  
google_drives:
  - name: "university"
    enabled: true
```
Scan local and university Google Drive for teaching/research materials.

### Collaborative Research
```yaml
google_drives:
  - name: "lab_shared"
    enabled: true
    folder_id: "1xY2zA3bC..."  # Shared research folder
```
Only scan the shared research collaboration folder.

### Comprehensive Review
```yaml
search_roots:
  - ~/Documents
  - ~/Desktop
  - ~/Downloads
  
google_drives:
  - name: "personal"
    enabled: true
  - name: "work"
    enabled: true
```
Scan everything for complete coverage.

---

## 🎉 You're Ready!

Launch Dossier Helper and watch your files get:
✅ Discovered from local and cloud storage
✅ Classified by category and subcategory  
✅ Tagged with color-coded Finder labels
✅ Reported in a comprehensive CSV
✅ Entertained with Strong Bad commentary

**Happy organizing!** 🎮💪📚
