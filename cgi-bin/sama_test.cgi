#!/usr/home/dka25y/samaenv/bin/python3
import asyncio
import os
import sys
from urllib.parse import unquote

sys.path.insert(0, "/usr/home/dka25y/public_html")

from SAMA_TRACK_V63_AUTOCOMPLETE_3CHAR import app


async def main():
    content_length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
    request_body = sys.stdin.buffer.read(content_length) if content_length > 0 else b""

    headers = []

    for env_name, header_name in [
        ("HTTP_AUTHORIZATION", b"authorization"),
        ("HTTP_COOKIE", b"cookie"),
        ("CONTENT_TYPE", b"content-type"),
        ("CONTENT_LENGTH", b"content-length"),
    ]:
        value = os.environ.get(env_name, "")
        if value:
            headers.append((header_name, value.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": os.environ.get("REQUEST_METHOD", "GET"),
        "scheme": "https" if os.environ.get("HTTPS") else "http",
        "path": unquote(os.environ.get("PATH_INFO", "/")),
        "raw_path": os.environ.get("PATH_INFO", "/").encode(),
        "query_string": os.environ.get("QUERY_STRING", "").encode(),
        "headers": headers,
        "client": (os.environ.get("REMOTE_ADDR", ""), 0),
        "server": (
            os.environ.get("SERVER_NAME", ""),
            int(os.environ.get("SERVER_PORT", "443"))
        ),
    }

    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {
                "type": "http.request",
                "body": request_body,
                "more_body": False,
            }

        return {
            "type": "http.disconnect",
        }

    response = {
        "status": 200,
        "headers": [],
        "body": b"",
    }

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
            response["headers"] = message["headers"]
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    await app(scope, receive, send)

    print("Status: %s" % response["status"])

    for name, value in response["headers"]:
        print(
            "%s: %s"
            % (
                name.decode("latin-1"),
                value.decode("latin-1"),
            )
        )

    print()
    sys.stdout.flush()
    sys.stdout.buffer.write(response["body"])


asyncio.run(main())
