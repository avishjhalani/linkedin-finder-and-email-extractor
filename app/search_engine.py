import re
import urllib.parse
from typing import List, Dict, Any, Optional
from ddgs import DDGS

from app.email_verifier import (
    resolve_company_domain,
    verify_mx_records,
    parse_person_name,
    generate_email_permutations,
    extract_email_from_text,
    verify_email_deliverability
)

# Standard roles targeted for Indian enterprise talent scouting
DEFAULT_TARGET_ROLES = [
    "Senior Manager",
    "HR",
    "Talent Acquisition",
    "HR Manager",
    "HR Head"
]

def clean_linkedin_url(raw_url: str) -> str:
    """Standardizes LinkedIn profile URL to clean canonical format."""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if "in" in path_parts:
            idx = path_parts.index("in")
            if idx + 1 < len(path_parts):
                slug = path_parts[idx + 1]
                netloc = parsed.netloc
                if not netloc.endswith("linkedin.com"):
                    netloc = "in.linkedin.com"
                return f"https://{netloc}/in/{slug}"
    except Exception:
        pass
    return raw_url.split("?")[0].split("#")[0]

def clean_job_title(title_raw: str, snippet: str, company: str) -> str:
    """Extracts a neat job headline from search result."""
    # Strip " | LinkedIn" and unicode replacement characters
    title = title_raw.replace("\ufffd", " - ").replace("–", "-")
    title = re.split(r"\s*\|\s*LinkedIn", title, flags=re.IGNORECASE)[0].strip()
    
    parts = title.split(" - ")
    headline = parts[1].strip() if len(parts) >= 2 else title
    
    # Remove trailing ellipses and trailing dividers
    headline = headline.split("...")[0].strip()
    headline = headline.split(" | ")[0].strip()
    
    # If headline is too short, extract from snippet preview
    if len(headline) < 3:
        headline = snippet[:60].strip() + "..."
        
    return headline

