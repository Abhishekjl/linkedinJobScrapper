"""Quick debug: fetch a LinkedIn company page and print relevant text."""
import asyncio
from anti_detect import build_client, get_headers

URL = "https://www.linkedin.com/company/google"

async def main():
    async with build_client() as client:
        r = await client.get(URL, headers=get_headers())
        html = r.text

    # Print sections likely to contain follower/employee info
    import re
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    print("=== Visible text snippets containing 'follow' or 'employ' ===")
    text = soup.get_text(" ", strip=True)
    for line in text.split(" "):
        pass  # too noisy, use regex instead

    matches = re.findall(r'.{0,60}(?:follow|employ).{0,60}', text, re.IGNORECASE)
    for m in matches:
        print(repr(m))

    print("\n=== Script tags with JSON data ===")
    for script in soup.find_all("script", type=re.compile(r"json", re.I)):
        content = script.string or ""
        if "follow" in content.lower() or "employ" in content.lower():
            # print first 500 chars
            print(content[:500])
            print("---")

asyncio.run(main())
