# INF601G - Advanced Programming in Python
# Kyle Horn
# Scheduled Check-In Bot

import os
import requests

# Gets the Practice Hub site address from the computer's environment variables
BASE_URL = os.environ.get("PRACTICE_API_URL")
# Gets the API token from the computer's environment variables
TOKEN = os.environ.get("PRACTICE_API_TOKEN")


# Creates a class that will contain all API methods
class PracticeHubClient:
    # Runs when a new PracticeHubClient object is created
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        # Creates the Authorization header using the API token as a Bearer token
        self.headers = {"Authorization": f"Bearer {token}"}

    def check_connection(self):
        """Calls a simple endpoint to confirm the URL and token both work."""
        resp = requests.get(f"{self.base}/api/v1/me", headers=self.headers)
        # A 200 response means the token was accepted
        if resp.ok:
            return True, resp.json()
        # Anything else means the URL or token is wrong
        return False, resp.status_code


# Checks if this file is being run directly instead of being imported
if __name__ == "__main__":
    # Stops the program early with a clear message if either setting is missing
    if not BASE_URL:
        raise SystemExit("PRACTICE_API_URL is not set.")
    if not TOKEN:
        raise SystemExit("PRACTICE_API_TOKEN is not set.")

    client = PracticeHubClient(BASE_URL, TOKEN)

    # Simple test: confirm we can authenticate without ever printing the token
    ok, result = client.check_connection()
    if ok:
        print(f"Connected to {BASE_URL} - authenticated as user id {result.get('id')}")
    else:
        raise SystemExit(f"Connection/authentication failed (status code {result})")
