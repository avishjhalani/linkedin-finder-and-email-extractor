import os
import re
import urllib.parse
from typing import Dict, List, Tuple, Optional, Any
import dns.resolver
import httpx
from ddgs import DDGS

# Well-known enterprise domains dictionary for instant zero-latency lookup
KNOWN_COMPANY_DOMAINS = {
    "optum": "optum.com",
    "unitedhealth": "uhg.com",
    "unitedhealth group": "uhg.com",
    "google": "google.com",
    "alphabet": "abc.xyz",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "apple": "apple.com",
    "meta": "meta.com",
    "facebook": "meta.com",
    "netflix": "netflix.com",
    "tesla": "tesla.com",
    "nvidia": "nvidia.com",
    "intel": "intel.com",
    "ibm": "ibm.com",
    "cisco": "cisco.com",
    "oracle": "oracle.com",
    "salesforce": "salesforce.com",
    "adobe": "adobe.com",
    "tcs": "tcs.com",
    "tata consultancy services": "tcs.com",
    "infosys": "infosys.com",
    "wipro": "wipro.com",
    "cognizant": "cognizant.com",
    "accenture": "accenture.com",
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
    "morgan stanley": "morganstanley.com",
    "citigroup": "citi.com",
    "stripe": "stripe.com",
    "uber": "uber.com",
    "airbnb": "airbnb.com",
    "spotify": "spotify.com"
}

def safe_ddgs_search(
    query: str,
    max_results: int = 15,
    serper_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes resilient multi-engine search:
    1. Serper API (if SERPER_API_KEY provided or in environment) - searches Google directly with 0 datacenter blocks.
    2. Yahoo engine via DDGS (backend='yahoo') - fast, reliable on cloud hosts like Render/AWS.
    3. Bing engine via DDGS (backend='bing') - reliable on cloud hosts.
    4. Auto / DuckDuckGo fallback.
    """
    # 1. Check Serper API (Free 2,500 Google queries)
    api_key = serper_api_key or os.getenv("SERPER_API_KEY")
    if api_key:
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": max_results}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("organic", []):
                        results.append({
                            "title": item.get("title", ""),
                            "href": item.get("link", ""),
                            "body": item.get("snippet", "")
                        })
                    if results:
                        return results
        except Exception:
            pass

    # 2. Free search engines: Yahoo, Bing, Auto, DuckDuckGo
    # Yahoo and Bing do NOT block AWS/Render cloud IPs like DuckDuckGo does
    for backend in ["yahoo", "bing", "auto", "duckduckgo"]:
        try:
            ddgs = DDGS(timeout=5)
            results = list(ddgs.text(query, backend=backend, max_results=max_results))
            if results:
                return results
        except Exception:
            continue
    return []

def resolve_company_domain(company_name: str, apollo_api_key: Optional[str] = None) -> str:
    """Finds the primary domain for a given company name."""
    clean_name = company_name.strip().lower()
    if clean_name in KNOWN_COMPANY_DOMAINS:
        return KNOWN_COMPANY_DOMAINS[clean_name]

    # Check Apollo Organization Enrichment if API key provided
    if apollo_api_key:
        apollo_org = enrich_organization_apollo(clean_name, apollo_api_key)
        if apollo_org and apollo_org.get("domain"):
            return apollo_org["domain"]

    # Search web for official website
    query = f'"{company_name}" official website'
    try:
        results = safe_ddgs_search(query, max_results=5)
        ignored = [
            'wikipedia.org', 'linkedin.com', 'facebook.com', 'twitter.com',
            'x.com', 'youtube.com', 'glassdoor.com', 'indeed.com',
            'bloomberg.com', 'crunchbase.com', 'instagram.com', 'github.com'
        ]
        for r in results:
            href = r.get('href', '')
            parsed = urllib.parse.urlparse(href)
            netloc = parsed.netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            if netloc and not any(ign in netloc for ign in ignored):
                return netloc
    except Exception:
        pass

    # Fallback: sanitized company name + .com
    sanitized = re.sub(r'[^a-zA-Z0-9]', '', clean_name)
    return f"{sanitized}.com" if sanitized else "company.com"

def verify_mx_records(domain: str) -> Tuple[bool, List[str], str]:
    """
    Checks if a domain has valid DNS MX records and detects mail provider.
    Returns: (is_valid, mx_hosts, provider_summary)
    """
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        sorted_records = sorted(answers, key=lambda r: r.preference)
        hosts = [str(r.exchange).rstrip('.') for r in sorted_records]
        
        # Identify common mail gateways
        combined = " ".join(hosts).lower()
        if "google" in combined or "aspmx" in combined:
            provider = "Google Workspace"
        elif "outlook" in combined or "microsoft" in combined:
            provider = "Microsoft 365"
        elif "pphosted" in combined or "proofpoint" in combined:
            provider = "Proofpoint Enterprise"
        elif "mimecast" in combined:
            provider = "Mimecast Secure"
        elif "barracuda" in combined:
            provider = "Barracuda Networks"
        else:
            provider = "Custom / Enterprise MX"
            
        return True, hosts, provider
    except Exception:
        return False, [], "No MX Records Found"

def parse_person_name(raw_name: str) -> Dict[str, str]:
    """
    Parses full name, first name, and last name while stripping titles,
    credentials, nicknames, and trailing noise.
    """
    name = raw_name.strip()
    # Strip nicknames in quotes or parentheses (e.g. Brenda (Tepp) Small -> Brenda Small)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'["\'][^"\']*["\']', '', name)

    # Strip salutations/prefixes
    prefixes = [r'\bDr\.?\b', r'\bMr\.?\b', r'\bMs\.?\b', r'\bMrs\.?\b', r'\bProf\.?\b']
    for p in prefixes:
        name = re.sub(p, '', name, flags=re.IGNORECASE)

    # Strip academic, professional credentials and suffixes
    suffixes = [
        r'\bJr\.?\b', r'\bSr\.?\b', r'\bII\b', r'\bIII\b', r'\bIV\b',
        r'\bSPHR\b', r'\bPHR\b', r'\bSHRM-[A-Z]+\b', r'\bMBA\b', r'\bPMP\b',
        r'\bPhD\b', r'\bPh\.D\.?\b', r'\bCPA\b', r'\bCIPD\b', r'\bMS\b',
        r'\bMSc\b', r'\bBSc\b', r'\bBA\b', r'\bEsq\.?\b', r'\bMD\b'
    ]
    for s in suffixes:
        name = re.sub(s, '', name, flags=re.IGNORECASE)

    # Remove unwanted punctuation
    name = re.sub(r'[,|/\\#@!?:;~`]', ' ', name)
    words = [w.strip('. ') for w in name.split() if w.strip('. ')]

    if not words:
        cleaned = raw_name.strip()
        return {"full_name": cleaned, "first_name": cleaned, "last_name": ""}
    if len(words) == 1:
        w = words[0].title()
        return {"full_name": w, "first_name": w, "last_name": ""}

    first_name = words[0].title()
    last_name = words[-1].title()
    full_name = " ".join([w.title() for w in words])

    return {
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name
    }

def generate_email_permutations(first_name: str, last_name: str, domain: str) -> Dict[str, str]:
    """Generates standard corporate email formats."""
    f = re.sub(r'[^a-zA-Z]', '', first_name).lower()
    l = re.sub(r'[^a-zA-Z]', '', last_name).lower()
    dom = domain.lower().strip()

    if not f and not l:
        return {"default": f"contact@{dom}"}
    if not l:
        return {"first": f"{f}@{dom}"}
    if not f:
        return {"last": f"{l}@{dom}"}

    f_init = f[0]
    l_init = l[0]

    return {
        "first.last": f"{f}.{l}@{dom}",      # john.doe@domain.com (Default standard)
        "flast": f"{f_init}{l}@{dom}",        # jdoe@domain.com
        "firstlast": f"{f}{l}@{dom}",        # johndoe@domain.com
        "first_last": f"{f}_{l}@{dom}",      # john_doe@domain.com
        "first": f"{f}@{dom}",               # john@domain.com
        "last.first": f"{l}.{f}@{dom}",      # doe.john@domain.com
        "first.l": f"{f}.{l_init}@{dom}",    # john.d@domain.com
        "fl": f"{f_init}{l_init}@{dom}"      # jd@domain.com
    }

def extract_email_from_text(text: str, domain: Optional[str] = None) -> Optional[str]:
    """Extracts email addresses matching domain from text or snippets."""
    if not text:
        return None
    matches = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    if not matches:
        return None
    # Prefer emails matching domain if provided
    if domain:
        dom_clean = domain.lower()
        for m in matches:
            if dom_clean in m.lower():
                return m
    return matches[0]

def query_hunter_io(first_name: str, last_name: str, domain: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Enrich lead using Hunter.io Email Finder API if API key provided."""
    if not api_key:
        return None
    try:
        url = "https://api.hunter.io/v2/email-finder"
        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key
        }
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                email = data.get("email")
                score = data.get("score", 0)
                if email:
                    return {
                        "email": email,
                        "confidence": f"Hunter Verified ({score}%)",
                        "score": score
                    }
    except Exception:
        pass
    return None

