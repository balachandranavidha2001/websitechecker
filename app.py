from flask import Flask, render_template, request, jsonify
import os
import requests
# import whois  <-- This line is removed
import validators
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import tldextract
import time
import re
from urllib.parse import urljoin, urlsplit

app = Flask(__name__)

# --- ADDED API CONFIG ---
API_KEY = os.environ.get('WHOIS_API_KEY')
API_URL = 'https://api.api-ninjas.com/v1/whois?domain='
# ------------------------

# --- CRAWLER FUNCTION ---
def crawl_site(start_url, max_pages=50):
    """Crawls a site to find internal links. Returns a set of URLs."""
    try:
        base_domain = urlsplit(start_url).netloc
        links_to_visit = {start_url}
        visited_links = set()
        headers = {'User-Agent': 'SitemapGeneratorBot/1.0'}

        while links_to_visit and len(visited_links) < max_pages:
            current_url = links_to_visit.pop()
            
            if current_url in visited_links:
                continue
                
            # Ensure we only crawl the same domain
            if urlsplit(current_url).netloc != base_domain:
                continue

            visited_links.add(current_url)

            try:
                response = requests.get(current_url, timeout=5, headers=headers)
                # Only parse successful HTML pages
                if response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', ''):
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href']
                        # Create an absolute URL from a relative one
                        absolute_link = urljoin(start_url, href)
                        
                        # Clean up fragments (#)
                        absolute_link = urlsplit(absolute_link)._replace(fragment="").geturl()
                        
                        if absolute_link not in visited_links:
                            links_to_visit.add(absolute_link)
            except Exception:
                continue # Ignore pages that fail to load

        return visited_links
    except Exception as e:
        print(f"Crawl failed for {start_url}: {e}")
        return {start_url} # Return at least the base URL


def extract_seo_from_html(html: str) -> dict:
    """Extracts comprehensive SEO info from an HTML page."""
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Basic SEO
        page_title = None
        if soup.title and soup.title.string:
            page_title = soup.title.string.strip()

        # Meta Description
        description = None
        meta_desc = soup.find('meta', attrs={'name': re.compile(r'^description$', re.I)})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': re.compile(r'^og:description$', re.I)})
        if meta_desc:
            description = (meta_desc.get('content') or '').strip() or None

        # Meta Keywords
        keywords = None
        meta_kw = soup.find('meta', attrs={'name': re.compile(r'^keywords$', re.I)})
        if meta_kw:
            keywords = (meta_kw.get('content') or '').strip() or None

        # Open Graph Tags
        og_title = None
        og_desc = None
        og_image = None
        og_url = None
        
        og_title_tag = soup.find('meta', attrs={'property': 'og:title'})
        if og_title_tag:
            og_title = (og_title_tag.get('content') or '').strip() or None
            
        og_desc_tag = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc_tag:
            og_desc = (og_desc_tag.get('content') or '').strip() or None
            
        og_image_tag = soup.find('meta', attrs={'property': 'og:image'})
        if og_image_tag:
            og_image = (og_image_tag.get('content') or '').strip() or None
            
        og_url_tag = soup.find('meta', attrs={'property': 'og:url'})
        if og_url_tag:
            og_url = (og_url_tag.get('content') or '').strip() or None

        # Twitter Cards
        twitter_card = None
        twitter_title = None
        twitter_desc = None
        twitter_image = None
        
        twitter_card_tag = soup.find('meta', attrs={'name': 'twitter:card'})
        if twitter_card_tag:
            twitter_card = (twitter_card_tag.get('content') or '').strip() or None
            
        twitter_title_tag = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title_tag:
            twitter_title = (twitter_title_tag.get('content') or '').strip() or None
            
        twitter_desc_tag = soup.find('meta', attrs={'name': 'twitter:description'})
        if twitter_desc_tag:
            twitter_desc = (twitter_desc_tag.get('content') or '').strip() or None
            
        twitter_image_tag = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image_tag:
            twitter_image = (twitter_image_tag.get('content') or '').strip() or None

        # Canonical URL
        canonical = None
        canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_tag:
            canonical = (canonical_tag.get('href') or '').strip() or None

        # Robots Meta
        robots = None
        robots_tag = soup.find('meta', attrs={'name': 'robots'})
        if robots_tag:
            robots = (robots_tag.get('content') or '').strip() or None

        # H1 Tags (for content analysis)
        h1_tags = [h1.get_text().strip() for h1 in soup.find_all('h1') if h1.get_text().strip()]

        # Image Alt Tags (for accessibility and SEO)
        images_without_alt = len(soup.find_all('img', alt=False))
        total_images = len(soup.find_all('img'))

        # SEO Score Calculation
        seo_score = 0
        max_score = 100
        
        # Title (20 points)
        if page_title and len(page_title) >= 30 and len(page_title) <= 60:
            seo_score += 20
        elif page_title:
            seo_score += 10
            
        # Description (20 points)
        if description and len(description) >= 120 and len(description) <= 160:
            seo_score += 20
        elif description:
            seo_score += 10
            
        # H1 Tags (15 points)
        if h1_tags:
            seo_score += 15
            
        # Canonical URL (10 points)
        if canonical:
            seo_score += 10
            
        # Open Graph (15 points)
        if og_title and og_desc:
            seo_score += 15
        elif og_title or og_desc:
            seo_score += 8
            
        # Twitter Cards (10 points)
        if twitter_card:
            seo_score += 10
            
        # Images with Alt (10 points)
        if total_images > 0:
            alt_ratio = (total_images - images_without_alt) / total_images
            seo_score += int(10 * alt_ratio)

        return {
            'title': page_title,
            'description': description,
            'keywords': keywords,
            'og_title': og_title,
            'og_description': og_desc,
            'og_image': og_image,
            'og_url': og_url,
            'twitter_card': twitter_card,
            'twitter_title': twitter_title,
            'twitter_description': twitter_desc,
            'twitter_image': twitter_image,
            'canonical': canonical,
            'robots': robots,
            'h1_tags': h1_tags,
            'images_without_alt': images_without_alt,
            'total_images': total_images,
            'seo_score': seo_score,
            'seo_grade': get_seo_grade(seo_score)
        }
    except Exception:
        return {
            'title': None,
            'description': None,
            'keywords': None,
            'og_title': None,
            'og_description': None,
            'og_image': None,
            'og_url': None,
            'twitter_card': None,
            'twitter_title': None,
            'twitter_description': None,
            'twitter_image': None,
            'canonical': None,
            'robots': None,
            'h1_tags': [],
            'images_without_alt': 0,
            'total_images': 0,
            'seo_score': 0,
            'seo_grade': 'F'
        }

