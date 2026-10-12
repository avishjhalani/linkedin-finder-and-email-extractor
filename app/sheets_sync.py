import csv
import io
import datetime
from typing import List, Dict, Any, Optional
import httpx
import gspread
from google.oauth2.service_account import Credentials

GOOGLE_APPS_SCRIPT_TEMPLATE = """/**
 * Google Apps Script for LinkedIn Lead Exporter
 * Format: Name | Email | Company (Strictly 3 columns)
 *
 * 1. Open your Google Sheet
 * 2. Click Extensions > Apps Script
 * 3. Replace all code with this snippet
 * 4. Click 'Deploy' > 'Manage deployments' > Edit (or 'New deployment')
 * 5. Version: 'New version', Who has access: 'Anyone'
 * 6. Click 'Deploy'
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var payload = JSON.parse(e.postData.contents);
    var leads = payload.leads || [];
    
    // Check if headers exist, if not create them (Name, Email, Company)
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Name", "Email", "Company"]);
      var headerRange = sheet.getRange(1, 1, 1, 3);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#E8F0FE");
    }
    
    var rowsToAdd = [];
    
    for (var i = 0; i < leads.length; i++) {
      var lead = leads[i];
      var name = lead.name || lead.full_name || (lead.first_name + " " + lead.last_name).trim();
      var email = lead.email || "";
      var company = lead.company || "";
      
      rowsToAdd.push([name, email, company]);
    }
    
    if (rowsToAdd.length > 0) {
      var startRow = sheet.getLastRow() + 1;
      var range = sheet.getRange(startRow, 1, rowsToAdd.length, 3);
      range.setValues(rowsToAdd);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Successfully pushed " + leads.length + " leads (Name, Email, Company)!",
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

def prepare_leads_payload(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes leads to strictly ensure name, email, company are top-level."""
    formatted = []
    for l in leads:
        full_name = l.get("full_name") or f"{l.get('first_name', '')} {l.get('last_name', '')}".strip()
        formatted.append({
            "name": full_name,
            "full_name": full_name,
            "email": l.get("email", ""),
            "company": l.get("company", ""),
            # Keep original fields for backwards compatibility
            "first_name": l.get("first_name", ""),
            "last_name": l.get("last_name", ""),
            "job_title": l.get("job_title", ""),
            "linkedin_url": l.get("linkedin_url", "")
        })
    return formatted

def push_to_webhook(webhook_url: str, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pushes leads to Google Apps Script Webhook URL.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return {"success": False, "error": "Invalid Webhook URL provided."}
    
    payload_leads = prepare_leads_payload(leads)
    
    try:
        # Google Apps Script web apps return 302 redirects which need to be followed
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.post(webhook_url, json={"leads": payload_leads})
            
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
    Format: Name | Email | Company
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
        
        # Check if empty, append header (Name, Email, Company)
        existing = worksheet.get_all_values()
        if not existing:
            worksheet.append_row(["Name", "Email", "Company"])
            
        rows = [
            [
                l.get("full_name") or f"{l.get('first_name', '')} {l.get('last_name', '')}".strip(),
                l.get("email", ""),
                l.get("company", "")
            ]
            for l in leads
        ]
        worksheet.append_rows(rows)
        return {"success": True, "count": len(leads)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_yamm_csv(leads: List[Dict[str, Any]]) -> str:
    """
    Generates a CSV string formatted strictly with 3 columns:
    Name, Email, Company
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    headers = ["Name", "Email", "Company"]
    writer.writerow(headers)
    
    for lead in leads:
        full_name = lead.get("full_name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        writer.writerow([
            full_name,
            lead.get("email", ""),
            lead.get("company", "")
        ])
        
    return output.getvalue()
