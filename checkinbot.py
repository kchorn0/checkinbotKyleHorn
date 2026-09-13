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

# Where downloaded attachments get saved
ARTIFACT_DIR = "artifact"
FILES_DIR = os.path.join(ARTIFACT_DIR, "files")


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

    def download_attachment(self, download_url, destination_path):
        """Downloads one attachment's file bytes and saves them to destination_path."""
        # The API may return a full URL or just a path - handle both
        if download_url.startswith("http"):
            url = download_url
        else:
            url = f"{self.base}{download_url}"

        resp = requests.get(url, headers=self.headers, stream=True)
        resp.raise_for_status()

        with open(destination_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)


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


def download_all_attachments(client, posts):
    """Downloads every attachment for every post. Returns (success_count, failures)."""
    # Make sure the destination folder exists before we try to save anything into it
    os.makedirs(FILES_DIR, exist_ok=True)

    success_count = 0
    failures = []

    for post in posts:
        for attachment in post.get("attachments", []):
            filename = attachment.get("filename", f"attachment_{attachment.get('id')}")

            # Prefix with post id + attachment id so two attachments that happen to
            # share the same filename never overwrite each other
            safe_name = f"{post['id']}_{attachment['id']}_{filename}"
            destination_path = os.path.join(FILES_DIR, safe_name)

            try:
                client.download_attachment(attachment["download_url"], destination_path)
                success_count += 1
            except (requests.RequestException, OSError) as e:
                # Record the failure instead of letting the whole program crash,
                # and instead of silently pretending everything worked
                failures.append({
                    "post_id": post["id"],
                    "attachment_id": attachment.get("id"),
                    "filename": filename,
                    "error": str(e),
                })

    return success_count, failures


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

    # Task 1: download every attachment from those posts
    success_count, failures = download_all_attachments(client, instructor_posts)
    print(f"Downloaded {success_count} attachment(s) to {FILES_DIR}/")

    if failures:
        print(f"WARNING: {len(failures)} attachment(s) failed to download:")
        for failure in failures:
            print(f"  - post {failure['post_id']}, attachment {failure['attachment_id']} "
                  f"({failure['filename']}): {failure['error']}")
