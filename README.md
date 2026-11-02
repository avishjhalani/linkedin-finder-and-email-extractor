# LinkedIn HR & Executive Email Finder (India v2.0) 🇮🇳

A specialized lead finder and verified email extractor targeted at **Senior Managers, HR, Talent Acquisition, HR Managers, and HR Heads** across India.

Directly uploads leads to your **Google Sheet** with strictly 3 columns formatted for **Yet Another Mail Merge (YAMM)** or **Mailmeteor**.

---

## ⚡ Key Features

- **India-Focused HR Discovery**: Pinpoints Senior Managers, HR, and Talent Acquisition leaders across Indian tech hubs (Bengaluru, Hyderabad, Gurgaon, Pune, Noida, Mumbai, Chennai, Delhi NCR).
- **Deliverability & MX Verification**: Validates corporate mail servers (Google Workspace, Microsoft 365, Proofpoint) and checks for published recruiter bio emails.
- **1-Click Google Sheets Upload**: Pushes strictly formatted 3 columns (`Name`, `Email`, `Company`) to your connected Google Sheet.
- **YAMM Mail Merge Ready**: Column headers and data structure match Yet Another Mail Merge and Mailmeteor out of the box.
- **CSV Export & Quick Copy**: Download 3-column CSV or copy all emails to clipboard with one click.
- **Privacy First**: API keys and webhook URLs are masked with zero client-side exposure.

---

## 🚀 Quick Start (Local)

1. Double-click `run.bat` (or run `python run.py`).
2. Your browser will automatically open `http://localhost:8000`.
3. Type any company (e.g., `Optum`, `Amazon`, `TCS`, `Flipkart`, `Infosys`) and click **Extract Leads**.
4. Click **Upload to Google Sheet** to sync all contacts immediately!

---

## 📊 Google Sheets Setup (Zero OAuth)

1. Open a Google Sheet.
2. In the top menu, go to **Extensions** &rarr; **Apps Script**.
3. Paste the Apps Script code provided in the app's **Google Sheets Guide** modal.
4. Click **Deploy** &rarr; **New deployment** &rarr; Select **Web app**.
5. Set **Who has access** to **Anyone**, then click **Deploy**.
6. Copy the Web app URL and paste it into **Settings** in the app.
