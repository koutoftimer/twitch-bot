import sqlite3
from collections.abc import Coroutine
from functools import cached_property
from typing import Any, Callable, Self

import httpx

from bot_config import Config, CLIENT_ID


class DB:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.conn = sqlite3.connect(filename)

    def __getitem__(self, key: str, /) -> str:
        self.__migration()
        res = self.conn.execute(
            "SELECT value FROM commands WHERE name = ?", (key,)
        ).fetchone()
        return res[0] if res else ""

    def __setitem__(self, key: str, value: str, /) -> None:
        self.__migration()
        self.conn.execute(
            """
            INSERT INTO commands (name, value)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.conn.commit()

    def __migration(self):
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                name TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        self.conn.commit()


Permission = Callable[["Context"], bool]


def is_admin(ctx: "Context") -> bool:
    return ctx.author == ctx.config.chat_channel_user_name


class Command:
    def __init__(
        self,
        process: Callable[["Context"], Coroutine[Any, Any, None]],
        permissions: list[Permission],
        usage: Callable[[Self], str],
    ) -> None:
        self.process = process
        self.permissions = permissions
        self.usage = usage(self)

    async def __call__(self, config: Config, text: str, author: str) -> None:
        ctx = Context(config, text, author)
        if all(guard(ctx) for guard in self.permissions):
            return await self.process(ctx)

        await send_message(
            config,
            f"@{author} you aren't alllowed to execute this command",
        )

    @cached_property
    def name(self) -> str:
        return f"!{self.process.__name__.replace('_', '-')}"


class Context:
    def __init__(self, config: Config, text: str, author: str):
        self.db = DB(".db.sqlite3")
        self.config = config
        self.text = text
        self.author = author


COMMANDS = dict[str, Command]()


def register_command(
    usage: Callable[[Command], str],
    permissions: list[Permission] | None = None,
):
    permissions = [] if permissions is None else permissions

    def wrapper(f: Callable[[Context], Coroutine[Any, Any, None]]):
        command = Command(usage=usage, process=f, permissions=permissions)
        if command.name in COMMANDS:
            raise ValueError("Repeating command name")
        COMMANDS[command.name] = command
        return command

    return wrapper


async def send_message(config: Config, msg: str) -> None:
    headers = {
        "Authorization": f"Bearer {config.access_token}",
        "Client-Id": CLIENT_ID,
        "Content-Type": "application/json",
    }
    payload = {
        "broadcaster_id": config.chat_channel_user_id,
        "sender_id": config.bot_user_id,
        "message": msg[:500],
    }
    async with httpx.AsyncClient() as client:
        await client.post(
            url="https://api.twitch.tv/helix/chat/messages",
            headers=headers,
            json=payload,
        )


@register_command(
    lambda self: (
        f"{self.name} - to list available commands or "
        f"{self.name} <command_name> - to show usage for provided commad"
    )
)
async def help(ctx: Context) -> None:
    parts = ctx.text.split(maxsplit=1)

    if len(parts) == 1:
        names = ", ".join(sorted(COMMANDS.keys()))
        return await send_message(ctx.config, f"Bot commands: {names}")

    if len(parts) != 2:
        return await send_message(
            ctx.config, f"@{ctx.author} too many arguments. Type {help.usage}"
        )

    command_name = parts[1]
    if command_name not in COMMANDS:
        return await send_message(ctx.config, f"@{ctx.author} {command_name} not found")

    command = COMMANDS[command_name]
    await send_message(ctx.config, f"@{ctx.author} {command_name} {command.usage}")


@register_command(
    lambda self: f"{self.name} - describes current project or what I'm working on"
)
async def project(ctx: Context) -> None:
    await send_message(ctx.config, f"@{ctx.author} {ctx.db["project"]}")


@register_command(
    lambda self: f"{self.name} - set output for {project.name}",
    permissions=[is_admin],
)
async def set_project(ctx: Context) -> None:
    parts = ctx.text.split(maxsplit=1)
    if len(parts) != 2:
        return await send_message(
            ctx.config,
            f"@{ctx.author} no project description provided",
        )

    ctx.db["project"] = parts[1]
    await send_message(ctx.config, f"@{ctx.author} project description updated")
