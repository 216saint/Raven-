import requests
import random, re
import json
import os
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import warnings
warnings.filterwarnings("ignore")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
]

SEARCH_ENGINES = [
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
    {"name": "OnionLand", "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}"},
    {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
    {"name": "Amnesia", "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}"},
    {"name": "Kaizer", "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}"},
    {"name": "Anima", "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}"},
    {"name": "Tornado", "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}"},
    {"name": "TorNet", "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}"},
    {"name": "Torland", "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}"},
    {"name": "Find Tor", "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}"},
    {"name": "Excavator", "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}"},
    {"name": "Onionway", "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}"},
    {"name": "Tor66", "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}"},
    {"name": "OSS", "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}"},
    {"name": "Torgol", "url": "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}"},
    {"name": "The Deep Searches", "url": "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}"},
]

# Backward-compatible flat list used by existing search logic
DEFAULT_SEARCH_ENGINES = [e["url"] for e in SEARCH_ENGINES]

# Curated clearnet OSINT sources — only included when the user selects the
# "Dark Web + OSINT" search profile. These are reachable without Tor and
# index leaks, paste sites, breach repositories, and historical web content.
#
# Notes:
# - These endpoints render HTML aimed at humans, so result extraction is
#   best-effort (same as the .onion engines).
# - We deliberately do NOT include the CIA tipline .onion as a search target —
#   it has no query interface. It is referenced in the LLM system prompt as a
#   cross-reference for OPSEC/whistleblower guidance, alongside the Darknet
#   Bible primer.
OSINT_SOURCES = [
    {
        "name": "Intelligence X",
        "url": "https://intelx.io/?s={query}",
        "needs_tor": False,
    },
    {
        "name": "DDoSecrets",
        "url": "https://ddosecrets.com/wiki/Special:Search?search={query}",
        "needs_tor": False,
    },
    {
        "name": "Wayback Machine",
        "url": "https://web.archive.org/web/2024*/{query}",
        "needs_tor": False,
    },
]

OSINT_SOURCE_URLS = [s["url"] for s in OSINT_SOURCES]

def _build_session(use_tor: bool) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if use_tor:
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }
    return session


def get_tor_session():
    return _build_session(use_tor=True)


def fetch_search_results(endpoint, query):
    """Fetch results from a single search endpoint.

    Routes onion endpoints through Tor and clearnet OSINT sources through the
    direct connection (or the user's egress proxy, which the requests library
    picks up via HTTP_PROXY/HTTPS_PROXY env if set — kept out-of-band here).
    For OSINT sources we accept both onion AND clearnet links in the returned
    results, since some of those pages reference leaked .onion sites.
    """
    url = endpoint.format(query=query)
    use_tor = ".onion" in endpoint
    accept_clearnet = not use_tor  # OSINT pages frequently link to clearnet leaks too
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = _build_session(use_tor=use_tor)

    try:
        response = session.get(url, headers=headers, timeout=40)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        seen = set()
        for a in soup.find_all('a'):
            try:
                href = a.get('href') or ''
                title = a.get_text(strip=True)
                if len(title) <= 3:
                    continue
                # Onion links — primary harvest from any source
                onion_match = re.findall(r'https?:\/\/[a-z0-9\.\-]+\.onion[^\s"\'<>]*', href)
                if onion_match:
                    candidate = onion_match[0]
                    if "search" not in candidate and candidate not in seen:
                        seen.add(candidate)
                        links.append({"title": title, "link": candidate})
                        continue
                # Clearnet links — only kept from OSINT sources, and only if
                # they look like leak/breach/paste pages (heuristic filter).
                if accept_clearnet:
                    clear_match = re.findall(r'https?:\/\/[^\s"\'<>]+', href)
                    if clear_match:
                        candidate = clear_match[0]
                        if candidate in seen:
                            continue
                        low = candidate.lower()
                        if any(tok in low for tok in (
                            "leak", "breach", "dump", "paste", "torrent",
                            "archive.org/web", "ddosecrets", "intelx",
                        )):
                            seen.add(candidate)
                            links.append({"title": title, "link": candidate})
            except Exception:
                continue
        return links
    except Exception:
        return []


def get_search_results(refined_query, max_workers=5, include_osint=False):
    """Query the dark-web engines (and optionally OSINT clearnet sources) and
    return a deduplicated list of {title, link} dicts.
    """
    endpoints = list(DEFAULT_SEARCH_ENGINES)
    if include_osint:
        endpoints += OSINT_SOURCE_URLS

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_search_results, endpoint, refined_query)
                   for endpoint in endpoints]
        for future in as_completed(futures):
            try:
                result_urls = future.result()
            except Exception:
                result_urls = []
            results.extend(result_urls)

    seen_links = set()
    unique_results = []
    for res in results:
        link = res.get("link")
        if not link:
            continue
        clean_link = link.rstrip('/')
        if clean_link not in seen_links:
            seen_links.add(clean_link)
            unique_results.append(res)

    return unique_results
