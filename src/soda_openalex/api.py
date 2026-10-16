"""Small, dependency-free OpenAlex client. Never log authenticated URLs."""
from . import __version__
import json
import os
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MAX_PER_PAGE = 100


class Client:
    def __init__(self, retries=5, interval=0.15):
        self.key = os.environ.get("OPENALEX_API_KEY")
        self.retries = retries
        self.interval = interval

    def get(self, endpoint, **params):
        if self.key:
            params["api_key"] = self.key
        request = Request("https://api.openalex.org/" + endpoint + "?" + urlencode(params),
                          headers={"User-Agent": f"soda-openalex/{__version__}"})
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.interval)
                with urlopen(request, timeout=90) as response:
                    return json.load(response)
            except (HTTPError, URLError, TimeoutError) as exc:
                retry = not isinstance(exc, HTTPError) or exc.code == 429 or 500 <= exc.code < 600
                if not retry or attempt == self.retries:
                    code = getattr(exc, "code", "network")
                    raise RuntimeError(f"OpenAlex {endpoint} request failed ({code}); credentials redacted") from None
                delay = min(60, 2 ** attempt)
                header = exc.headers.get("Retry-After") if isinstance(exc, HTTPError) else None
                if header:
                    try:
                        delay = float(header)
                    except ValueError:
                        try:
                            delay = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
                        except (TypeError, ValueError):
                            pass
                time.sleep(max(0, delay))

    def works_by_ids(self, ids):
        """Explicit refresh utility; never used during offline release rebuilds."""
        result = []
        for start in range(0, len(ids), 100):
            batch = ids[start:start + 100]
            response = self.get("works", filter="openalex:" + "|".join(batch), per_page=100, corpus="core")
            works = response["results"]
            if {w["id"] for w in works} != set(batch):
                raise ValueError("ID batch incomplete or merged; explicit reconciliation required")
            result.extend(works)
        return result
