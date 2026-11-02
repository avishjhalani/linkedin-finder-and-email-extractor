import csv
import io
from typing import List, Dict, Any
import httpx

GOOGLE_APPS_SCRIPT_TEMPLATE = """// Google Apps Script for LinkedIn Lead Importer (3 Columns: Name, Email, Company)
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);
    var leads = data.leads || [];
    
    // Auto-create headers if sheet is empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Name", "Email", "Company"]);
      sheet.getRange(1, 1, 1, 3).setFontWeight("bold").setBackground("#1e293b").setFontColor("#ffffff");
    }
    
    var rows = [];
    for (var i = 0; i < leads.length; i++) {
      var lead = leads[i];
      // Format strictly: Name, Email, Company
      var name = lead.name || ((lead.first_name || "") + " " + (lead.last_name || "")).trim();
      var email = lead.email || "";
      var company = lead.company || "";
      rows.push([name, email, company]);
    }
    
    if (rows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, 3).setValues(rows);
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      "status": "success",
      "count": rows.length
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      "status": "error",
      "error": err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
"""

def push_to_google_sheet(webhook_url: str, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pushes leads to Google Sheets via Google Apps Script Webhook.
    Strictly sends 3 columns: Name, Email, Company.
    """
    clean_url = webhook_url.strip()
    if not clean_url:
        return {"success": False, "error": "No Google Sheets Webhook URL configured."}
        
    formatted_leads = []
    for lead in leads:
        name = lead.get("name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        email = lead.get("email", "").strip()
        company = lead.get("company", "").strip()
        if email:
            formatted_leads.append({
                "name": name,
                "email": email,
                "company": company
            })
            
    if not formatted_leads:
        return {"success": False, "error": "No valid leads selected to push."}
        
    try:
        payload = {"leads": formatted_leads}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.post(clean_url, json=payload)
            if resp.status_code == 200:
                try:
                    res_json = resp.json()
                    return {
                        "success": True,
                        "count": len(formatted_leads),
                        "response": res_json
                    }
                except Exception:
                    return {"success": True, "count": len(formatted_leads)}
            else:
                return {
                    "success": False,
                    "error": f"Google Sheets Webhook returned HTTP {resp.status_code}: {resp.text[:100]}"
                }
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_yamm_csv(leads: List[Dict[str, Any]]) -> str:
    """
    Generates CSV formatted strictly with 3 columns: Name, Email, Company.
    Ready for 1-click import into Google Sheets / YAMM / Mailmeteor.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Name", "Email", "Company"])
    
    for lead in leads:
        name = lead.get("name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        email = lead.get("email", "").strip()
        company = lead.get("company", "").strip()
        if email:
            writer.writerow([name, email, company])
            
    return output.getvalue()
