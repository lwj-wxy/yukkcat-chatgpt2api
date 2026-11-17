"""Public image URL validation and DNS pinning shared by input/output downloads."""
import ipaddress
import socket
from urllib.parse import ParseResult, urlparse

from curl_cffi import CurlOpt


def validate_public_image_url(source: str) -> tuple[ParseResult, tuple[str, ...]]:
    """Validate a remote image URL before every network hop.

    Public image URLs are the supported contract. Resolving the hostname here
    blocks loopback, private, link-local, multicast, and other non-routable
    destinations that would otherwise make this endpoint an SSRF primitive.
    Redirects are validated independently by the caller.
    """
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("image_url must be an http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("image_url must not include credentials")
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid image_url host") from exc
    if not hostname:
        raise ValueError("invalid image_url host")
    normalized_host = hostname.rstrip(".").lower()
    if normalized_host in {"localhost", "localhost.localdomain"} or normalized_host.endswith(".local"):
        raise ValueError("image_url host is not publicly reachable")
    try:
        literal = ipaddress.ip_address(normalized_host)
    except ValueError:
        literal = None
    addresses: list[str]
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = [item[4][0] for item in socket.getaddrinfo(normalized_host, port, type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise ValueError("image_url host could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("image_url host is not publicly reachable")
    return parsed, tuple(dict.fromkeys(addresses))


def image_fetch_curl_options(parsed: ParseResult, addresses: tuple[str, ...]) -> dict[CurlOpt, object]:
    """Pin the connection to the public addresses validated for this hop."""
    hostname = parsed.hostname or ""
    try:
        ipaddress.ip_address(hostname.rstrip("."))
    except ValueError:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        resolved = [
            f"{hostname}:{port}:{f'[{address}]' if ':' in address else address}"
            for address in addresses
        ]
    else:
        resolved = []
    options: dict[CurlOpt, object] = {CurlOpt.NOPROXY: "*"}
    if resolved:
        options[CurlOpt.RESOLVE] = resolved
    return options
