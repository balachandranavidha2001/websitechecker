import os
import requests

def whois_api_lookup(domain):
    key = os.getenv('WHOIS_API_KEY')
    if not key:
        raise RuntimeError("WHOIS_API_KEY not set")
    url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={key}&domainName={domain}&outputFormat=JSON"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()