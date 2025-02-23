import os
from dataclasses import dataclass

# This is the URL you can find at https://dev.twitch.tv/console/apps
# NOTE: copy paste to avoid typing mistakes
REDIRECT_URL = os.environ.get("REDIRECT_URL", "")

# At dev console you can find Cliend ID.
CLIENT_ID = os.environ.get("CLIENT_ID", "")

# Id of the user whose channel to join. Put in in the file ".user_login"
USER_LOGIN = os.environ.get("USER_LOGIN", "")


@dataclass(slots=True)
class Config:
    access_token: str = ""
    session_id: str = ""
    bot_user_id: str = ""
    chat_channel_user_id: str = ""
    chat_channel_user_name: str = ""
