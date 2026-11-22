"""Drive a real landing page and form with headless Chromium (optional extra).

Install with ``pip install 'leadtrace[browser]'``. Playwright is imported only
when browser mode runs, so the core package keeps zero runtime dependencies.
"""

import ipaddress
import json
import os
import time
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
SETTLE_TIMEOUT_MS = 5_000
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


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
    if content_type in ("text/plain", ""):
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                return data
        except ValueError:
            pass
    if content_type in ("application/x-www-form-urlencoded", "text/plain", ""):
        return {key: values[0] for key, values in parse_qs(body, keep_blank_values=True).items()}
    return None


def blocked_host(url):
    """True for literal private, link-local, or reserved IPs (cloud metadata, LAN).

    Loopback stays allowed so local test sites work. Hostnames are not resolved.
    """
    host = urlsplit(url).hostname or ""
    if host in LOOPBACK_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_loopback and (ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def _matches_lead(request, email):
    """True if the POST is the form: its parsed body, or its raw body if unparseable, has the email."""
    body = parse_body(request.headers.get("content-type"), request.post_data)
    if body is None:
        return email in (request.post_data or "")
    return body.get("email") == email


def submit_form(url, fields, *, selectors=None, submit="[type=submit]", browser_path=None):
    """Open ``url``, fill ``fields``, click submit, and capture the form POST.

    The form POST is the first POST whose body carries the synthetic email.
    Other POSTs (analytics beacons, pixels) are listed in ``other_posts``.
    Returns a dict with ``final_url``, ``other_posts``, ``blocked``, and either
    ``submitted`` with ``submit_url`` and ``submit_status``, or ``error``.
    """
    sync_playwright, PlaywrightError, PlaywrightTimeout = _load_playwright()
    selectors = selectors or {}
    email = fields["email"]
    result = {"final_url": None, "other_posts": [], "blocked": []}
    posts, responses, failed = [], [], []

    def guard(route):
        if blocked_host(route.request.url):
            result["blocked"].append(route.request.url)
            route.abort()
        else:
            route.continue_()

    with sync_playwright() as pw:
        args = ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []
        try:
            browser = pw.chromium.launch(headless=True, executable_path=browser_path or None, args=args)
        except PlaywrightError as exc:
            raise BrowserUnavailable(
                "Could not launch a browser. Set --browser-path or run: python -m playwright install chromium. "
                + str(exc).splitlines()[0]
            ) from exc
        try:
            page = browser.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            page.route("**/*", guard)
            page.goto(url, wait_until="load")
            try:
                page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)
            except PlaywrightTimeout:
                pass  # Long-polling pages never go idle; read the URL anyway.
            for name in VISIBLE_FIELDS:
                locator = page.locator(selectors.get(name, f"[name={name}]"))
                if locator.count() == 0:
                    if name == "email":
                        result["final_url"] = page.url
                        result["error"] = "No email field found on the page."
                        return result
                    continue
                locator.first.fill(str(fields[name]))
            # Read the URL at submit time, after deferred scripts had a chance to rewrite it.
            result["final_url"] = page.url
            if page.locator(submit).count() == 0:
                result["error"] = f"No submit control matches {submit!r}."
                return result
            page.on("request", lambda req: posts.append(req) if req.method == "POST" else None)
            page.on("response", lambda res: responses.append(res))
            page.on("requestfailed", lambda req: failed.append(req))
            page.locator(submit).first.click(no_wait_after=True)
            deadline = time.monotonic() + STEP_TIMEOUT_MS / 1000
            match = None
            while match is None and time.monotonic() < deadline:
                match = next((req for req in posts if _matches_lead(req, email)), None)
                if match is None:
                    page.wait_for_timeout(100)
            result["other_posts"] = [req.url for req in posts if req is not match]
            if match is None:
                result["error"] = "No POST carrying the synthetic email was sent after submit."
                return result
            result["submit_url"] = match.url
            result["submitted"] = parse_body(match.headers.get("content-type"), match.post_data)
            if result["submitted"] is None:
                result["error"] = "Form body uses an unsupported encoding (urlencoded or JSON only)."
                return result
            # Non-blocking wait for the form response, bounded by the same deadline.
            response = None
            while time.monotonic() < deadline and match not in failed:
                response = next((r for r in responses if r.request == match), None)
                if response is not None:
                    break
                page.wait_for_timeout(100)
            result["submit_status"] = response.status if response else None
        except PlaywrightTimeout:
            result["error"] = "Timed out waiting for the page or the form POST."
        except PlaywrightError as exc:
            result["error"] = str(exc).splitlines()[0]
        finally:
            browser.close()
    return result