def get_seo_grade(score):
    """Convert SEO score to letter grade."""
    if score >= 90:
        return 'A+'
    elif score >= 80:
        return 'A'
    elif score >= 70:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 50:
        return 'D'
    else:
        return 'F'

def check_url(url):
    """Checks a single URL and returns a result dictionary."""
    start_time = time.perf_counter() 

    result = {
        "url": url,
        "status": "",
        "domain_info": {},
        "seo": {"title": None, "description": None, "keywords": None},
        "duration": "0.00s",
    }

    # Validate URL
    if not validators.url(url):
        result['status'] = "Invalid URL"
        end_time = time.perf_counter()
        result['duration'] = f"{end_time - start_time:.2f}s"
        return result

    # Extract domain
    try:
        extracted = tldextract.extract(url)
        domain = extracted.domain + '.' + extracted.suffix
        if not extracted.domain or not extracted.suffix: 
             raise ValueError("Invalid domain")
    except Exception as e:
       result['status'] = "Invalid Domain"
       end_time = time.perf_counter()
       result['duration'] = f"{end_time - start_time:.2f}s"
       return result

    # Check if website is reachable and, if HTML, extract SEO info
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'WebsiteChecker/1.0'})
        result['status'] = f"Working ({response.status_code})"
        content_type = response.headers.get('Content-Type', '')
        if response.ok and 'text/html' in content_type:
            result['seo'] = extract_seo_from_html(response.text)
    except requests.exceptions.Timeout:
        result['status'] = "Not Working"
    except requests.exceptions.RequestException as e:
        result['status'] = "Not Working"


    # --- THIS BLOCK IS REPLACED ---
    if API_KEY:
        try:
            headers = { 'X-Api-Key': API_KEY }
            response = requests.get(API_URL + domain, headers=headers, timeout=5)
            response.raise_for_status() # Raise an error for bad status codes
            
            data = response.json()

            # Helper to convert API's Unix timestamps to a readable string
            def format_timestamp(ts):
                if not ts:
                    return "Unknown"
                try:
                    # API gives timestamps in seconds
                    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    return "Unknown"

            result['domain_info'] = {
                "domain": data.get("domain_name", domain),
                "registrar": data.get("registrar", "Unknown"),
                "registered_on": format_timestamp(data.get("creation_date")),
                "expires_on": format_timestamp(data.get("expiration_date")),
                "updated_on": format_timestamp(data.get("updated_date")),
            }
        
        except Exception as e:
            print(f"WHOIS API error: {e}") # For debugging in Vercel logs
            result['domain_info'] = {"error": "Could not fetch WHOIS data."}
    else:
        print("WHOIS API key not set.") # For debugging
        result['domain_info'] = {"error": "WHOIS API key not configured on server."}
    # --- END OF REPLACED BLOCK ---

    
    end_time = time.perf_counter() 
    result['duration'] = f"{end_time - start_time:.2f}s" 
    return result


@app.route("/", methods=["GET"])
def index():
    """Renders the main page."""
    return render_template("index.html")


@app.route("/check_one", methods=["POST"])
def check_one():
    """Checks a single URL sent via JSON."""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not url.startswith("http"):
        url_to_check = "http://" + url
    else:
        url_to_check = url

    result = check_url(url_to_check)
    result['url'] = url 
    
    return jsonify(result=result)

# --- NEW ROUTE TO GENERATE SITEMAP ---
@app.route("/generate_sitemap", methods=["POST"])
def generate_sitemap():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    if not url.startswith("http"):
        url = "http://" + url
        
    # Run the crawler
    found_urls = crawl_site(url)
    
    return jsonify(urls=list(found_urls))
# --- END OF NEW ROUTE ---


if __name__ == "__main__":
    app.run(debug=True)