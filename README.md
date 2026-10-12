# 🚀 LinkedIn Finder & Email Extractor (YAMM-Ready)

A powerful, fast, and automated tool to search for LinkedIn profiles using natural language queries (e.g., **"find 10 hr working at optum"**), extract & verify corporate emails, and push them directly to **Google Sheets** for cold email outreach using **Yet Another Mail Merge (YAMM)**.

---

## ✨ Features

- 🔍 **Natural Language Queries**: Simply type queries like `"find 10 hr working at optum"`, `"15 software engineers at google in london"`, or `"recruiters at amazon"`.
- ⚡ **LinkedIn X-Ray Engine**: Discovers public LinkedIn profiles with accurate names, job titles, companies, locations, and direct profile URLs without getting banned or rate-limited.
- 📧 **Smart Corporate Email Extraction**:
  - Automatically identifies company domain (e.g., `optum.com`).
  - Scrapes public emails mentioned directly in candidate bios/snippets.
  - Generates standard enterprise email formats (`first.last@domain.com`, `flast@domain.com`, etc.).
  - Performs live **DNS MX record verification** (e.g., Proofpoint, Google Workspace, Microsoft 365) to confirm the domain receives mail.
  - Optional **Hunter.io API** enrichment support.
  - Dropdown on each lead to switch between pattern permutations on the fly.
- 📊 **One-Click Push to Google Sheets**:
  - **Option 1: Google Apps Script Webhook (Recommended)** — zero OAuth setup, paste a 10-line script into your Google Sheet, and rows stream in instantly!
  - **Option 2: Google Service Account** (`credentials.json` + `gspread`).
- 📥 **YAMM-Ready CSV Export**: Instant download of CSV pre-formatted with merge columns ready for Yet Another Mail Merge.
- 💻 **Modern Web Interface**: Glassmorphic dark UI, live progress indicators, and inline editing.

---

## 🏃 Quick Start

### 1. Launch the Application

Simply double-click:
```cmd
run.bat
```
Or run in PowerShell / Command Prompt:
```powershell
python run.py
```

The application will start the local server and automatically open your default browser at:
👉 **`http://localhost:8000`**

---

## 💡 How to Use

### Step 1: Search for Candidates
In the search bar, type your query. For example:
> `find 10 hr working at optum`

The tool automatically parses:
- **Role**: HR / Human Resources
- **Company**: Optum
- **Company Domain**: `optum.com` (MX records verified via Proofpoint)
- **Target Count**: 10

Click **"Find Leads"** (or press Enter). Within seconds, candidate profiles with their discovered email addresses will appear in the table.

### Step 2: Review & Customize Emails
- The table shows candidate **Name**, **Job Title**, **Company**, and **Discovered Email**.
- Each candidate has a confidence badge:
  - 🟢 **Verified (Public Bio)**: Found directly in public snippet or web index.
  - 🔵 **MX Verified (first.last)**: Corporate email pattern backed by active mail server.
  - 🟣 **Hunter Verified**: Enriched via Hunter.io API (if API key provided).
- You can change the format using the pattern dropdown or edit the email address inline.

---

## 📊 Pushing Leads to Google Sheets (for YAMM)

### Fast Setup (Google Apps Script Webhook — 60 Seconds)

1. Open a new or existing **Google Sheet** (e.g., titled `Optum HR Leads`).
2. In Google Sheets, click **Extensions** &rarr; **Apps Script**.
3. Delete any default code in `Code.gs` and paste the following snippet:

```javascript
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var payload = JSON.parse(e.postData.contents);
    var leads = payload.leads || [];
    
    // Check if headers exist, if not create them
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "First Name",
        "Last Name",
        "Email Address",
        "Job Title",
        "Company",
        "LinkedIn Profile",
        "Email Confidence",
        "Date Added"
      ]);
      var headerRange = sheet.getRange(1, 1, 1, 8);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#E8F0FE");
    }
    
    var today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
    var rowsToAdd = [];
    
    for (var i = 0; i < leads.length; i++) {
      var lead = leads[i];
      rowsToAdd.push([
        lead.first_name || "",
        lead.last_name || "",
        lead.email || "",
        lead.job_title || "",
        lead.company || "",
        lead.linkedin_url || "",
        lead.confidence || "",
        today
      ]);
    }
    
    if (rowsToAdd.length > 0) {
      var startRow = sheet.getLastRow() + 1;
      var range = sheet.getRange(startRow, 1, rowsToAdd.length, 8);
      range.setValues(rowsToAdd);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      count: leads.length
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
```

4. Click **Deploy** (top right) &rarr; **New deployment**.
5. Click the gear icon next to "Select type", choose **Web app**.
6. Set **Who has access** to **Anyone** *(essential so your local script can send rows)*.
7. Click **Deploy** and copy the **Web app URL** (`https://script.google.com/macros/s/.../exec`).
8. In the app:
   - Click **"Push to Google Sheet"** (or open **Settings**).
   - Paste your Webhook URL and click **"Push Now"**.
   - Your leads will immediately appear in your Google Sheet!

---

## ✉️ Sending Mails with Yet Another Mail Merge (YAMM)

1. Open your Google Sheet containing the pushed leads.
2. Ensure you have the **Yet Another Mail Merge** add-on installed in Google Workspace.
3. Open Gmail and create a **Draft** email with merge tags:
   ```text
   Subject: Quick question regarding {{Company}} HR

   Hi {{First Name}},

   I came across your profile and noticed your role as {{Job Title}} at {{Company}}.
   
   [Your personalized message here...]

   Best regards,
   [Your Name]
   ```
4. Return to your Google Sheet:
   - Click **Extensions** &rarr; **Yet Another Mail Merge: Mail Merge for Gmail** &rarr; **Start Mail Merge**.
   - Select your recipient column: `Email Address`.
   - Select your draft.
   - Click **Send Emails**!

---

## 📁 Project Architecture

```
d:\linkedin finder and email extractor\
├── app/
│   ├── main.py                # FastAPI server & REST API
│   ├── query_parser.py        # Natural language parser for prompt queries
│   ├── linkedin_finder.py     # LinkedIn search & profile discovery
│   ├── email_extractor.py     # Domain lookup, MX verification & pattern synthesis
│   ├── sheets_sync.py         # Google Sheets Webhook and YAMM CSV exporter
│   └── static/
│       ├── index.html         # Modern web dashboard
│       ├── app.js             # Real-time search, filters, and export logic
│       └── style.css          # Badges & animations
├── run.py                     # Python server runner
├── run.bat                    # Windows 1-click launcher
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

---

## 🛡️ Best Practices & Legal Notes

- This tool discovers **publicly indexed LinkedIn profiles** via search engines without violating LinkedIn login sessions or scraping private account pages.
- Email generation uses standard enterprise RFC patterns combined with real-time MX DNS server validation.
- When doing cold outreach via YAMM, always adhere to CAN-SPAM / GDPR guidelines, include an unsubscribe option, and maintain reasonable sending volumes.
