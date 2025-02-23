import asyncio
import json
import logging
import logging.config
import socket
import urllib
import urllib.parse
from typing import Any

import httpx
from websockets.asyncio.client import connect, ClientConnection

from bot_config import Config, CLIENT_ID, USER_LOGIN, REDIRECT_URL
from commands import COMMANDS, send_message

logger = logging.getLogger("twitch-bot")


def validate(config: Config):
    resp = httpx.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={"Authorization": f"OAuth {config.access_token}"},
    )

    if resp.status_code != 200:
        logger.fatal(f"/oauth2/validate returned status code {resp.status_code}")
        logger.debug(resp.text)
        raise SystemExit(1)

    logger.info("Valid token")


def get_user_id(config: Config):

    def helper(url: str) -> tuple[str, str]:
        headers = {
            "Authorization": f"Bearer {config.access_token}",
            "Client-Id": CLIENT_ID,
        }
        resp = httpx.get(url, headers=headers)

        if resp.status_code != 200:
            logger.debug(resp.text)
            logger.fatal(f"Failed to get channel_user_id for {USER_LOGIN}")
            raise SystemExit(1)

        return resp.json()["data"][0]["id"], resp.json()["data"][0]["display_name"]

    config.chat_channel_user_id, _ = helper(
        f"https://api.twitch.tv/helix/users?login={USER_LOGIN}"
    )
    config.bot_user_id, config.chat_channel_user_name = helper(
        f"https://api.twitch.tv/helix/users"
    )


def register_listeners(config: Config):
    resp = httpx.post(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Client-Id": CLIENT_ID,
            "Content-Type": "application/json",
        },
        json={
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": config.chat_channel_user_id,
                "user_id": config.bot_user_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": config.session_id,
            },
        },
    )

    data = resp.json()
    if resp.status_code != 202:
        logger.fatal(
            "Failed to subscribe to channel.chat.message. "
            f"API call returned status code {resp.status_code}"
        )
        logger.fatal(data)
        raise SystemExit(1)

    logger.info(f"Subscribed to channel.chat.message [{data['data'][0]['id']}]")


async def process_command(config: Config, text: str, author: str):
    command = COMMANDS.get(text.split(maxsplit=1)[0].lower(), None)
    if command is not None:
        await command(config, text, author)
    else:
        await COMMANDS["!help"](config, text, author)


async def on_message(ws: ClientConnection, msg: Any, config: Config):
    data = json.loads(msg)
    message_type = data["metadata"]["message_type"]

    if message_type == "session_welcome":
        config.session_id = data["payload"]["session"]["id"]
        register_listeners(config)
        await send_message(config, "Twitch bot is up and running")

    elif message_type == "session_keepalive":
        pass

    elif message_type == "notification":
        text = data["payload"]["event"]["message"]["text"]
        username = data["payload"]["event"]["chatter_user_name"]
        print(f"{username}: {text}")
        if text.startswith("!"):
            await process_command(config, text, username)

    elif message_type == "session_reconnect":
        url = data["payload"]["session"]["reconnect_url"]
        logger.error(f"session_reconnect {msg}")
        await startWebSocketClient(config, url)

    elif message_type == "revocation":
        logger.error(f"revocation {msg}")
        await ws.close()

    else:
        logger.error(f"unknown message type {msg}")


async def startWebSocketClient(
    config: Config,
    url: str = "wss://eventsub.wss.twitch.tv/ws",
):
    async with connect(url) as ws:
        async for msg in ws:
            await on_message(ws, msg, config)


REDIRECTION_SCRIPT = b"<script>location.href = location.href.replace('#', '?')</script>"


def get_access_token(config: Config):
    data = dict(
        response_type="token",
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URL,
        scope="user:bot user:read:chat user:write:chat",
    )
    query = urllib.parse.urlencode(data)
    auth_url = f"https://id.twitch.tv/oauth2/authorize?{query}"
    print(f"Authorize via following url: http://localhost:3000/auth")

    server = socket.create_server(("0.0.0.0", 3000))
    while True:
        conn, _ = server.accept()
        request = conn.recv(1 << 20).split(b"\r\n")[0]

        if not request.startswith(b"GET"):
            logger.debug(f"Bad request: {request=}")
            continue

        requested_url = request.split()[1].decode("utf-8")
        logger.debug(f"route {requested_url}")

        if requested_url == "/":
            conn.sendall(b"HTTP/1.1 200 OK\r\n\r\n" + REDIRECTION_SCRIPT)
            continue

        if requested_url == "/auth":
            location = f"Location: {auth_url}".encode("utf-8")
            conn.sendall(b"HTTP/1.1 303 See Other\r\n" + location + b"\r\n\r\n")
            continue

        if "access_token" in requested_url:
            parts = urllib.parse.urlparse(requested_url)
            query = urllib.parse.parse_qs(parts.query)
            config.access_token = query["access_token"][0]
            logger.debug("access_token is set")
            conn.sendall(b"HTTP/1.1 200 OK\r\n\r\nDONE")
            break

        conn.sendall(b"HTTP/1.1 404 Not found\r\n\r\n")


async def main():
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"simple": {"format": "%(levelname)-8s - %(message)s"}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "level": "DEBUG",
                    "formatter": "simple",
                    "stream": "ext://sys.stdout",
                },
                "stderr": {
                    "class": "logging.StreamHandler",
                    "level": "ERROR",
                    "formatter": "simple",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "twitch-bot": {
                    "level": "DEBUG",
                    "handlers": ["stderr", "stdout"],
                },
            },
        }
    )
    config = Config()

    get_access_token(config)
    validate(config)
    get_user_id(config)
    await startWebSocketClient(config)


if __name__ == "__main__":
    asyncio.run(main())
