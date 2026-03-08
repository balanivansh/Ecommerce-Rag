import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

def scrape_product_info(url: str) -> Dict[str, Any]:
    """Scrape product metadata from a given URL using BeautifulSoup."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Heuristics for typical e-com sites:
        title = soup.find('h1', class_=lambda c: c and 'title' in c.lower()) or soup.find('h1')
        title_text = title.get_text(strip=True) if title else "Unknown Title"
        
        description = soup.find(class_=lambda c: c and 'desc' in c.lower()) or soup.find('p')
        desc_text = description.get_text(strip=True) if description else "No description available"
        
        # Grab raw text for SEO/CRO analysis
        full_text = soup.get_text(separator=' ', strip=True)[:5000] # Limit to 5000 chars roughly
        
        # Grab h1-h6 tags for SEO audit
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
        
        return {
            "title": title_text,
            "description": desc_text,
            "full_text": full_text,
            "headings": headings,
            "url": url,
            "success": True
        }
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}
