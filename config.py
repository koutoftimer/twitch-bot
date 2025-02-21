# This is the URL you can find at https://dev.twitch.tv/console/apps
# NOTE: copy paste to avoid typing mistakes
REDIRECT_URL = "http://localhost:3000/"

# At dev console you can find Cliend ID. Put it in the file ".client_id"
# NOTE: You can just create a quoted string similar to REDIRECT_URL
CLIENT_ID = open(".client_id").read().strip()

# Id of the user whose channel to join. Put in in the file ".user_login"
# NOTE: You can just create a quoted string similar to REDIRECT_URL
USER_LOGIN = open(".user_login").read().strip()
