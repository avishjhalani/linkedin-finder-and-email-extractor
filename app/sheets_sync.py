import csv
import io
import datetime
from typing import List, Dict, Any, Optional
import httpx
import gspread
from google.oauth2.service_account import Credentials

GOOGLE_APPS_SCRIPT_TEMPLATE = """/**
 * Google Apps Script for LinkedIn Lead Exporter
 * 1. Open your Google Sheet
 * 2. Click Extensions > Apps Script
 * 3. Delete any default code and paste this entire code
 * 4. Click 'Deploy' > 'New deployment'
 * 5. Select type: 'Web app'
 * 6. Set Description: 'Lead Webhook'
 * 7. Set 'Who has access': 'Anyone' (IMPORTANT!)
 * 8. Click 'Deploy' and copy the 'Web app URL'
 * 9. Paste that URL into the LinkedIn Finder app!
 */

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
      // Format header row bold with nice background
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
      message: "Successfully pushed " + leads.length + " leads to Google Sheet!",
      count: leads.length
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
"""

def push_to_webhook(webhook_url: str, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pushes leads to Google Apps Script Webhook URL.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return {"success": False, "error": "Invalid Webhook URL provided."}
    
    try:
        # Google Apps Script web apps return 302 redirects which need to be followed
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.post(webhook_url, json={"leads": leads})
            
            if resp.status_code in [200, 201]:
                try:
                    data = resp.json()
                    return {"success": True, "count": len(leads), "details": data}
                except Exception:
                    return {"success": True, "count": len(leads), "details": resp.text}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}"
                }
    except Exception as e:
        return {"success": False, "error": str(e)}

def push_to_service_account(
    credentials_json_path: str,
    spreadsheet_id_or_url: str,
    leads: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Pushes leads using Google Cloud Service Account credentials JSON via gspread.
    """
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(credentials_json_path, scopes=scopes)
        client = gspread.authorize(creds)
        
        if spreadsheet_id_or_url.startswith("http"):
            sh = client.open_by_url(spreadsheet_id_or_url)
        else:
            sh = client.open_by_key(spreadsheet_id_or_url)
            
        worksheet = sh.get_worksheet(0)
        
        # Check if empty, append header
        existing = worksheet.get_all_values()
        if not existing:
            worksheet.append_row([
                "First Name", "Last Name", "Email Address", "Job Title",
                "Company", "LinkedIn Profile", "Email Confidence", "Date Added"
            ])
            
        today = datetime.date.today().isoformat()
        rows = [
            [
                l.get("first_name", ""),
                l.get("last_name", ""),
                l.get("email", ""),
                l.get("job_title", ""),
                l.get("company", ""),
                l.get("linkedin_url", ""),
                l.get("confidence", ""),
                today
            ]
            for l in leads
        ]
        worksheet.append_rows(rows)
        return {"success": True, "count": len(leads)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_yamm_csv(leads: List[Dict[str, Any]]) -> str:
    """
    Generates a CSV string formatted specifically for Yet Another Mail Merge (YAMM).
    Standard YAMM Merge Tags:
    - {{First Name}}
    - {{Last Name}}
    - {{Job Title}}
    - {{Company}}
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    headers = [
        "First Name",
        "Last Name",
        "Email Address",
        "Job Title",
        "Company",
        "LinkedIn Profile",
        "Email Confidence",
        "Date Added"
    ]
    writer.writerow(headers)
    
    today = datetime.date.today().isoformat()
    for lead in leads:
        writer.writerow([
            lead.get("first_name", ""),
            lead.get("last_name", ""),
            lead.get("email", ""),
            lead.get("job_title", ""),
            lead.get("company", ""),
            lead.get("linkedin_url", ""),
            lead.get("confidence", ""),
            today
        ])
        
    return output.getvalue()
