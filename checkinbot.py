# INF601G - Advanced Programming in Python
# Kyle Horn
# Scheduled Check-In Bot

import os
import requests

# Gets the Practice Hub site address from the computer's environment variables
BASE_URL = os.environ.get("PRACTICE_API_URL")
# Gets the API token from the computer's environment variables
TOKEN = os.environ.get("PRACTICE_API_TOKEN")
# Gets the instructor's user id from the computer's environment variables
INSTRUCTOR_ID = os.environ.get("INSTRUCTOR_ID")

# How many posts to request per page (the API allows up to 100)
PAGE_SIZE = 100


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

    def list_posts_page(self, author_id, limit, offset):
        """Gets one page of posts written by a specific author."""
        params = {"author": author_id, "limit": limit, "offset": offset}
        resp = requests.get(f"{self.base}/api/v1/posts", headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_all_posts_by_author(self, author_id):
        """Pages through every post by one author until there are no more pages left."""
        all_posts = []
        offset = 0

        while True:
            page = self.list_posts_page(author_id, PAGE_SIZE, offset)

            # No posts came back, so we've reached the end
            if not page:
                break

            all_posts.extend(page)

            # If the page came back smaller than what we asked for,
            # that means this was the last page
            if len(page) < PAGE_SIZE:
                break

            # Otherwise, move forward to request the next page
            offset += PAGE_SIZE

        return all_posts


def collect_instructor_posts(client, instructor_id):
    """Builds a clean list of dictionaries with everything Task 1 needs to save."""
    posts = client.get_all_posts_by_author(instructor_id)

    collected = []
    for post in posts:
        collected.append({
            "id": post["id"],
            "title": post["title"],
            "body": post["body"],
            "tags": post["tags"],
            "created_at": post["created_at"],
            "updated_at": post["updated_at"],
            "attachments": post.get("attachments", []),
        })
    return collected


# Checks if this file is being run directly instead of being imported
if __name__ == "__main__":
    # Stops the program early with a clear message if a required setting is missing
    if not BASE_URL:
        raise SystemExit("PRACTICE_API_URL is not set.")
    if not TOKEN:
        raise SystemExit("PRACTICE_API_TOKEN is not set.")
    if not INSTRUCTOR_ID:
        raise SystemExit("INSTRUCTOR_ID is not set.")

    client = PracticeHubClient(BASE_URL, TOKEN)

    # Simple test: confirm we can authenticate without ever printing the token
    ok, result = client.check_connection()
    if ok:
        print(f"Connected to {BASE_URL} - authenticated as user id {result.get('id')}")
    else:
        raise SystemExit(f"Connection/authentication failed (status code {result})")

    # Task 1: collect every post written by the instructor
    instructor_posts = collect_instructor_posts(client, INSTRUCTOR_ID)
    print(f"Collected {len(instructor_posts)} posts by instructor id {INSTRUCTOR_ID}")
