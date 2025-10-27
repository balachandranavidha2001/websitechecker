from flask import Flask, render_template, request, jsonify
import os
import requests
from urllib.parse import urlparse
from datetime import datetime
import validators  
from bs4 import BeautifulSoup
import time 
import re
import socket
from urllib.parse import urljoin, urlsplit

app = Flask(__name__)

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
        # "sitemap_url": None  <-- REMOVED
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

    # --- SITEMAP FINDER LOGIC REMOVED ---

    # WHOIS / domain info (try python-whois first, fallback to RDAP over HTTPS)
    try:
        w = whois.whois(domain)

        def get_date(date_val):
            if isinstance(date_val, list):
                return date_val[0] if date_val else None
            return date_val

        creation_date = get_date(w.creation_date)
        expiration_date = get_date(w.expiration_date)
        updated_date = get_date(w.updated_date)

        result['domain_info'] = {
            "domain": domain,
            "registrar": w.registrar or "Unknown",
            "registered_on": creation_date.strftime('%Y-%m-%d %H:%M:%S') if creation_date else "Unknown",
            "expires_on": expiration_date.strftime('%Y-%m-%d %H:%M:%S') if expiration_date else "Unknown",
            "updated_on": updated_date.strftime('%Y-%m-%d %H:%M:%S') if updated_date else "Unknown",
        }
    except Exception as e:
        # Log the failure (visible in Render logs)
        print(f"WHOIS failed for {domain}: {e}")

        # RDAP fallback via HTTPS (rdap.org) — Render allows HTTPS egress
        try:
            rdap_resp = requests.get(f"https://rdap.org/domain/{domain}", timeout=10,
                                     headers={'User-Agent': 'WebsiteChecker/1.0'})
            if rdap_resp.ok:
                rdap = rdap_resp.json()

                # helper parse
                def parse_iso(dt):
                    try:
                        if not dt:
                            return None
                        # rdap times often end with 'Z'
                        return datetime.fromisoformat(dt.replace('Z', '+00:00'))
                    except Exception:
                        return None

                creation_date = None
                expiration_date = None
                updated_date = None
                # 'events' is common in RDAP responses
                for ev in rdap.get('events', []):
                    action = ev.get('eventAction', '').lower()
                    date = ev.get('eventDate')
                    if 'registration' in action:
                        creation_date = parse_iso(date)
                    elif 'expiration' in action:
                        expiration_date = parse_iso(date)
                    elif 'last' in action or 'update' in action:
                        updated_date = parse_iso(date)

                # registrar extraction best-effort
                registrar = "Unknown"
                entities = rdap.get('entities') or []
                if entities:
                    # try to find a vcard with org/name
                    ent = entities[0]
                    vcard = ent.get('vcardArray')
                    if vcard and len(vcard) > 1:
                        for item in vcard[1]:
                            if len(item) >= 4 and item[0].lower() in ('fn', 'org', 'organization'):
                                registrar = item[3] or registrar
                                break

                result['domain_info'] = {
                    "domain": domain,
                    "registrar": registrar or "Unknown",
                    "registered_on": creation_date.strftime('%Y-%m-%d %H:%M:%S') if creation_date else "Unknown",
                    "expires_on": expiration_date.strftime('%Y-%m-%d %H:%M:%S') if expiration_date else "Unknown",
                    "updated_on": updated_date.strftime('%Y-%m-%d %H:%M:%S') if updated_date else "Unknown",
                }
            else:
                print(f"RDAP lookup returned {rdap_resp.status_code} for {domain}")
                result['domain_info'] = {}
        except Exception as e2:
            print(f"RDAP fallback failed for {domain}: {e2}")
            result['domain_info'] = {}
    
    end_time = time.perf_counter() 
    result['duration'] = f"{end_time - start_time:.2f}s" 
    return result


def _parse_iso(dt):
    try:
        if not dt:
            return None
        return datetime.fromisoformat(dt.replace('Z', '+00:00'))
    except Exception:
        return None

