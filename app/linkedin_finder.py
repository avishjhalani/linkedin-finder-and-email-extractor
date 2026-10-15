import re
import urllib.parse
from typing import List, Dict, Any, Optional
from ddgs import DDGS

from app.email_extractor import (
    resolve_company_domain,
    verify_mx_records,
    parse_person_name,
    generate_email_permutations,
    extract_email_from_text,
    query_hunter_io,
    query_apollo_io,
    safe_ddgs_search
)

def clean_linkedin_url(raw_url: str) -> str:
    """Cleans and standardizes LinkedIn profile URL."""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        # Keep clean https://www.linkedin.com/in/username
        path_parts = [p for p in parsed.path.split('/') if p]
        if 'in' in path_parts:
            idx = path_parts.index('in')
            if idx + 1 < len(path_parts):
                slug = path_parts[idx + 1]
                # If there's language subdomain like in.linkedin.com, keep or normalize
                netloc = parsed.netloc
                if not netloc.endswith("linkedin.com"):
                    netloc = "www.linkedin.com"
                return f"https://{netloc}/in/{slug}"
    except Exception:
        pass
    # Fallback strip query params
    return raw_url.split('?')[0].split('#')[0]

def clean_headline(title_part: str, snippet: str, company: str) -> str:
    """Extracts a neat headline / job title from search result."""
    title_part = title_part.replace('\ufffd', ' - ').replace('', ' - ')
    # Remove " | LinkedIn" and any subsequent titles
    cleaned = re.split(r'\s*\|\s*LinkedIn', title_part, flags=re.IGNORECASE)[0].strip()
    # If title has multiple separators like ' - '
    parts = cleaned.split(' - ')
    headline = parts[1].strip() if len(parts) >= 2 else cleaned
    
    # Remove trailing ellipses or trailing names that bleed in search engines
    headline = headline.split('...')[0].strip()
    headline = headline.split(' | ')[0].strip()
    headline = headline.split(' – ')[0].strip()
    
    # Clean redundant trailing company mentions if messy
    headline = re.sub(r'\s*@\s*LinkedIn.*$', '', headline, flags=re.IGNORECASE)
    
    if len(headline) < 3:
        # Fallback to snippet preview
        headline = snippet[:60].strip() + "..."
        
    return headline

def extract_location(text: str) -> str:
    """Tries to extract location from headline or snippet."""
    # Look for patterns like "Location: United States", "Greater Boston Area", "India"
    loc_match = re.search(r'(?:Location:\s*|based in\s+|in\s+)([A-Z][a-zA-Z\s,]+)(?:·|\||\n|$)', text)
    if loc_match:
        loc = loc_match.group(1).strip()
        if len(loc) < 30 and not any(w in loc.lower() for w in ['optum', 'linkedin', 'experience']):
            return loc
    return ""

