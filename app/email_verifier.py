import re
import urllib.parse
from typing import Dict, List, Tuple, Optional, Any
import dns.resolver
import httpx
from ddgs import DDGS

# Comprehensive dictionary of well-known employers for instant domain resolution
KNOWN_DOMAINS: Dict[str, str] = {
    # Tech Giants & US Enterprises
    "amazon": "amazon.com",
    "optum": "optum.com",
    "unitedhealth": "uhg.com",
    "unitedhealth group": "uhg.com",
    "google": "google.com",
    "microsoft": "microsoft.com",
    "meta": "meta.com",
    "apple": "apple.com",
    "netflix": "netflix.com",
    "uber": "uber.com",
    "airbnb": "airbnb.com",
    "cisco": "cisco.com",
    "oracle": "oracle.com",
    "salesforce": "salesforce.com",
    "adobe": "adobe.com",
    "ibm": "ibm.com",
    "intel": "intel.com",
    "nvidia": "nvidia.com",
    "qualcomm": "qualcomm.com",
    "paypal": "paypal.com",
    "stripe": "stripe.com",
    "atlassian": "atlassian.com",
    "freshworks": "freshworks.com",
    "zoho": "zoho.com",
    "postman": "postman.com",
    "browserstack": "browserstack.com",
    "chargebee": "chargebee.com",
    "darwinbox": "darwinbox.com",
    
    # Top IT Services & Consultancies in India
    "tcs": "tcs.com",
    "tata consultancy services": "tcs.com",
    "infosys": "infosys.com",
    "wipro": "wipro.com",
    "cognizant": "cognizant.com",
    "accenture": "accenture.com",
    "hcl": "hcltech.com",
    "hcltech": "hcltech.com",
    "hcl technologies": "hcltech.com",
    "tech mahindra": "techmahindra.com",
    "capgemini": "capgemini.com",
    "l&t": "larsentoubro.com",
    "larsen & toubro": "larsentoubro.com",
    "ltimindtree": "ltimindtree.com",
    "mindtree": "ltimindtree.com",
    "mphasis": "mphasis.com",
    "hexaware": "hexaware.com",
    "persistent": "persistent.com",
    "genpact": "genpact.com",
    
    # Big 4 & Financial Giants
    "deloitte": "deloitte.com",
    "pwc": "pwc.com",
    "ey": "ey.com",
    "ernst & young": "ey.com",
    "kpmg": "kpmg.com",
    "mckinsey": "mckinsey.com",
    "bcg": "bcg.com",
    "bain": "bain.com",
    "goldman sachs": "gs.com",
    "jpmorgan": "jpmchase.com",
    "jp morgan": "jpmchase.com",
    "morgan stanley": "morganstanley.com",
    "citigroup": "citi.com",
    "citi": "citi.com",
    "barclays": "barclays.com",
    "hsbc": "hsbc.com",
    "standard chartered": "sc.com",
    
    # Indian Tech Unicorns & Product Leaders
    "flipkart": "flipkart.com",
    "swiggy": "swiggy.in",
    "zomato": "zomato.com",
    "paytm": "paytm.com",
    "phonepe": "phonepe.com",
    "ola": "olacabs.com",
    "razorpay": "razorpay.com",
    "cred": "cred.club",
    "meesho": "meesho.com",
    "nykaa": "nykaa.com",
    "zepto": "zeptonow.com",
    "blinkit": "blinkit.com",
    "myntra": "myntra.com",
    "lenskart": "lenskart.com",
    "dream11": "dream11.com",
    "zerodha": "zerodha.com",
    "groww": "groww.in",
    "makemytrip": "makemytrip.com",
    "urban company": "urbancompany.com",
    "inmobi": "inmobi.com",
    "jio": "jio.com",
    "reliance jio": "jio.com",
    "reliance": "ril.com",
    "tata": "tata.com",
    "airtel": "airtel.in",
    "bharti airtel": "airtel.in"
}