def query_apollo_io(
    first_name: str,
    last_name: str,
    domain: Optional[str] = None,
    organization_name: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Enrich lead using Apollo.io People Match API.
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

        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                person = resp.json().get("person") or {}
                email = person.get("email")
                status = person.get("email_status") or "verified"
                # Exclude masked or locked emails
                if email and "email_not_unlocked" not in email:
                    return {
                        "email": email,
                        "confidence": f"Apollo Verified ({status})",
                        "status": status,
                        "title": person.get("title")
                    }
    except Exception as e:
        print(f"Apollo match error: {e}")
    return None

def enrich_organization_apollo(domain_or_name: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Enrich company details and verify domain using Apollo.io Organization Enrichment API.
    Works on Free & Paid Apollo plans.
    """
    if not api_key:
        return None
    try:
        url = f"https://api.apollo.io/v1/organizations/enrich?domain={urllib.parse.quote(domain_or_name)}"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": api_key.strip()
        }
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                org = resp.json().get("organization") or {}
                website = org.get("website_url") or ""
                parsed = urllib.parse.urlparse(website)
                dom = parsed.netloc.lower()
                if dom.startswith("www."):
                    dom = dom[4:]
                return {
                    "name": org.get("name"),
                    "domain": dom,
                    "linkedin_url": org.get("linkedin_url"),
                    "employees": org.get("estimated_num_employees"),
                    "industry": org.get("industry")
                }
    except Exception as e:
        print(f"Apollo org enrichment error: {e}")
    return None