def get_domain_info(raw):
    domain = raw.strip()
    # normalize: remove scheme/path
    if domain.startswith('http://') or domain.startswith('https://'):
        domain = urlparse(domain).netloc
    domain = domain.rstrip('/')

    result = {"domain": domain, "registrar": "Unknown", "registered_on": "Unknown",
              "expires_on": "Unknown", "updated_on": "Unknown"}

    # Try python-whois first (if installed)
    try:
        import whois
        w = whois.whois(domain)
        def _first(d):
            if isinstance(d, list):
                return d[0] if d else None
            return d
        creation = _first(w.creation_date)
        expiration = _first(w.expiration_date)
        updated = _first(w.updated_date)

        if creation:
            result['registered_on'] = creation.strftime('%Y-%m-%d %H:%M:%S') if hasattr(creation, 'strftime') else str(creation)
        if expiration:
            result['expires_on'] = expiration.strftime('%Y-%m-%d %H:%M:%S') if hasattr(expiration, 'strftime') else str(expiration)
        if updated:
            result['updated_on'] = updated.strftime('%Y-%m-%d %H:%M:%S') if hasattr(updated, 'strftime') else str(updated)
        result['registrar'] = w.registrar or result['registrar']

        # return early if we have meaningful data
        if result['registrar'] != "Unknown" or result['registered_on'] != "Unknown":
            return result
    except Exception as e:
        print(f"[domain] python-whois failed for {domain}: {e}")

    # RDAP HTTPS fallback (rdap.org)
    try:
        rdap_resp = requests.get(f"https://rdap.org/domain/{domain}", timeout=10,
                                 headers={'User-Agent': 'WebsiteChecker/1.0'})
        if rdap_resp.ok:
            rdap = rdap_resp.json()
            creation = expiration = updated = None
            for ev in rdap.get('events', []):
                action = (ev.get('eventAction') or '').lower()
                date = ev.get('eventDate')
                if 'registration' in action:
                    creation = _parse_iso(date) or creation
                elif 'expiration' in action:
                    expiration = _parse_iso(date) or expiration
                elif 'last' in action or 'update' in action:
                    updated = _parse_iso(date) or updated

            if creation:
                result['registered_on'] = creation.strftime('%Y-%m-%d %H:%M:%S')
            if expiration:
                result['expires_on'] = expiration.strftime('%Y-%m-%d %H:%M:%S')
            if updated:
                result['updated_on'] = updated.strftime('%Y-%m-%d %H:%M:%S')

            # try to extract registrar from entities/vcard
            entities = rdap.get('entities') or []
            if entities:
                for ent in entities:
                    vcard = ent.get('vcardArray')
                    if vcard and len(vcard) > 1:
                        for item in vcard[1]:
                            if len(item) >= 4 and item[0].lower() in ('fn', 'org', 'organization'):
                                registrar = item[3] or None
                                if registrar:
                                    result['registrar'] = registrar
                                    break
                    if result['registrar'] != "Unknown":
                        break
            # return if we have any useful data
            if result['registrar'] != "Unknown" or result['registered_on'] != "Unknown":
                return result
        else:
            print(f"[domain] RDAP returned status {rdap_resp.status_code} for {domain}")
    except Exception as e:
        print(f"[domain] RDAP failed for {domain}: {e}")

    # Optional commercial WHOIS API fallback (example: WHOISXMLAPI). Configure WHOIS_API_KEY in env.
    api_key = os.getenv('WHOIS_API_KEY')
    if api_key:
        try:
            api_url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={api_key}&domainName={domain}&outputFormat=JSON"
            r = requests.get(api_url, timeout=10, headers={'User-Agent': 'WebsiteChecker/1.0'})
            if r.ok:
                j = r.json()
                whois_record = j.get('WhoisRecord', {})
                registrar = whois_record.get('registrarName')
                created = whois_record.get('createdDate')
                expires = whois_record.get('expiresDate')
                updated = whois_record.get('updatedDate')
                if registrar:
                    result['registrar'] = registrar
                if created:
                    parsed = _parse_iso(created) or None
                    result['registered_on'] = parsed.strftime('%Y-%m-%d %H:%M:%S') if parsed else created
                if expires:
                    parsed = _parse_iso(expires) or None
                    result['expires_on'] = parsed.strftime('%Y-%m-%d %H:%M:%S') if parsed else expires
                if updated:
                    parsed = _parse_iso(updated) or None
                    result['updated_on'] = parsed.strftime('%Y-%m-%d %H:%M:%S') if parsed else updated
                return result
            else:
                print(f"[domain] WHOIS API returned {r.status_code} for {domain}")
        except Exception as e:
            print(f"[domain] WHOIS API failed for {domain}: {e}")

    # Nothing found; return Unknowns
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