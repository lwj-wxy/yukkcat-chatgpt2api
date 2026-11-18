"""Incremental handoff of upstream raster files to the caller's image store."""
from __future__ import annotations

from queue import Queue
from threading import Event, Thread
from urllib.parse import parse_qsl, urlsplit

from fastapi import HTTPException

from services.image_failure import ImageDownloadError
from utils.helper import is_codex_image_model
from utils.image_download_urls import validate_public_image_url


def asset_identity(url):
    parsed = urlsplit(url)
    # The estuary endpoint encodes the file identity in its query string.
    query = [(k, v) for k, v in parse_qsl(parsed.query)
             if k.lower() not in {"sig", "se", "st", "sp", "sv", "sr", "skt", "ske", "sks", "skv",
                                  "ts", "signature", "expires", "key-pair-id", "policy"}
             and not k.lower().startswith("x-amz-")]
    return parsed.netloc.lower(), parsed.path, tuple(sorted(query))


def public_asset(url):
    try:
        parsed, _ = validate_public_image_url(url)
        if parsed.scheme != "https":
            raise ValueError
    except (ValueError, OSError):
        raise ImageDownloadError("upstream did not provide a public HTTPS image URL") from None
    return url


def direct_stream(request, stream, generate):
    if not stream or is_codex_image_model(request.model) or str(request.output_format).lower() in {"svg", "gif"}:
        raise HTTPException(400, "upstream_url requires a streaming Web raster image request")

    def events():
        queue = Queue()
        closed = Event()

        def ready(index, url):
            if closed.is_set():
                raise ImageDownloadError("image delivery was cancelled")
            queue.put(("ready", (index, url)))

        def run():
            request.file_ready = ready
            attempts = []
            singles = 0
            try:
                for output in generate(request):
                    for attempt in output.image_attempts:
                        if attempt not in attempts:
                            attempts.append(attempt)
                    if output.kind != "result":
                        continue
                    for offset, item in enumerate(output.data):
                        index = (singles if request.images and len(output.data) == 1
                                 else offset if request.images else output.index - 1)
                        ready(index, item["url"])
                    singles += len(output.data)
                queue.put(("done", attempts))
            except Exception as exc:
                queue.put(("error", exc))

        Thread(target=run, name="upstream-image-delivery", daemon=True).start()
        sent = {}
        try:
            while True:
                kind, value = queue.get()
                if kind == "error":
                    raise value
                if kind == "done":
                    if len(sent) != request.n:
                        exc = ImageDownloadError(f"upstream supplied {len(sent)} of {request.n} images")
                        exc.image_attempts = value
                        raise exc
                    yield {"type": "image_batch.completed", "count": len(sent), "_image_attempts": value}
                    return
                index, url = value
                identity = asset_identity(url)
                if sent.get(index) == identity:
                    continue
                if not 0 <= index < request.n or index in sent or identity in sent.values():
                    raise ImageDownloadError("upstream returned conflicting image slots")
                sent[index] = identity
                yield {"type": "image.ready", "index": index, "url": public_asset(url)}
        finally:
            closed.set()

    return events()