def search_linkedin_leads(
    role: str,
    company: str,
    count: int = 10,
    location: str = "",
    preferred_pattern: str = "first.last",
    custom_domain: Optional[str] = None,
    hunter_api_key: Optional[str] = None,
    apollo_api_key: Optional[str] = None,
    serper_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Discovers LinkedIn profiles using X-Ray search and enriches with emails.
    """
    # 1. Resolve Company Domain and MX
    domain = custom_domain.strip().lower() if custom_domain else resolve_company_domain(company, apollo_api_key)
    mx_valid, mx_hosts, mail_provider = verify_mx_records(domain)
    
    # 2. Build search queries with location intelligence
    queries = []
    loc_clean = (location or "").strip().lower()
    
    if loc_clean == "india":
        # Targeted India queries
        queries.append(f'site:in.linkedin.com/in/ "{company}" "{role}"')
        queries.append(f'site:in.linkedin.com/in/ {company} {role}')
        queries.append(f'site:in.linkedin.com/in/ "{company}" ("{role}" OR "Human Resources" OR "Talent Acquisition")')
        queries.append(f'site:linkedin.com/in/ "{company}" ("{role}" OR "Human Resources") "India"')
        queries.append(f'site:linkedin.com/in/ "{company}" "{role}" (Bengaluru OR Hyderabad OR Gurgaon OR Noida OR India)')
    elif location:
        loc_part = f'"{location}"'
        queries.append(f'site:linkedin.com/in/ "{company}" "{role}" {loc_part}'.strip())
        queries.append(f'site:linkedin.com/in/ "{company}" {role} {loc_part}'.strip())
        queries.append(f'site:linkedin.com/in/ {company} {role} {loc_part}'.strip())
    else:
        queries.append(f'site:linkedin.com/in/ "{company}" "{role}"'.strip())
        queries.append(f'site:linkedin.com/in/ "{company}" {role}'.strip())
        queries.append(f'site:linkedin.com/in/ {company} {role}'.strip())

    foreign_domains = [
        'uk.linkedin.com', 'us.linkedin.com', 'au.linkedin.com', 'ca.linkedin.com',
        'ph.linkedin.com', 'ie.linkedin.com', 'sg.linkedin.com', 'nz.linkedin.com',
        'za.linkedin.com', 'my.linkedin.com', 'ae.linkedin.com', 'de.linkedin.com', 'fr.linkedin.com'
    ]
    indian_cities = [
        'india', 'bengaluru', 'bangalore', 'hyderabad', 'gurgaon', 'gurugram',
        'noida', 'mumbai', 'pune', 'chennai', 'delhi', 'new delhi', 'kolkata', 'ahmedabad'
    ]

    seen_urls = set()
    seen_names = set()
    leads = []
    
    for q in queries:
        if len(leads) >= count:
            break
        try:
            # Request extra results to account for deduplication
            fetch_limit = min(max(count * 2, 15), 50)
            raw_results = safe_ddgs_search(q, max_results=fetch_limit, serper_api_key=serper_api_key)
            
            for item in raw_results:
                if len(leads) >= count:
                    break
                
                raw_url = item.get('href', '')
                if '/in/' not in raw_url:
                    continue
                
                clean_url = clean_linkedin_url(raw_url)
                if clean_url in seen_urls:
                    continue

                title = item.get('title', '')
                snippet = item.get('body', '')

                # Strict location verification if India is specified
                if loc_clean == "india":
                    url_lower = clean_url.lower()
                    combined_text = (title + " " + snippet).lower()
                    if any(fd in url_lower for fd in foreign_domains):
                        continue
                    if "location: united states" in combined_text or "location: united kingdom" in combined_text or "location: philippines" in combined_text or "location: canada" in combined_text:
                        continue
                    if "in.linkedin.com" not in url_lower and not any(city in combined_text for city in indian_cities):
                        continue
                elif location:
                    combined_text = (title + " " + snippet).lower()
                    if loc_clean not in combined_text and loc_clean not in clean_url.lower():
                        continue
                
                # Extract person name and headline
                title_clean = title.split(' | LinkedIn')[0].strip()
                title_parts = title_clean.split(' - ')
                if len(title_parts) >= 2:
                    raw_name = title_parts[0].strip()
                    headline_raw = title_parts[1].strip()
                else:
                    title_parts_dash = title_clean.split(' – ')
                    if len(title_parts_dash) >= 2:
                        raw_name = title_parts_dash[0].strip()
                        headline_raw = title_parts_dash[1].strip()
                    else:
                        raw_name = title_clean
                        headline_raw = role
                        
                name_info = parse_person_name(raw_name)
                full_name = name_info['full_name']
                first_name = name_info['first_name']
                last_name = name_info['last_name']
                
                if not first_name or len(first_name) < 2:
                    continue
                if first_name.lower() in ['linkedin', 'profile', 'profiles', 'top', 'jobs', 'find', 'the', 'best', 'directory']:
                    continue
                if full_name.lower() in seen_names:
                    continue
                
                seen_urls.add(clean_url)
                seen_names.add(full_name.lower())
                
                headline = clean_headline(headline_raw, snippet, company)
                cand_loc = location or extract_location(snippet)
                
                # 3. Email Extraction & Generation
                permutations = generate_email_permutations(first_name, last_name, domain)
                
                # Check 1: Apollo.io enrichment if API key provided
                apollo_data = query_apollo_io(
                    first_name=first_name,
                    last_name=last_name,
                    domain=domain,
                    organization_name=company,
                    linkedin_url=clean_url,
                    api_key=apollo_api_key
                ) if apollo_api_key else None

                # Check 2: Hunter.io enrichment if API key provided
                hunter_data = query_hunter_io(first_name, last_name, domain, hunter_api_key) if hunter_api_key else None
                
                # Check 3: Snippet public email
                bio_email = extract_email_from_text(snippet, domain)
                
                if apollo_data:
                    final_email = apollo_data['email']
                    confidence = apollo_data['confidence']
                    email_source = "apollo"
                elif hunter_data:
                    final_email = hunter_data['email']
                    confidence = hunter_data['confidence']
                    email_source = "hunter"
                elif bio_email:
                    final_email = bio_email
                    confidence = "Verified (Public Bio)"
                    email_source = "bio"
                else:
                    # Pick email based on preferred pattern
                    final_email = permutations.get(preferred_pattern, permutations.get("first.last", f"{first_name.lower()}@{domain}"))
                    if mx_valid:
                        confidence = f"MX Verified ({preferred_pattern})"
                    else:
                        confidence = f"Pattern Guess ({preferred_pattern})"
                    email_source = "pattern"
                
                leads.append({
                    "id": len(leads) + 1,
                    "full_name": full_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": headline,
                    "company": company,
                    "domain": domain,
                    "location": cand_loc,
                    "email": final_email,
                    "confidence": confidence,
                    "email_source": email_source,
                    "email_permutations": permutations,
                    "linkedin_url": clean_url,
                    "snippet": snippet[:150] + "..." if len(snippet) > 150 else snippet
                })
        except Exception as e:
            print(f"Search iteration error for query '{q}': {e}")
            continue

    return {
        "query": {
            "role": role,
            "company": company,
            "location": location,
            "requested_count": count
        },
        "domain_info": {
            "domain": domain,
            "mx_valid": mx_valid,
            "mx_hosts": mx_hosts[:2],
            "mail_provider": mail_provider
        },
        "total_found": len(leads),
        "leads": leads
    }

if __name__ == "__main__":
    res = search_linkedin_leads("HR", "Optum", count=3)
    print(f"Found {res['total_found']} leads:")
    for lead in res['leads']:
        print(f"• {lead['full_name']} | {lead['job_title']} | {lead['email']} ({lead['confidence']})")
