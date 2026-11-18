"""Incremental handoff of upstream raster files to the caller's image store."""
from __future__ import annotations

import base64
import hashlib
import time
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from urllib.parse import parse_qsl, urlsplit

from fastapi import HTTPException

from services.image_failure import ImageDownloadError
from utils.helper import is_codex_image_model


def asset_identity(url):
    parsed = urlsplit(url)
    # The estuary endpoint encodes the file identity in its query string.
    query = [(k, v) for k, v in parse_qsl(parsed.query)
             if k.lower() not in {"sig", "se", "st", "sp", "sv", "sr", "skt", "ske", "sks", "skv",
                                  "ts", "signature", "expires", "key-pair-id", "policy"}
             and not k.lower().startswith("x-amz-")]
    return parsed.netloc.lower(), parsed.path, tuple(sorted(query))


def direct_stream(request, stream, generate):
    if not stream or is_codex_image_model(request.model) or str(request.output_format).lower() in {"svg", "gif"}:
        raise HTTPException(400, "upstream_stream requires a streaming Web raster image request")

    def events():
        queue = Queue(maxsize=6)
        closed = Event()
        lock = Lock()
        slots = {}

        def send(kind, value):
            while not closed.is_set():
                try:
                    queue.put((kind, value), timeout=0.2)
                    return
                except Full:
                    if request.deadline_monotonic and time.monotonic() >= request.deadline_monotonic:
                        closed.set()
                    continue
            raise ImageDownloadError("image delivery was cancelled")

        def ready(index, url, backend):
            identity = asset_identity(url)
            with lock:
                if slots.get(index) == identity:
                    return
                if index in slots or identity in slots.values() or not 0 <= index < request.n:
                    raise ImageDownloadError("upstream returned conflicting image slots")
                slots[index] = identity
            try:
                send("event", {"type": "image.start", "index": index})
                size = 0
                digest = hashlib.sha256()
                deadline = backend.deadline_monotonic or time.monotonic() + 120
                for chunk in backend.iter_image_file(url, deadline, 32 << 20):
                    size += len(chunk)
                    digest.update(chunk)
                    for offset in range(0, len(chunk), 48 * 1024):
                        frame = chunk[offset:offset + 48 * 1024]
                        send("event", {"type": "image.chunk", "index": index,
                                       "chunk": base64.b64encode(frame).decode("ascii")})
                if not size:
                    raise ImageDownloadError("empty upstream image")
                send("event", {"type": "image.ready", "index": index, "bytes": size,
                               "sha256": digest.hexdigest()})
            except Exception:
                if not closed.is_set():
                    send("error", ImageDownloadError("upstream image transfer failed"))
                raise

        def run():
            request.file_ready = ready
            attempts = []
            count = 0
            try:
                for output in generate(request):
                    for attempt in output.image_attempts:
                        if attempt not in attempts:
                            attempts.append(attempt)
                    if output.kind == "result":
                        if output.deliver_selected_files:
                            output.deliver_selected_files(count)
                        count += len(output.data)
                if count != request.n:
                    exc = ImageDownloadError(f"upstream supplied {count} of {request.n} images")
                    exc.image_attempts = attempts
                    raise exc
                send("done", attempts)
            except Exception as exc:
                if not closed.is_set():
                    send("error", exc)

        Thread(target=run, name="upstream-image-delivery", daemon=True).start()
        sent = set()
        try:
            while True:
                try:
                    kind, value = queue.get(timeout=0.5)
                except Empty:
                    if closed.is_set():
                        raise ImageDownloadError("image delivery timed out")
                    continue
                if kind == "error":
                    raise value
                if kind == "done":
                    if len(sent) != request.n:
                        exc = ImageDownloadError(f"upstream supplied {len(sent)} of {request.n} images")
                        exc.image_attempts = value
                        raise exc
                    yield {"type": "image_batch.completed", "count": len(sent), "_image_attempts": value}
                    return
                if value["type"] == "image.ready":
                    sent.add(value["index"])
                yield value
        finally:
            closed.set()

    return events()