def resolve_company_domain(company_name: str, apollo_api_key: Optional[str] = None) -> str:
    """Resolves primary corporate domain for a company name."""
    clean = company_name.strip().lower()
    if clean in KNOWN_DOMAINS:
        return KNOWN_DOMAINS[clean]
    
    # Check Apollo Organization Enrichment if API key provided
    if apollo_api_key:
        try:
            url = f"https://api.apollo.io/v1/organizations/enrich?domain={urllib.parse.quote(clean)}"
            headers = {"Content-Type": "application/json", "X-Api-Key": apollo_api_key.strip()}
            with httpx.Client(timeout=4.0) as client:
                r = client.get(url, headers=headers)
                if r.status_code == 200:
                    dom = r.json().get("organization", {}).get("primary_domain")
                    if dom:
                        return dom
        except Exception:
            pass

    # Check if user already typed a domain
    if "." in clean and not any(w in clean for w in ["inc", "ltd", "corp", "llc", "pvt"]):
        return clean.replace("https://", "").replace("http://", "").split("/")[0]

    # Quick web search lookup
    try:
        ddgs = DDGS(timeout=4)
        results = list(ddgs.text(f'"{company_name}" official site company', max_results=3))
        ignored = [
            "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
            "x.com", "youtube.com", "glassdoor.com", "indeed.com", "instagram.com"
        ]
        for r in results:
            href = r.get("href", "")
            netloc = urllib.parse.urlparse(href).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if netloc and not any(ign in netloc for ign in ignored):
                return netloc
    except Exception:
        pass

    sanitized = re.sub(r"[^a-zA-Z0-9]", "", clean)
    return f"{sanitized}.com" if sanitized else "company.com"

def verify_mx_records(domain: str) -> Tuple[bool, List[str], str]:
    """
    Checks if domain has valid DNS MX records and identifies mail provider.
    Returns: (is_valid, mx_hosts, mail_provider)
    """
    try:
        answers = dns.resolver.resolve(domain, "MX")
        sorted_records = sorted(answers, key=lambda r: r.preference)
        hosts = [str(r.exchange).rstrip(".") for r in sorted_records]
        
        provider = "Enterprise Mail Server"
        hosts_str = " ".join(hosts).lower()
        if "google" in hosts_str or "aspmx" in hosts_str:
            provider = "Google Workspace (Gmail)"
        elif "outlook" in hosts_str or "protection.outlook.com" in hosts_str:
            provider = "Microsoft 365"
        elif "pphosted" in hosts_str or "proofpoint" in hosts_str:
            provider = "Proofpoint Enterprise"
        elif "mimecast" in hosts_str:
            provider = "Mimecast Cloud"
        elif "barracuda" in hosts_str:
            provider = "Barracuda Networks"
            
        return True, hosts, provider
    except Exception:
        return False, [], "No Active Mail Server"

def parse_person_name(raw_name: str) -> Dict[str, str]:
    """
    Extracts clean first name and last name, stripping emojis, pronouns,
    and professional credentials like MBA, PMP, SHRM, etc.
    """
    # 1. Remove parenthetical or bracketed notes (e.g. "(She/Her)", "[PMP]")
    name_clean = re.sub(r"\s*[\(\[\{].*?[\)\]\}]", "", raw_name)
    
    # 2. Remove emojis and symbols
    name_clean = re.sub(r"[^\w\s\.-]", "", name_clean)
    
    # 3. Strip titles like "Dr.", "Mr.", "Ms.", "Mrs."
    name_clean = re.sub(r"^(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+", "", name_clean, flags=re.IGNORECASE)
    
    # 4. Remove common certifications and trailing noise
    creds = [
        "mba", "phr", "sphr", "shrm", "shrm-cp", "shrm-scp", "pmp", "ca",
        "cfa", "iim", "iit", "xlri", "hr", "talent", "recruiter", "lead"
    ]
    parts = [p.strip() for p in name_clean.split() if p.strip()]
    cleaned_parts = []
    for p in parts:
        lower_p = p.lower().strip(".,-")
        if lower_p in creds:
            continue
        cleaned_parts.append(p.capitalize())
        
    if not cleaned_parts:
        return {"full_name": raw_name.strip(), "first_name": "Team", "last_name": ""}
        
    first_name = cleaned_parts[0]
    last_name = " ".join(cleaned_parts[1:]) if len(cleaned_parts) > 1 else ""
    full_name = f"{first_name} {last_name}".strip()
    
    return {
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name
    }

