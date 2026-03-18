import random
import httpx

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://www.linkedin.com/",
    "https://www.google.co.in/",
]

SEC_CH_UA_LIST = [
    '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    '"Chromium";v="121", "Not(A:Brand";v="99", "Google Chrome";v="121"',
    '"Microsoft Edge";v="121", "Not(A:Brand";v="99", "Chromium";v="121"',
]


def get_headers() -> dict:
    ua = random.choice(USER_AGENTS)
    is_chrome = "Chrome" in ua and "Edg" not in ua
    is_edge = "Edg" in ua
    is_firefox = "Firefox" in ua
    is_safari = "Safari" in ua and "Chrome" not in ua

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,hi;q=0.6",
            "en-IN,en;q=0.9",
        ]),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": random.choice(REFERERS),
        "Cache-Control": random.choice(["no-cache", "max-age=0"]),
        "Upgrade-Insecure-Requests": "1",
    }

    if is_chrome or is_edge:
        headers["sec-ch-ua"] = random.choice(SEC_CH_UA_LIST)
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = random.choice(['"Windows"', '"macOS"', '"Linux"'])
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "cross-site"
        headers["Sec-Fetch-User"] = "?1"

    return headers


def get_api_headers() -> dict:
    """Headers specifically for LinkedIn's JSON API endpoints."""
    headers = get_headers()
    headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    })
    return headers


def build_client(proxies: str | None = None, timeout: float = 20.0) -> httpx.AsyncClient:
    """Build an async HTTP client with optional proxy and connection pooling."""
    transport_kwargs = {}
    if proxies:
        transport_kwargs["proxy"] = proxies

    return httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        **transport_kwargs,
    )
