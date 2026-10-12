import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.query_parser import parse_natural_language_query
from app.linkedin_finder import search_linkedin_leads
from app.email_extractor import resolve_company_domain, verify_mx_records
from app.sheets_sync import (
    push_to_webhook,
    push_to_service_account,
    generate_yamm_csv,
    GOOGLE_APPS_SCRIPT_TEMPLATE
)

CONFIG_FILE = Path("config.json")

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "webhook_url": "",
        "hunter_api_key": "",
        "default_pattern": "first.last",
        "service_account_path": "",
        "spreadsheet_id": ""
    }

def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

app = FastAPI(
    title="LinkedIn Finder & Email Scraper",
    description="Find LinkedIn profiles and discover emails ready for Google Sheets & YAMM.",
    version="1.0.0"
)

# Models
class QueryParseRequest(BaseModel):
    query: str

class SearchRequest(BaseModel):
    role: str
    company: str
    count: int = Field(default=10, ge=1, le=50)
    location: Optional[str] = ""
    preferred_pattern: Optional[str] = "first.last"
    custom_domain: Optional[str] = ""

class SheetsExportRequest(BaseModel):
    method: str = "webhook"  # "webhook" or "service_account"
    webhook_url: Optional[str] = ""
    credentials_json_path: Optional[str] = ""
    sheet_id_or_url: Optional[str] = ""
    leads: List[Dict[str, Any]]

class CsvExportRequest(BaseModel):
    leads: List[Dict[str, Any]]

class ConfigUpdateRequest(BaseModel):
    webhook_url: Optional[str] = ""
    hunter_api_key: Optional[str] = ""
    default_pattern: Optional[str] = "first.last"
    service_account_path: Optional[str] = ""
    spreadsheet_id: Optional[str] = ""

# API Endpoints
@app.post("/api/parse")
def api_parse_query(req: QueryParseRequest):
    parsed = parse_natural_language_query(req.query)
    # Also resolve domain preview for this company
    domain = resolve_company_domain(parsed["company"])
    mx_valid, _, provider = verify_mx_records(domain)
    parsed["detected_domain"] = domain
    parsed["domain_mx_valid"] = mx_valid
    parsed["mail_provider"] = provider
    return parsed

@app.post("/api/search")
def api_search(req: SearchRequest):
    cfg = load_config()
    hunter_key = cfg.get("hunter_api_key", "").strip() or None
    
    try:
        results = search_linkedin_leads(
            role=req.role,
            company=req.company,
            count=req.count,
            location=req.location or "",
            preferred_pattern=req.preferred_pattern or cfg.get("default_pattern", "first.last"),
            custom_domain=req.custom_domain or None,
            hunter_api_key=hunter_key
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/sheets")
def api_export_sheets(req: SheetsExportRequest):
    cfg = load_config()
    
    if req.method == "webhook":
        url = (req.webhook_url or cfg.get("webhook_url", "")).strip()
        if not url:
            raise HTTPException(status_code=400, detail="No Google Apps Script Webhook URL provided.")
        result = push_to_webhook(url, req.leads)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to push to Google Sheet Webhook."))
        return result
        
    elif req.method == "service_account":
        creds = (req.credentials_json_path or cfg.get("service_account_path", "")).strip()
        sheet = (req.sheet_id_or_url or cfg.get("spreadsheet_id", "")).strip()
        if not creds or not sheet:
            raise HTTPException(status_code=400, detail="Service account path and Spreadsheet ID are required.")
        result = push_to_service_account(creds, sheet, req.leads)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to push to Google Sheet via Service Account."))
        return result
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export method '{req.method}'.")

@app.post("/api/export/csv")
def api_export_csv(req: CsvExportRequest):
    csv_data = generate_yamm_csv(req.leads)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=linkedin_leads_yamm.csv"
        }
    )

@app.get("/api/config")
def api_get_config():
    return load_config()

@app.post("/api/config")
def api_update_config(req: ConfigUpdateRequest):
    cfg = load_config()
    data = req.dict(exclude_unset=True)
    cfg.update(data)
    save_config(cfg)
    return {"status": "saved", "config": cfg}

@app.get("/api/script-template")
def api_get_script_template():
    return {"template": GOOGLE_APPS_SCRIPT_TEMPLATE}

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "LinkedIn Finder API is running. Index file not created yet."}
