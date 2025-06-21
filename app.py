from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse

app = FastAPI(title="Website Scraper API", version="1.0.0")

class ScrapeRequest(BaseModel):
    url: HttpUrl
    timeout: Optional[int] = 10
    user_agent: Optional[str] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class CodeBlock(BaseModel):
    language: Optional[str] = None
    content: str
    tag: str

class ScrapedContent(BaseModel):
    url: str
    title: Optional[str] = None
    headers: Dict[str, List[str]]
    paragraphs: List[str]
    code_blocks: List[CodeBlock]
    meta_description: Optional[str] = None
    status_code: int

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    # Remove extra whitespace and normalize
    return re.sub(r'\s+', ' ', text.strip())

def extract_code_language(element) -> Optional[str]:
    """Extract programming language from code element classes"""
    classes = element.get('class', [])
    for cls in classes:
        # Common patterns for language classes
        if cls.startswith(('language-', 'lang-', 'highlight-')):
            return cls.split('-', 1)[1]
        elif cls in ['python', 'javascript', 'html', 'css', 'java', 'cpp', 'c', 'sql', 'json', 'xml']:
            return cls
    return None

def scrape_website(url: str, timeout: int = 10, user_agent: str = None) -> ScrapedContent:
    """
    Scrape a website and extract headers, paragraphs, and code blocks
    """
    headers = {
        'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = clean_text(title_tag.get_text()) if title_tag else None
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_description = meta_desc.get('content') if meta_desc else None
        
        # Extract headers (h1-h6)
        headers_dict = {}
        for i in range(1, 7):
            header_tag = f'h{i}'
            header_elements = soup.find_all(header_tag)
            if header_elements:
                headers_dict[header_tag] = [clean_text(h.get_text()) for h in header_elements if clean_text(h.get_text())]
        
        # Extract paragraphs
        paragraph_elements = soup.find_all('p')
        paragraphs = [clean_text(p.get_text()) for p in paragraph_elements if clean_text(p.get_text())]
        
        # Extract code blocks
        code_blocks = []
        
        # Look for various code-containing elements
        code_selectors = [
            'pre code',  # Most common: <pre><code>
            'pre',       # Just <pre>
            'code',      # Inline or block <code>
            '.highlight', # GitHub/GitLab style
            '.code-block',
            '.codehilite',
            '[class*="language-"]',
            '[class*="highlight-"]'
        ]
        
        processed_elements = set()  # To avoid duplicates
        
        for selector in code_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Skip if we've already processed this element
                element_id = id(element)
                if element_id in processed_elements:
                    continue
                processed_elements.add(element_id)
                
                content = element.get_text()
                if not content.strip():
                    continue
                
                # Determine language
                language = extract_code_language(element)
                
                # If it's a pre > code structure, check the code element too
                if element.name == 'pre':
                    code_child = element.find('code')
                    if code_child and not language:
                        language = extract_code_language(code_child)
                
                code_blocks.append(CodeBlock(
                    language=language,
                    content=content.strip(),
                    tag=element.name
                ))
        
        return ScrapedContent(
            url=str(url),
            title=title,
            headers=headers_dict,
            paragraphs=paragraphs,
            code_blocks=code_blocks,
            meta_description=meta_description,
            status_code=response.status_code
        )
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}")

@app.get("/")
async def root():
    return {
        "message": "Website Scraper API",
        "endpoints": {
            "/scrape": "POST - Scrape a website",
            "/docs": "API documentation"
        }
    }

@app.post("/scrape", response_model=ScrapedContent)
async def scrape_endpoint(request: ScrapeRequest):
    """
    Scrape a website and extract structured content
    
    - **url**: The URL to scrape
    - **timeout**: Request timeout in seconds (default: 10)
    - **user_agent**: Custom user agent string (optional)
    """
    return scrape_website(
        url=str(request.url),
        timeout=request.timeout,
        user_agent=request.user_agent
    )

@app.get("/scrape")
async def scrape_get(url: str, timeout: int = 10):
    """
    Scrape a website via GET request (for quick testing)
    
    - **url**: The URL to scrape
    - **timeout**: Request timeout in seconds
    """
    return scrape_website(url=url, timeout=timeout)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)