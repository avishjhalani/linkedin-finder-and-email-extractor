import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.search_engine import search_indian_hr_leads
from app.sheets_client import push_to_google_sheet, generate_yamm_csv, GOOGLE_APPS_SCRIPT_TEMPLATE

# Configuration management
CONFIG_FILE = Path(__file__).parent.parent / "config.json"

def load_file_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "webhook_url": "",
        "hunter_api_key": "",
        "default_pattern": "first.last"
    }

def save_file_config(cfg: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_effective_config() -> Dict[str, Any]:
    disk = load_file_config()
    return {
        "webhook_url": os.getenv("GOOGLE_WEBHOOK_URL") or disk.get("webhook_url", ""),
        "hunter_api_key": os.getenv("HUNTER_API_KEY") or disk.get("hunter_api_key", ""),
        "default_pattern": os.getenv("DEFAULT_PATTERN") or disk.get("default_pattern", "first.last")
    }

def mask_secret(secret: str, is_url: bool = False) -> str:
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
    title="LinkedIn Verified HR & Lead Finder",
    description="High-precision Indian HR and Executive contact discovery for cold outreach and YAMM mail merge",
    version="2.0.0"
)

# Request Models
class SearchRequest(BaseModel):
    company: str
    target_roles: Optional[List[str]] = Field(default_factory=lambda: ["Senior Manager", "HR", "Talent Acquisition", "HR Manager", "HR Head"])
    count: int = Field(default=10, ge=1, le=50)
    preferred_pattern: Optional[str] = "first.last"
    custom_domain: Optional[str] = ""

class SheetsExportRequest(BaseModel):
    webhook_url: Optional[str] = ""
    leads: List[Dict[str, Any]]

class CsvExportRequest(BaseModel):
    leads: List[Dict[str, Any]]

class ConfigUpdateRequest(BaseModel):
    webhook_url: Optional[str] = ""
    hunter_api_key: Optional[str] = ""
    default_pattern: Optional[str] = "first.last"

# API Endpoints
@app.post("/api/search")
def api_search(req: SearchRequest):
    if not req.company or not req.company.strip():
        raise HTTPException(status_code=400, detail="Company name is required.")
        
    cfg = get_effective_config()
    hunter_key = cfg.get("hunter_api_key", "").strip() or None
    
    try:
        results = search_indian_hr_leads(
            company=req.company.strip(),
            target_roles=req.target_roles,
            count=req.count,
            preferred_pattern=req.preferred_pattern or cfg.get("default_pattern", "first.last"),
            custom_domain=req.custom_domain or None,
            hunter_api_key=hunter_key
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export/sheets")
def api_export_sheets(req: SheetsExportRequest):
    cfg = get_effective_config()
    provided_url = (req.webhook_url or "").strip()
    
    # Use server's secured secret if masked placeholder or empty was passed
    if not provided_url or "••••" in provided_url:
        effective_url = cfg.get("webhook_url", "").strip()
    else:
        effective_url = provided_url

    if not effective_url:
        raise HTTPException(status_code=400, detail="No Google Apps Script Webhook URL configured on server or in request.")
        
    result = push_to_google_sheet(effective_url, req.leads)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to upload leads to Google Sheet."))
    return result

@app.post("/api/export/csv")
def api_export_csv(req: CsvExportRequest):
    csv_data = generate_yamm_csv(req.leads)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=verified_hr_leads.csv"
        }
    )

@app.get("/api/config")
def api_get_config():
    cfg = get_effective_config()
    return {
        "webhook_configured": bool(cfg.get("webhook_url")),
        "webhook_masked": mask_secret(cfg.get("webhook_url", ""), is_url=True),
        "hunter_configured": bool(cfg.get("hunter_api_key")),
        "hunter_masked": mask_secret(cfg.get("hunter_api_key", "")),
        "default_pattern": cfg.get("default_pattern", "first.last"),
        "is_env_webhook": bool(os.getenv("GOOGLE_WEBHOOK_URL"))
    }

@app.post("/api/config")
def api_update_config(req: ConfigUpdateRequest):
    disk = load_file_config()
    if req.webhook_url and "••••" not in req.webhook_url:
        disk["webhook_url"] = req.webhook_url.strip()
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
    return {"status": "healthy", "service": "linkedin-hr-finder", "version": "2.0.0"}

@app.head("/")
def head_root():
    return Response(status_code=200)

@app.get("/favicon.ico")
def get_favicon():
    return Response(content=b"", media_type="image/x-icon")

# Mount frontend
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "LinkedIn HR Finder API is running"}
