import hashlib
import ipaddress
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}
GENERIC_SCHOLARSHIP_TOKENS = {
    "a",
    "an",
    "and",
    "award",
    "awards",
    "for",
    "fund",
    "grant",
    "program",
    "scholarship",
    "scholarships",
    "the",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def normalized_label(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(clean_text(value))
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Scholarship URLs must use http or https and include a hostname")

    scheme = parsed.scheme.casefold()
    hostname = parsed.hostname.casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = parsed.port
    try:
        is_ipv6 = ipaddress.ip_address(hostname).version == 6
    except ValueError:
        is_ipv6 = False
    netloc = f"[{hostname}]" if is_ipv6 else hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{netloc}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_PARAMETERS
        ),
        doseq=True,
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def content_hash(text: str) -> str:
    return hashlib.sha256(clean_text(text).encode("utf-8")).hexdigest()


def scholarship_fingerprint(
    name: str,
    provider: str | None,
    deadline: datetime | None,
    award_max_cents: int | None,
) -> str:
    identity: dict[str, Any] = {
        "name": normalized_label(name),
        "provider": normalized_label(provider),
        "deadline": deadline.astimezone(UTC).isoformat() if deadline else None,
        "award_max_cents": award_max_cents,
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def token_similarity(left: str, right: str) -> float:
    left_label = normalized_label(left)
    right_label = normalized_label(right)
    left_tokens = (
        {token for token in left_label.split() if token not in GENERIC_SCHOLARSHIP_TOKENS}
        if left_label
        else set()
    )
    right_tokens = (
        {token for token in right_label.split() if token not in GENERIC_SCHOLARSHIP_TOKENS}
        if right_label
        else set()
    )
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
