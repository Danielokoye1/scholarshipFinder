import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


class UnsafeBrowserTarget(ValueError):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class ValidatedTarget:
    hostname: str
    addresses: tuple[str, ...]


TOKEN_LIKE_PATH_SEGMENT = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9._~-]{24,}$")


def redact_path(path: str) -> str:
    segments = path.split("/")
    redacted = [
        "[redacted]" if len(segment) > 64 or TOKEN_LIKE_PATH_SEGMENT.fullmatch(segment) else segment
        for segment in segments
    ]
    return "/".join(redacted) or "/"


def redact_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").casefold()
    if not hostname:
        return "invalid-url"
    try:
        is_ipv6 = ipaddress.ip_address(hostname).version == 6
    except ValueError:
        is_ipv6 = False
    netloc = f"[{hostname}]" if is_ipv6 else hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port and port not in {80, 443}:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme.casefold(), netloc, redact_path(parsed.path), "", ""))


def resolve_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise UnsafeBrowserTarget("dns_failure", "The destination hostname could not be resolved") from error
    return tuple(sorted({result[4][0] for result in results}))


def validate_browser_url(
    value: str,
    *,
    navigation_domain: str | None = None,
    allow_private_network: bool = False,
    allow_http: bool = False,
) -> ValidatedTarget:
    parsed = urlsplit(value)
    if parsed.scheme not in ({"http", "https"} if allow_http else {"https"}):
        raise UnsafeBrowserTarget("insecure_scheme", "Browser inspection requires HTTPS")
    if parsed.username or parsed.password:
        raise UnsafeBrowserTarget("embedded_credentials", "URLs containing credentials are blocked")
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if not hostname:
        raise UnsafeBrowserTarget("invalid_hostname", "The browser destination has no valid hostname")
    if navigation_domain and hostname != navigation_domain.casefold().rstrip("."):
        raise UnsafeBrowserTarget(
            "cross_domain_redirect",
            "The application requested a hostname that has not been approved",
        )
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise UnsafeBrowserTarget("invalid_port", "The browser destination uses an invalid port") from error
    if not allow_private_network and port not in ({80, 443} if allow_http else {443}):
        raise UnsafeBrowserTarget("unusual_port", "Non-standard destination ports are blocked")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        addresses = resolve_addresses(hostname, port)
    else:
        if not allow_private_network:
            raise UnsafeBrowserTarget("direct_ip", "Direct IP browser destinations are blocked")
        addresses = (hostname,)
    if not allow_private_network:
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise UnsafeBrowserTarget(
                    "private_network",
                    "The destination resolves to a private, local, reserved, or non-routable address",
                )
    return ValidatedTarget(hostname=hostname, addresses=addresses)
