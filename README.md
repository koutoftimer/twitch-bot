# What is it?

This is **just** a port of the [official chat client][1] example for NodeJS
into Python. And a few bot commands.

I've tried to follow [suckless][2] so if you have an idea how to improve
codebase do not hesitate to [create an Issue][3].

*Note:* it doesn't do correct reconnects yet.

# Use case

Its only use case is to show most recent messages in the terminal window.

# Configuration

Configurations and instructions in `config.py`

# Usage

To configure bot you need to pass several environment variables as shown in `.env.example`.

```console
$ cp .env.example .env
```

modify `.env`

```console
$ source .env
```

Create virtual environment and activate it.

```console
(venv) $ pip install -r requirements.txt
(venv) $ python twitch_bot.py
```

Use `requirements-frozen.txt` if you have some errors or create an Issue.

   [1]: https://dev.twitch.tv/docs/chat/chatbot-guide/#example-code
   [2]: https://suckless.org/
   [3]: https://github.com/aukamo/twitch-bot/issues/new
