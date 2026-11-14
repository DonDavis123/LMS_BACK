CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"

# openid + email identify the Google account; calendar.events lets us create
# and update events (and Google Meet links) on the user's calendar.
OAUTH_SCOPES = ("openid", "email", CALENDAR_EVENTS_SCOPE)