def search_indian_hr_leads(
    company: str,
    target_roles: Optional[List[str]] = None,
    count: int = 10,
    preferred_pattern: str = "first.last",
    custom_domain: Optional[str] = None,
    hunter_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finds verified LinkedIn profiles for Senior Managers, HR, Talent Acquisition,
    HR Managers, and HR Heads at a specific company in India.
    """
    clean_company = company.strip()
    roles = target_roles if target_roles and len(target_roles) > 0 else DEFAULT_TARGET_ROLES
    
    # 1. Resolve domain and check corporate mail server MX
    domain = custom_domain.strip().lower() if custom_domain else resolve_company_domain(clean_company)
    mx_valid, mx_hosts, mail_provider = verify_mx_records(domain)
    
    # 2. Build targeted India search queries
    # Construct roles OR clause
    roles_or = " OR ".join([f'"{r}"' for r in roles])
    
    queries = [
        f'site:in.linkedin.com/in/ "{clean_company}" ({roles_or})',
        f'site:in.linkedin.com/in/ {clean_company} "Talent Acquisition"',
        f'site:in.linkedin.com/in/ {clean_company} "HR Manager" OR "HR Head"',
        f'site:in.linkedin.com/in/ {clean_company} "Senior Manager"'
    ]

    foreign_domains = [
        "uk.linkedin.com", "us.linkedin.com", "au.linkedin.com", "ca.linkedin.com",
        "ph.linkedin.com", "ie.linkedin.com", "sg.linkedin.com", "nz.linkedin.com",
        "ae.linkedin.com", "de.linkedin.com", "fr.linkedin.com"
    ]
    indian_indicators = [
        "india", "bengaluru", "bangalore", "hyderabad", "gurgaon", "gurugram",
        "noida", "mumbai", "pune", "chennai", "delhi", "new delhi", "kolkata", "ahmedabad"
    ]

    seen_urls = set()
    seen_names = set()
    leads = []
    
    for q in queries:
        if len(leads) >= count:
            break
            
        try:
            ddgs = DDGS(timeout=4)
            # Fetch with margin for deduplication
            fetch_limit = min(max(count * 2, 10), 30)
            raw_results = list(ddgs.text(q, max_results=fetch_limit))
            
            for item in raw_results:
                if len(leads) >= count:
                    break
                    
                raw_url = item.get("href", "")
                if "/in/" not in raw_url:
                    continue
                    
                clean_url = clean_linkedin_url(raw_url)
                if clean_url in seen_urls:
                    continue
                    
                title = item.get("title", "")
                snippet = item.get("body", "")
                combined_lower = (title + " " + snippet + " " + clean_url).lower()
                
                # Verify Indian location relevance
                if any(fd in clean_url.lower() for fd in foreign_domains):
                    continue
                if "location: united states" in combined_lower or "location: united kingdom" in combined_lower or "location: canada" in combined_lower:
                    continue
                if "in.linkedin.com" not in clean_url.lower() and not any(city in combined_lower for city in indian_indicators):
                    continue
                    
                # Extract candidate name
                title_clean = title.split(" | LinkedIn")[0].strip()
                title_parts = title_clean.split(" - ")
                if len(title_parts) >= 2:
                    raw_name = title_parts[0].strip()
                    raw_headline = title_parts[1].strip()
                else:
                    raw_name = title_clean
                    raw_headline = "HR / Talent Acquisition"
                    
                name_info = parse_person_name(raw_name)
                full_name = name_info["full_name"]
                first_name = name_info["first_name"]
                last_name = name_info["last_name"]
                
                # Skip invalid names or search engine directory noise
                if not first_name or len(first_name) < 2:
                    continue
                if first_name.lower() in ["linkedin", "top", "profiles", "jobs", "directory", "the", "find"]:
                    continue
                if full_name.lower() in seen_names:
                    continue
                    
                seen_urls.add(clean_url)
                seen_names.add(full_name.lower())
                
                headline = clean_job_title(raw_headline, snippet, clean_company)
                
                # Email Generation & Verification
                permutations = generate_email_permutations(first_name, last_name, domain)
                
                # Check 1: Public bio / post snippet email
                bio_email = extract_email_from_text(snippet, domain)
                
                if bio_email:
                    final_email = bio_email
                    deliverability = "🟢 Verified (Public Recruiter Bio)"
                    is_deliverable = True
                else:
                    # Select corporate pattern
                    final_email = permutations.get(preferred_pattern, permutations.get("first.last", f"{first_name.lower()}@{domain}"))
                    
                    # Check 2: Hunter.io deliverability verifier if API key configured
                    if hunter_api_key:
                        hunter_check = verify_email_deliverability(final_email, hunter_api_key)
                        if hunter_check.get("verified"):
                            if hunter_check.get("deliverable"):
                                deliverability = f"🟢 Hunter Verified ({hunter_check.get('score')}%)"
                                is_deliverable = True
                            else:
                                deliverability = f"🔴 Undeliverable ({hunter_check.get('status')})"
                                is_deliverable = False
                        else:
                            deliverability = f"🟡 Active MX Pattern ({preferred_pattern})"
                            is_deliverable = None
                    else:
                        if mx_valid:
                            deliverability = f"🟡 Active MX Pattern ({preferred_pattern})"
                            is_deliverable = None
                        else:
                            deliverability = f"🔴 Inactive Domain"
                            is_deliverable = False
                            
                leads.append({
                    "id": len(leads) + 1,
                    "name": full_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": headline,
                    "company": clean_company,
                    "domain": domain,
                    "email": final_email,
                    "deliverability": deliverability,
                    "is_deliverable": is_deliverable,
                    "linkedin_url": clean_url,
                    "permutations": permutations
                })
        except Exception as e:
            continue
            
    return {
        "company": clean_company,
        "domain": domain,
        "mx_valid": mx_valid,
        "mail_provider": mail_provider,
        "total_found": len(leads),
        "leads": leads
    }
