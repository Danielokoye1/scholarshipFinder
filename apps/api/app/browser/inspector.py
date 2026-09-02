import hashlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.browser.network import UnsafeBrowserTarget, redact_url, validate_browser_url
from app.config import settings


@dataclass(frozen=True)
class RawFormField:
    ordinal: int
    form_index: int
    tag_name: str
    input_type: str
    label: str
    required: bool
    disabled: bool
    autocomplete: str | None


@dataclass(frozen=True)
class InspectionResult:
    final_url: str
    final_domain: str
    redirect_chain: list[str]
    page_title: str | None
    response_status: int | None
    page_content_hash: str
    fields: list[RawFormField]
    barriers: list[str]
    blocked_requests: list[dict[str, str]]


class BrowserInspectionError(RuntimeError):
    def __init__(self, category: str, message: str, blocked_requests: list[dict[str, str]] | None = None):
        self.category = category
        self.blocked_requests = blocked_requests or []
        super().__init__(message)


MAX_BLOCKED_REQUEST_RECORDS = 50


FIELD_SCRIPT = """
() => {
  const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim().slice(0, 500);
  const controls = Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'));
  return controls.map((element, ordinal) => {
    const labels = element.labels ? Array.from(element.labels).map((item) => item.innerText).join(' ') : '';
    const aria = element.getAttribute('aria-label') || '';
    const placeholder = element.getAttribute('placeholder') || '';
    const nearby = element.closest('label')?.innerText || '';
    const fallback = element.getAttribute('name') || element.getAttribute('id') || '';
    const form = element.closest('form');
    const forms = Array.from(document.forms);
    return {
      ordinal,
      form_index: form ? Math.max(forms.indexOf(form), 0) : 0,
      tag_name: element.tagName.toLowerCase(),
      input_type: (element.getAttribute('type') || element.tagName).toLowerCase().slice(0, 40),
      label: clean(labels || aria || nearby || placeholder || fallback || `Unlabeled field ${ordinal + 1}`),
      required: Boolean(element.required || element.getAttribute('aria-required') === 'true'),
      disabled: Boolean(element.disabled),
      autocomplete: clean(element.getAttribute('autocomplete')) || null,
    };
  });
}
"""

BARRIER_SCRIPT = """
() => {
  const text = (document.body?.innerText || '').toLowerCase().slice(0, 200000);
  const has = (selector) => Boolean(document.querySelector(selector));
  const barriers = [];
  if (has('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], [class*="captcha" i], [id*="captcha" i]') || /\\bcaptcha\\b/.test(text)) barriers.push('captcha');
  if (/\\b(two[- ]factor|2fa|one[- ]time (code|password)|verification code|authenticator code)\\b/.test(text)) barriers.push('two_factor_authentication');
  if (/\\b(recommendation|recommender|letter of recommendation)\\b/.test(text)) barriers.push('recommendation');
  if (/\\b(electronic signature|type your signature|applicant signature)\\b/.test(text)) barriers.push('signature');
  if (/\\b(i certify|i attest|under penalty of perjury)\\b/.test(text)) barriers.push('attestation');
  if (has('input[type="file"]')) barriers.push('file_upload');
  if (Array.from(document.querySelectorAll('textarea')).some((el) => /essay|personal statement|short answer|describe|explain/i.test(`${el.labels?.[0]?.innerText || ''} ${el.getAttribute('aria-label') || ''} ${el.name || ''}`))) barriers.push('essay');
  return Array.from(new Set(barriers));
}
"""


