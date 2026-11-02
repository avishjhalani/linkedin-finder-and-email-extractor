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
    verify_email_deliverability,
    query_apollo_people_match
)

# Standard roles targeted for Indian enterprise talent scouting
DEFAULT_TARGET_ROLES = [
    "Senior Manager",
    "HR",
    "Talent Acquisition",
    "HR Manager",
    "HR Head"
]

INDIAN_CITIES = [
    "india", "bengaluru", "bangalore", "hyderabad", "gurgaon", "gurugram",
    "noida", "mumbai", "pune", "chennai", "delhi", "new delhi", "kolkata", "ahmedabad"
]

FOREIGN_DOMAINS = [
    "uk.linkedin.com", "us.linkedin.com", "au.linkedin.com", "ca.linkedin.com",
    "ph.linkedin.com", "ie.linkedin.com", "sg.linkedin.com", "nz.linkedin.com",
    "ae.linkedin.com", "de.linkedin.com", "fr.linkedin.com"
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

def clean_job_title(raw_headline: str, snippet: str, company: str) -> str:
    """Produces a clean, professional job headline without clutter."""
    hl = raw_headline.replace("\ufffd", " - ").replace("–", "-")
    hl = re.split(r"\s*\|\s*LinkedIn", hl, flags=re.IGNORECASE)[0].strip()
    
    # Strip concatenated second profiles
    if "..." in hl:
        hl = hl.split("...")[0].strip()
    
    # Clean leading noise like "with 10 years of experience presently working as"
    hl = re.sub(
        r"^(?:with\s+)?(?:\d+\+?\s+)?years\s+(?:of\s+)?experience\s+(?:presently\s+|currently\s+)?(?:working\s+as\s+)?",
        "",
        hl,
        flags=re.IGNORECASE
    ).strip()
    
    # Generic location or directory noise checks (e.g. "Bengaluru, Karnataka, India | Professional Profile")
    is_generic_noise = bool(re.search(r"\b(?:professional\s+profile|professional\s+community|followers|connections|bengaluru|mumbai|delhi|karnataka|gurgaon|noida|hyderabad|pune|india)\b", hl, re.IGNORECASE))
    
    # If headline is too short, is just the company name, or is location noise
    if len(hl) < 3 or hl.lower() in [company.lower(), "india", "linkedin"] or is_generic_noise:
        # Extract specific role from snippet if available
        exp_m = re.search(
            r"((?:Senior\s+Manager|HR\s+Manager|HR\s+Head|Head\s+HR|Director|Lead|Specialist|Partner|Talent\s+Acquisition|Recruiter|Recruiting)[^·\n.,|]{0,50})",
            snippet,
            re.IGNORECASE
        )
        if exp_m:
            hl = exp_m.group(1).strip()
        else:
            hl = f"HR & Talent Leader @ {company}"

    # Capitalize properly if all lowercase
    if hl.islower():
        hl = hl.title()

    return hl.rstrip(" -–|·,")

def verify_current_employee(company: str, title: str, snippet: str, url: str) -> tuple[bool, str, str]:
    """
    Strictly verifies if a candidate is a CURRENT employee of target company in India.
    Returns (is_valid, clean_headline, rejection_reason).
    """
    comp_clean = company.strip().lower()
    
    title_first_segment = re.split(r"\s*\|\s*LinkedIn", title, flags=re.IGNORECASE)[0].strip()
    title_lower = title_first_segment.lower()
    snippet_lower = snippet.lower()
    url_lower = url.lower()
    
    # 1. Location verification (India)
    if any(fd in url_lower for fd in FOREIGN_DOMAINS) and not any(c in snippet_lower for c in INDIAN_CITIES):
        return False, "", "Foreign LinkedIn domain outside India"
    if "location: united states" in snippet_lower or "location: united kingdom" in snippet_lower or "location: canada" in snippet_lower:
        return False, "", "Location is outside India"
    if "in.linkedin.com" not in url_lower and not any(c in (title_lower + " " + snippet_lower) for c in INDIAN_CITIES):
        return False, "", "Profile location is not in India"

    # 2. Ex-employee checks
    # Matches: "ex-stripe", "ex - stripe", "ex-navi, stripe", "formerly at stripe", "past: stripe"
    ex_patterns = [
        rf"\bex[- /]+(?:[a-zA-Z0-9&]+[,\s/]+){{0,2}}{re.escape(comp_clean)}\b",
        rf"\bformerly\s+(?:at\s+)?{re.escape(comp_clean)}\b",
        rf"\bformer\s+{re.escape(comp_clean)}\b",
        rf"\bpast\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b",
        rf"\bprevious\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b"
    ]
    for pat in ex_patterns:
        if re.search(pat, title_lower) or re.search(pat, snippet_lower):
            # Only allow if current experience clearly overrides
            if not re.search(rf"\b(?:experience|current)\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b", snippet_lower):
                return False, "", f"Ex-employee of {company}"

    # 3. Extract Name & Headline
    title_parts = title_first_segment.split(" - ")
    name = title_parts[0].strip()
    raw_headline = " - ".join(title_parts[1:]).strip() if len(title_parts) > 1 else ""
    
    # 4. Check if headline is just another company name (e.g. "Aju John - Intuit")
    if raw_headline and len(title_parts) == 2:
        if comp_clean not in raw_headline.lower() and re.match(r"^[A-Z][A-Za-z0-9\s.,&]{1,35}$", raw_headline):
            if not re.search(rf"\b(?:experience|current)\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b", snippet_lower):
                return False, "", f"Current employer is {raw_headline}, not {company}"

    # 5. Check if headline explicitly says "at [OtherCompany]"
    other_at_match = re.search(r"\b(?:at|@)\s+([A-Z][A-Za-z0-9\s.,&]{2,30})\b", raw_headline)
    if other_at_match:
        other_comp = other_at_match.group(1).strip().lower()
        if comp_clean not in other_comp and other_comp not in comp_clean:
            if not re.search(rf"\b(?:experience|current)\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b", snippet_lower):
                return False, "", f"Headline states working at {other_at_match.group(1)}"

    # 6. Positive verification: Target company must be in headline or current experience
    has_in_headline = bool(re.search(rf"\b{re.escape(comp_clean)}\b", raw_headline.lower()))
    has_in_current_exp = bool(re.search(rf"\b(?:experience|current)\s*:\s*[^·\n]*\b{re.escape(comp_clean)}\b", snippet_lower))
    has_at_company = bool(re.search(rf"(?:at|@)\s*{re.escape(comp_clean)}\b", (raw_headline + " " + snippet).lower()))

    if not (has_in_headline or has_in_current_exp or has_at_company):
        return False, "", f"{company} not confirmed as current employer"

    clean_hl = clean_job_title(raw_headline, snippet, company)
    return True, clean_hl, "Verified Current Employee"

def search_indian_hr_leads(
    company: str,
    target_roles: Optional[List[str]] = None,
    count: int = 10,
    preferred_pattern: str = "first.last",
    custom_domain: Optional[str] = None,
    hunter_api_key: Optional[str] = None,
    apollo_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finds verified LinkedIn profiles for CURRENT Senior Managers, HR, Talent Acquisition,
    HR Managers, and HR Heads at a specific company in India.
    """
    clean_company = company.strip()
    roles = target_roles if target_roles and len(target_roles) > 0 else DEFAULT_TARGET_ROLES
    
    # 1. Resolve domain and check corporate mail server MX
    domain = custom_domain.strip().lower() if custom_domain else resolve_company_domain(clean_company, apollo_api_key)
    mx_valid, mx_hosts, mail_provider = verify_mx_records(domain)
    
    # 2. Build targeted India search queries
    roles_or = " OR ".join([f'"{r}"' for r in roles])
    
    queries = [
        f'site:linkedin.com/in "{clean_company}" "India" ({roles_or})',
        f'site:linkedin.com/in "at {clean_company}" "India" ({roles_or})',
        f'site:linkedin.com/in "@{clean_company}" "India" ({roles_or})',
        f'site:linkedin.com/in "{clean_company}" India "Talent Acquisition"',
        f'site:linkedin.com/in "{clean_company}" India "HR Manager" OR "HR Head" OR "Recruiter"'
    ]

    seen_urls = set()
    seen_names = set()
    leads = []
    
    for q in queries:
        if len(leads) >= count:
            break
            
        try:
            ddgs = DDGS(timeout=5)
            # Fetch with margin for deduplication and strict filtering
            fetch_limit = min(max(count * 2, 12), 35)
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
                
                # 3. Strict current employment & location verification
                is_valid, headline, reason = verify_current_employee(clean_company, title, snippet, clean_url)
                if not is_valid:
                    continue

                # 4. Extract candidate name
                title_first_segment = re.split(r"\s*\|\s*LinkedIn", title, flags=re.IGNORECASE)[0].strip()
                title_parts = title_first_segment.split(" - ")
                raw_name = title_parts[0].strip()
                    
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
                
                # 5. Email Generation & Verification
                permutations = generate_email_permutations(first_name, last_name, domain)
                
                # Check Apollo.io People Match API if key configured
                apollo_match = query_apollo_people_match(
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                    organization_name=clean_company,
                    linkedin_url=clean_url,
                    api_key=apollo_api_key
                ) if apollo_api_key else None
                
                # Check Public bio / snippet email
                bio_email = extract_email_from_text(snippet, domain)
                
                if apollo_match:
                    final_email = apollo_match["email"]
                    deliverability = apollo_match["deliverability"]
                    is_deliverable = True
                elif bio_email:
                    final_email = bio_email
                    deliverability = "Verified (Public Recruiter Bio)"
                    is_deliverable = True
                else:
                    # Select corporate pattern
                    final_email = permutations.get(preferred_pattern, permutations.get("first.last", f"{first_name.lower()}@{domain}"))
                    
                    # Check Hunter.io deliverability verifier if API key configured
                    if hunter_api_key:
                        hunter_check = verify_email_deliverability(final_email, hunter_api_key)
                        if hunter_check.get("verified"):
                            if hunter_check.get("deliverable"):
                                deliverability = f"Hunter Verified ({hunter_check.get('score')}%)"
                                is_deliverable = True
                            else:
                                deliverability = f"Undeliverable ({hunter_check.get('status')})"
                                is_deliverable = False
                        else:
                            deliverability = f"Active MX Pattern ({preferred_pattern})"
                            is_deliverable = None
                    else:
                        if mx_valid:
                            deliverability = f"Active MX Pattern ({preferred_pattern})"
                            is_deliverable = None
                        else:
                            deliverability = "Inactive Domain"
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
        except Exception:
            continue
            
    return {
        "company": clean_company,
        "domain": domain,
        "mx_valid": mx_valid,
        "mail_provider": mail_provider,
        "total_found": len(leads),
        "leads": leads
    }