def generate_email_permutations(first_name: str, last_name: str, domain: str) -> Dict[str, str]:
    """Generates standard corporate email permutations."""
    f = re.sub(r"[^a-zA-Z]", "", first_name.lower())
    l = re.sub(r"[^a-zA-Z]", "", last_name.lower())
    dom = domain.lower()
    
    if not f and not l:
        return {"default": f"contact@{dom}"}
    if not l:
        return {
            "first": f"{f}@{dom}",
            "first.last": f"{f}@{dom}"
        }
    if not f:
        return {"last": f"{l}@{dom}"}
        
    f_init = f[0]
    l_init = l[0]
    
    return {
        "first.last": f"{f}.{l}@{dom}",      # e.g. amit.vaish@optum.com
        "flast": f"{f_init}{l}@{dom}",        # e.g. avaish@optum.com
        "firstlast": f"{f}{l}@{dom}",        # e.g. amitvaish@optum.com
        "first_last": f"{f}_{l}@{dom}",      # e.g. amit_vaish@optum.com
        "first.l": f"{f}.{l_init}@{dom}",    # e.g. amit.v@optum.com
        "first": f"{f}@{dom}",               # e.g. amit@optum.com
        "last.first": f"{l}.{f}@{dom}"       # e.g. vaish.amit@optum.com
    }

def extract_email_from_text(text: str, domain: Optional[str] = None) -> Optional[str]:
    """Extracts email addresses published directly in text or snippet."""
    if not text:
        return None
    matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    if not matches:
        return None
    # Prefer emails matching domain or common recruiter addresses
    if domain:
        dom_clean = domain.lower()
        for m in matches:
            if dom_clean in m.lower():
                return m
    return matches[0]

def verify_email_deliverability(email: str, hunter_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies deliverability of an email using Hunter.io Email Verifier API if API key provided.
    Docs: https://hunter.io/api-documentation/v2#email-verifier
    """
    if not hunter_api_key:
        return {
            "verified": False,
            "status": "unverified",
            "score": 0,
            "deliverable": None
        }
        
    try:
        url = "https://api.hunter.io/v2/email-verifier"
        params = {"email": email, "api_key": hunter_api_key.strip()}
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status = data.get("status")  # "valid", "invalid", "accept_all"
                result = data.get("result")  # "deliverable", "risky", "undeliverable"
                score = data.get("score", 0)
                is_deliverable = result == "deliverable" or status == "valid"
                return {
                    "verified": True,
                    "status": status,
                    "score": score,
                    "deliverable": is_deliverable,
                    "smtp_check": data.get("smtp_check", False)
                }
    except Exception:
        pass
        
    return {
        "verified": False,
        "status": "unverified",
        "score": 0,
        "deliverable": None
    }

def query_apollo_people_match(
    first_name: str,
    last_name: str,
    domain: Optional[str] = None,
    organization_name: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Enriches candidate and extracts verified direct email using Apollo.io People Match API.
    Docs: https://apolloio.github.io/apollo-api-docs/#people-match
    """
    if not api_key:
        return None
        
    try:
        url = "https://api.apollo.io/v1/people/match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": api_key.strip()
        }
        payload: Dict[str, Any] = {}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if domain:
            payload["domain"] = domain
        if organization_name:
            payload["organization_name"] = organization_name
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        with httpx.Client(timeout=6.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                person = resp.json().get("person") or {}
                email = person.get("email")
                status = person.get("email_status") or "verified"
                # Exclude masked or locked emails
                if email and "email_not_unlocked" not in email:
                    return {
                        "email": email,
                        "deliverability": f"Apollo Verified ({status})",
                        "status": status,
                        "title": person.get("title")
                    }
    except Exception:
        pass
        
    return None

