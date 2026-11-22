import json
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Any, Optional

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class InjectionResult:
    success: bool
    status_code: int
    url: str
    response_body: str
    is_dry_run: bool
    error_message: Optional[str] = None

def inject_lead(
    url: str,
    payload: Dict[str, Any],
    as_json: bool = True,
    headers: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
    timeout: float = 10.0,
    follow_redirects: bool = True
) -> InjectionResult:
    if dry_run or not url or url.startswith("mock://") or url == "dry-run":
        return InjectionResult(
            success=True,
            status_code=200,
            url=url or "dry-run://localhost",
            response_body=json.dumps({"status": "simulated_success", "payload_received": payload}),
            is_dry_run=True
        )

    req_headers = {"User-Agent": "FOCO-LeadTrace/0.2.0"}
    if headers:
        req_headers.update(headers)

    if as_json:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    else:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")

    try:
        open_url = urllib.request.urlopen if follow_redirects else urllib.request.build_opener(NoRedirect()).open
        with open_url(req, timeout=timeout) as response:
            res_body = response.read().decode("utf-8", errors="replace")
            status = response.status
            return InjectionResult(
                success=200 <= status < 300,
                status_code=status,
                url=url,
                response_body=res_body,
                is_dry_run=False
            )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        return InjectionResult(
            success=False,
            status_code=e.code,
            url=url,
            response_body=err_body,
            is_dry_run=False,
            error_message=f"HTTP {e.code}: {e.reason}"
        )
    except Exception as e:
        return InjectionResult(
            success=False,
            status_code=0,
            url=url,
            response_body="",
            is_dry_run=False,
            error_message=str(e)
        )
