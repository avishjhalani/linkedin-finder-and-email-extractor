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

def resolve_company_domain(company_name: str) -> str:
    """Finds the primary domain for a given company name."""
    clean_name = company_name.strip().lower()
    if clean_name in KNOWN_COMPANY_DOMAINS:
        return KNOWN_COMPANY_DOMAINS[clean_name]

    # Search web for official website
    query = f'"{company_name}" official website'
    try:
        results = list(DDGS().text(query, max_results=5))
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
