"""Drive a real landing page and form with headless Chromium (optional extra).

Install with ``pip install 'leadtrace[browser]'``. Playwright is imported only
when browser mode runs, so the core package keeps zero runtime dependencies.
"""

import json
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

# Canonical field -> URL query parameter carrying it on the landing URL.
URL_PARAMS = {
    "ft_source": "utm_source",
    "ft_medium": "utm_medium",
    "ft_campaign": "utm_campaign",
    "gclid": "gclid",
    "fbclid": "fbclid",
}
VISIBLE_FIELDS = ("email", "firstname", "lastname", "phone", "company")
STEP_TIMEOUT_MS = 30_000


class BrowserUnavailable(RuntimeError):
    """Playwright or a browser binary is missing."""


def _load_playwright():
    try:
        from playwright.sync_api import Error, TimeoutError, sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(
            "Browser mode needs Playwright. Install it with: pip install 'leadtrace[browser]'"
        ) from exc
    return sync_playwright, Error, TimeoutError


def landing_url(url, values):
    """Append the tracking params to ``url``, keeping any query it already has."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(param, values[field]) for field, param in URL_PARAMS.items()]
    return urlunsplit(parts._replace(query=urlencode(query)))


def parse_body(content_type, body):
    """Return the submitted fields as a flat dict, or None for unsupported encodings."""
    content_type = (content_type or "").split(";")[0].strip().lower()
    body = body or ""
    if content_type == "application/json":
        try:
            data = json.loads(body)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None
    if content_type in ("application/x-www-form-urlencoded", "text/plain", ""):
        return {key: values[0] for key, values in parse_qs(body, keep_blank_values=True).items()}
    return None


def submit_form(url, fields, *, selectors=None, submit="[type=submit]", browser_path=None):
    """Open ``url``, fill ``fields``, click submit, and capture the first POST.

    Returns a dict with ``final_url`` and either ``submitted`` (parsed body),
    ``submit_status`` and ``submit_url``, or ``error``.
    """
    sync_playwright, PlaywrightError, PlaywrightTimeout = _load_playwright()
    selectors = selectors or {}
    result = {"final_url": None}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, executable_path=browser_path or None)
        except PlaywrightError as exc:
            raise BrowserUnavailable(f"Could not launch a browser: {exc}".splitlines()[0]) from exc
        try:
            page = browser.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            page.goto(url, wait_until="load")
            result["final_url"] = page.url
            for name in VISIBLE_FIELDS:
                locator = page.locator(selectors.get(name, f"[name={name}]"))
                if locator.count() == 0:
                    if name == "email":
                        result["error"] = "No email field found on the page."
                        return result
                    continue
                locator.first.fill(str(fields[name]))
            if page.locator(submit).count() == 0:
                result["error"] = f"No submit control matches {submit!r}."
                return result
            with page.expect_request(lambda req: req.method == "POST") as captured:
                page.locator(submit).first.click()
            request = captured.value
            response = request.response()
            result["submit_url"] = request.url
            result["submit_status"] = response.status if response else None
            result["submitted"] = parse_body(request.headers.get("content-type"), request.post_data)
            if result["submitted"] is None:
                result["error"] = "Form body uses an unsupported encoding (urlencoded or JSON only)."
        except PlaywrightTimeout:
            result["error"] = "Timed out waiting for the page or the form POST."
        except PlaywrightError as exc:
            result["error"] = str(exc).splitlines()[0]
        finally:
            browser.close()
    return result
