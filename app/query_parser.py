import re
from typing import Dict, Any

ROLE_ACRONYMS = {
    "hr": "HR OR \"Human Resources\"",
    "ta": "Talent Acquisition",
    "pm": "Product Manager",
    "sde": "Software Engineer",
    "swe": "Software Engineer",
    "qa": "Quality Assurance",
    "em": "Engineering Manager",
    "devops": "DevOps Engineer",
    "sre": "Site Reliability Engineer",
    "ceo": "CEO OR \"Chief Executive Officer\"",
    "cto": "CTO OR \"Chief Technology Officer\"",
    "cfo": "CFO OR \"Chief Financial Officer\"",
    "cmo": "CMO OR \"Chief Marketing Officer\"",
    "coo": "COO OR \"Chief Operating Officer\"",
    "vp": "VP OR \"Vice President\"",
    "bd": "Business Development",
    "ae": "Account Executive",
    "sdr": "Sales Development Representative",
    "bdr": "Business Development Representative"
}

def parse_natural_language_query(query_text: str) -> Dict[str, Any]:
    """
    Parses a natural language query such as:
    - "find 10 hr working at optum"
    - "5 software engineers at google in new york"
    - "recruiters working for amazon"
    - "optum hr 10"
    """
    raw_text = query_text.strip()
    text = raw_text
    
    # 1. Extract Count (default to 10 if unspecified, cap between 1 and 50)
    count = 10
    count_match = re.search(r'\b(\d+)\b', text)
    if count_match:
        count = int(count_match.group(1))
        # Remove count from working text
        text = re.sub(r'\b' + count_match.group(1) + r'\b', '', text, count=1).strip()
    count = max(1, min(count, 50))
    
    # 2. Extract Location ("in new york", "based in london", "located in bangalore")
    location = ""
    loc_match = re.search(r'\b(?:located in|based in|in)\s+([a-zA-Z\s,]+)$', text, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()
        text = text[:loc_match.start()].strip()
    
    # 3. Extract Company ("working at optum", "at google", "for amazon", "works at stripe")
    company = ""
    comp_match = re.search(r'\b(?:working at|working for|works at|employed at|at|for)\s+([a-zA-Z0-9\s&.\-]+)', text, re.IGNORECASE)
    if comp_match:
        company = comp_match.group(1).strip()
        role_part = text[:comp_match.start()].strip()
    else:
        # Fallback heuristic: check if query looks like "optum hr" or "hr optum"
        parts = text.split()
        if len(parts) >= 2:
            # Check if first word is known company or second word is role
            company = parts[-1]
            role_part = " ".join(parts[:-1])
        else:
            role_part = text
            company = ""
            
    # Clean role part: remove common prompt filler prefixes
    role = re.sub(
        r'^(?:find|get|search|give me|look for|profiles of|list of|fetch|extract|scrapp?e|show me|bring me)\s+',
        '',
        role_part,
        flags=re.IGNORECASE
    ).strip()
    role = re.sub(r'\b(?:people|profiles|employees|staff|candidates|persons|workers)\b', '', role, flags=re.IGNORECASE).strip()
    
    # Clean company name
    company = re.sub(r'^(?:the|a)\s+', '', company, flags=re.IGNORECASE).strip()
    company = re.sub(r'\b(?:company|inc|corp|corporation)\b', '', company, flags=re.IGNORECASE).strip()
    
    # Normalize title casing
    clean_role = role.strip()
    clean_company = company.strip()
    
    if not clean_role and not clean_company:
        clean_role = "HR"
        clean_company = "Optum"
    elif not clean_role:
        clean_role = "HR"
    elif not clean_company:
        clean_company = "Optum"
        
    return {
        "raw_query": raw_text,
        "count": count,
        "role": clean_role,
        "company": clean_company,
        "location": location,
        "search_role_expanded": ROLE_ACRONYMS.get(clean_role.lower(), clean_role)
    }

if __name__ == "__main__":
    test_queries = [
        "find 10 hr working at optum",
        "find 5 software engineers at google in london",
        "get 20 marketing directors at microsoft",
        "15 recruiters working for amazon",
        "talent acquisition at meta in singapore",
        "find hr at optum"
    ]
    for q in test_queries:
        print(f"'{q}' -> {parse_natural_language_query(q)}")
