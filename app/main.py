import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
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

# Load environment variables from .env file if present
load_dotenv()

CONFIG_FILE = Path("config.json")

def load_file_config() -> Dict[str, Any]:
    """Loads settings stored on disk in config.json."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "webhook_url": "",
        "apollo_api_key": "",
        "hunter_api_key": "",
        "default_pattern": "first.last",
        "service_account_path": "",
        "spreadsheet_id": ""
    }

def save_file_config(cfg: Dict[str, Any]):
    """Saves non-sensitive settings or user overrides."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_effective_config() -> Dict[str, Any]:
    """
    Returns effective server config prioritizing Environment Variables
    (Render / Cloud secrets) over local config.json.
    """
    disk = load_file_config()
    return {
        "webhook_url": os.getenv("GOOGLE_WEBHOOK_URL") or disk.get("webhook_url", ""),
        "apollo_api_key": os.getenv("APOLLO_API_KEY") or disk.get("apollo_api_key", ""),
        "hunter_api_key": os.getenv("HUNTER_API_KEY") or disk.get("hunter_api_key", ""),
        "default_pattern": os.getenv("DEFAULT_PATTERN") or disk.get("default_pattern", "first.last"),
        "service_account_path": disk.get("service_account_path", ""),
        "spreadsheet_id": disk.get("spreadsheet_id", "")
    }

def mask_secret(secret: str, is_url: bool = False) -> str:
    """Masks secrets so they are NEVER exposed in browser network inspection."""
    if not secret:
        return ""
    if is_url:
        if "/macros/s/" in secret:
            prefix = secret.split("/macros/s/")[0] + "/macros/s/"
            suffix = "/exec" if secret.endswith("/exec") else ""
            return f"{prefix}••••••••••••••••{suffix}"
        return secret[:15] + "••••••••"
    if len(secret) <= 8:
        return "••••••••"
    return "••••••••" + secret[-4:]

app = FastAPI(
    title="LinkedIn Finder & Email Scraper",
    description="Find LinkedIn profiles and discover emails ready for Google Sheets & YAMM.",
    version="1.0.0"
)

# Request Models
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
    apollo_api_key: Optional[str] = ""
    hunter_api_key: Optional[str] = ""
    default_pattern: Optional[str] = "first.last"
    service_account_path: Optional[str] = ""
    spreadsheet_id: Optional[str] = ""

# API Endpoints
@app.post("/api/parse")
def api_parse_query(req: QueryParseRequest):
    parsed = parse_natural_language_query(req.query)
    cfg = get_effective_config()
    apollo_key = cfg.get("apollo_api_key", "").strip() or None
    domain = resolve_company_domain(parsed["company"], apollo_key)
    mx_valid, _, provider = verify_mx_records(domain)
    parsed["detected_domain"] = domain
    parsed["domain_mx_valid"] = mx_valid
    parsed["mail_provider"] = provider
    return parsed

@app.post("/api/search")
def api_search(req: SearchRequest):
    cfg = get_effective_config()
    hunter_key = cfg.get("hunter_api_key", "").strip() or None
    apollo_key = cfg.get("apollo_api_key", "").strip() or None
    
    try:
        results = search_linkedin_leads(
            role=req.role,
            company=req.company,
            count=req.count,
            location=req.location or "",
            preferred_pattern=req.preferred_pattern or cfg.get("default_pattern", "first.last"),
            custom_domain=req.custom_domain or None,
            hunter_api_key=hunter_key,
            apollo_api_key=apollo_key
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/sheets")
def api_export_sheets(req: SheetsExportRequest):
    cfg = get_effective_config()
    
    if req.method == "webhook":
        provided_url = (req.webhook_url or "").strip()
        # If user left the masked placeholder or empty, use server's secure secret
        if not provided_url or "••••" in provided_url:
            effective_url = cfg.get("webhook_url", "").strip()
        else:
            effective_url = provided_url

        if not effective_url:
            raise HTTPException(status_code=400, detail="No Google Apps Script Webhook URL configured on server.")
            
        result = push_to_webhook(effective_url, req.leads)
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
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to push via Service Account."))
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
    """
    Returns sanitized, masked configuration safe for web display.
    Secrets are masked so site visitors can NEVER inspect or steal them.
    """
    cfg = get_effective_config()
    return {
        "webhook_configured": bool(cfg.get("webhook_url")),
        "webhook_masked": mask_secret(cfg.get("webhook_url", ""), is_url=True),
        "apollo_configured": bool(cfg.get("apollo_api_key")),
        "apollo_masked": mask_secret(cfg.get("apollo_api_key", "")),
        "hunter_configured": bool(cfg.get("hunter_api_key")),
        "hunter_masked": mask_secret(cfg.get("hunter_api_key", "")),
        "default_pattern": cfg.get("default_pattern", "first.last"),
        "is_env_webhook": bool(os.getenv("GOOGLE_WEBHOOK_URL")),
        "is_env_apollo": bool(os.getenv("APOLLO_API_KEY"))
    }

@app.post("/api/config")
def api_update_config(req: ConfigUpdateRequest):
    """Saves user settings, ignoring masked placeholders."""
    disk = load_file_config()
    
    # Only update if user provided an actual new unmasked value
    if req.webhook_url and "••••" not in req.webhook_url:
        disk["webhook_url"] = req.webhook_url.strip()
    if req.apollo_api_key and "••••" not in req.apollo_api_key:
        disk["apollo_api_key"] = req.apollo_api_key.strip()
    if req.hunter_api_key and "••••" not in req.hunter_api_key:
        disk["hunter_api_key"] = req.hunter_api_key.strip()
    if req.default_pattern:
        disk["default_pattern"] = req.default_pattern
        
    save_file_config(disk)
    return {"status": "saved", "config": api_get_config()}

@app.get("/api/script-template")
def api_get_script_template():
    return {"template": GOOGLE_APPS_SCRIPT_TEMPLATE}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "linkedin-finder"}

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "LinkedIn Finder API is running."}
