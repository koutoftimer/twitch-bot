import json
import socket
import sys
import urllib
import urllib.parse
from typing import Any

import requests
import websocket

from config import REDIRECT_URL, CLIENT_ID, USER_LOGIN

access_token: str = ""
session_id: str = ""
# This is the User ID of the chat bot
bot_user_id = ""
# This is the User ID of the channel that the bot will join and listen to chat messages of
chat_channel_user_id = ""


def get_auth():
    resp = requests.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={"Authorization": f"OAuth {access_token}"},
    )
    if resp.status_code != 200:
        data = resp.json()
        print(
            f"Token is not valid. /oauth2/validate returned status code {resp.status_code}",
            file=sys.stderr,
        )
        print(data, file=sys.stderr)
        exit(1)
    print("Valid token")


def get_user_id():
    global chat_channel_user_id, bot_user_id, USER_LOGIN
    resp = requests.get(
        f"https://api.twitch.tv/helix/users?login={USER_LOGIN}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": CLIENT_ID,
        },
    )
    data = resp.json()
    if resp.status_code != 200:
        print(
            f"Failed to get user_id for {USER_LOGIN}",
            file=sys.stderr,
        )
        print(data)
        exit(1)
    chat_channel_user_id = data["data"][0]["id"]
    print(f"channel_user_id: {chat_channel_user_id}")

    resp = requests.get(
        f"https://api.twitch.tv/helix/users",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": CLIENT_ID,
        },
    )
    data = resp.json()
    if resp.status_code != 200:
        print(
            f"Failed to get user_id for {USER_LOGIN}",
            file=sys.stderr,
        )
        print(data)
        exit(1)
    bot_user_id = data["data"][0]["id"]
    print(f"user_id: {bot_user_id}")


def register_listeners():
    global chat_channel_user_id, bot_user_id, session_id
    resp = requests.post(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Client-Id": CLIENT_ID,
            "Content-Type": "application/json",
        },
        json={
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": chat_channel_user_id,
                "user_id": bot_user_id,
            },
            "transport": {
                "method": "websocket",
                "session_id": session_id,
            },
        },
    )
    data = resp.json()
    if resp.status_code != 202:
        print(
            f"Failed to subscribe to channel.chat.message. API call returned status code {resp.status_code}",
            file=sys.stderr,
        )
        print(data)
        exit(1)

    print(f"Subscribed to channel.chat.message [{data['data'][0]['id']}]")


def on_open(_: websocket.WebSocket):
    print("Connection opened")


def on_message(_: websocket.WebSocket, msg: Any):
    data = json.loads(msg)
    message_type = data["metadata"]["message_type"]

    if message_type == "session_welcome":
        global session_id
        session_id = data["payload"]["session"]["id"]
        register_listeners()
    elif message_type == "session_keepalive":
        pass
    elif message_type == "notification":
        text = data["payload"]["event"]["message"]["text"]
        username = data["payload"]["event"]["chatter_user_name"]
        print(f"{username}: {text}")
    else:
        print(f"Message receieved {type(msg)}, {msg}", file=sys.stderr)


def on_error(_: websocket.WebSocket, msg: Any):
    print(f"Error {msg}", file=sys.stderr)


def startWebSocketClient():
    ws_app = websocket.WebSocketApp(
        "wss://eventsub.wss.twitch.tv/ws",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
    )
    ws_app.run_forever()


def get_access_token():
    params = urllib.parse.urlencode(
        dict(
            response_type="token",
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URL,
            scope="user:bot user:read:chat user:write:chat",
        )
    )
    print("Authorize via following url:")
    print(f"https://id.twitch.tv/oauth2/authorize?{params}")

    REDIRECTION_SCRIPT = (
        "<script>location.href = location.href.replace('#', '?')</script>"
    )

    def token_accepted(client: socket.socket) -> bool:
        msg = client.recv(1 << 20).decode("utf-8").splitlines()
        requested_url = msg[0].split()[1]

        if requested_url == "/":
            client.send("HTTP/1.1 200 OK\r\n\r\n".encode("utf-8"))
            client.send(REDIRECTION_SCRIPT.encode("utf-8"))
            return False

        if "access_token" in requested_url:
            parts = urllib.parse.urlparse(requested_url)
            query = urllib.parse.parse_qs(parts.query)
            global access_token
            access_token = query["access_token"][0]
            client.send("HTTP/1.1 200 OK\r\n\r\nDONE".encode("utf-8"))
            client.close()
            return True

        client.send("HTTP/1.1 404 Not found\r\n\r\n".encode("utf-8"))
        return False

    with socket.create_server(("localhost", 3000)) as sock:
        client, _ = sock.accept()
        while not token_accepted(client):
            client.close()
            client, _ = sock.accept()


def main():
    get_access_token()
    get_auth()
    get_user_id()
    startWebSocketClient()


if __name__ == "__main__":
    main()