def clean_title(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip()[:500] or None


def inspect_application_page(
    url: str,
    *,
    allow_private_network: bool = False,
    allow_http: bool = False,
) -> InspectionResult:
    blocked_requests: list[dict[str, str]] = []
    navigation_chain: list[str] = []
    request_count = 0

    def record_blocked_request(request_url: str, category: str, reason: str) -> None:
        if len(blocked_requests) < MAX_BLOCKED_REQUEST_RECORDS:
            blocked_requests.append(
                {"url": redact_url(request_url), "category": category, "reason": reason}
            )

    try:
        initial = validate_browser_url(
            url,
            allow_private_network=allow_private_network,
            allow_http=allow_http,
        )
    except UnsafeBrowserTarget as error:
        raise BrowserInspectionError(error.category, str(error)) from error

    try:
        with sync_playwright() as playwright:
            pinned_address = next(
                (address for address in initial.addresses if ":" not in address),
                initial.addresses[0],
            )
            browser = playwright.chromium.launch(
                channel=settings.browser_channel,
                headless=True,
                args=[
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-domain-reliability",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--no-first-run",
                    f"--host-resolver-rules=MAP {initial.hostname} {pinned_address}",
                ],
            )
            context = browser.new_context(
                accept_downloads=False,
                service_workers="block",
                java_script_enabled=True,
            )

            def guard_request(route: Any, request: Any) -> None:
                nonlocal request_count
                request_count += 1
                try:
                    if request_count > settings.inspection_max_requests:
                        raise UnsafeBrowserTarget("request_limit", "The page exceeded the inspection request limit")
                    if request.method not in {"GET", "HEAD", "OPTIONS"}:
                        raise UnsafeBrowserTarget("unsafe_method", "Non-read-only browser requests are blocked")
                    if request.resource_type in {"image", "media", "font"}:
                        route.abort("blockedbyclient")
                        return
                    parsed = urlsplit(request.url)
                    if parsed.scheme in {"data", "blob", "about"}:
                        route.continue_()
                        return
                    is_navigation = request.is_navigation_request()
                    validate_browser_url(
                        request.url,
                        navigation_domain=initial.hostname,
                        allow_private_network=allow_private_network,
                        allow_http=allow_http,
                    )
                    if is_navigation:
                        redacted = redact_url(request.url)
                        if not navigation_chain or navigation_chain[-1] != redacted:
                            navigation_chain.append(redacted)
                    route.continue_()
                except UnsafeBrowserTarget as error:
                    record_blocked_request(request.url, error.category, str(error))
                    route.abort("blockedbyclient")

            def block_websocket(socket_route: Any) -> None:
                record_blocked_request(
                    socket_route.url,
                    "websocket_blocked",
                    "WebSocket connections are disabled during read-only inspection",
                )
                socket_route.close(code=1008, reason="Read-only inspection")

            context.route("**/*", guard_request)
            context.route_web_socket("**/*", block_websocket)
            page = context.new_page()
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=settings.inspection_timeout_ms,
                )
                page.wait_for_timeout(settings.inspection_settle_ms)
                if blocked_requests and not page.url.startswith(("http://", "https://")):
                    latest = blocked_requests[-1]
                    raise BrowserInspectionError(latest["category"], latest["reason"], blocked_requests)
                final_target = validate_browser_url(
                    page.url,
                    navigation_domain=initial.hostname,
                    allow_private_network=allow_private_network,
                    allow_http=allow_http,
                )
                if response is not None and response.status >= 400:
                    raise BrowserInspectionError(
                        "http_error",
                        f"The application page returned HTTP {response.status}",
                        blocked_requests,
                    )
                raw_fields = page.evaluate(FIELD_SCRIPT)
                if len(raw_fields) > settings.inspection_max_fields:
                    raise BrowserInspectionError(
                        "field_limit",
                        "The page contains too many fields for a safe automatic inspection",
                        blocked_requests,
                    )
                barriers = page.evaluate(BARRIER_SCRIPT)
                content = page.content().encode("utf-8")
                if len(content) > settings.inspection_max_html_bytes:
                    raise BrowserInspectionError(
                        "content_limit",
                        "The page is too large for a safe automatic inspection",
                        blocked_requests,
                    )
                content_hash = hashlib.sha256(content).hexdigest()
                fields = [RawFormField(**item) for item in raw_fields]
                return InspectionResult(
                    final_url=redact_url(page.url),
                    final_domain=final_target.hostname,
                    redirect_chain=navigation_chain or [redact_url(url)],
                    page_title=clean_title(page.title()),
                    response_status=response.status if response else None,
                    page_content_hash=content_hash,
                    fields=fields,
                    barriers=list(barriers),
                    blocked_requests=blocked_requests,
                )
            finally:
                context.close()
                browser.close()
    except BrowserInspectionError:
        raise
    except PlaywrightTimeoutError as error:
        raise BrowserInspectionError("timeout", "The application page inspection timed out", blocked_requests) from error
    except PlaywrightError as error:
        category = blocked_requests[-1]["category"] if blocked_requests else "browser_error"
        message = blocked_requests[-1]["reason"] if blocked_requests else "The isolated browser could not inspect this page"
        raise BrowserInspectionError(category, message, blocked_requests) from error
