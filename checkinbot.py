# INF601G - Advanced Programming in Python
# Kyle Horn
# Scheduled Check-In Bot

import json
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

# Where downloaded attachments and the collected.json summary get saved
ARTIFACT_DIR = "artifact"                                    # top-level output folder
FILES_DIR = os.path.join(ARTIFACT_DIR, "files")               # where attachments go
COLLECTED_JSON_PATH = os.path.join(ARTIFACT_DIR, "collected.json")  # the summary file


# Creates a class that will contain all API methods
class PracticeHubClient:
    # Runs when a new PracticeHubClient object is created
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")  # remove trailing slash so URLs join cleanly
        # Creates the Authorization header using the API token as a Bearer token
        self.headers = {"Authorization": f"Bearer {token}"}

    def check_connection(self):
        """Calls a simple endpoint to confirm the URL and token both work."""
        resp = requests.get(f"{self.base}/api/v1/me", headers=self.headers)  # "who am I?" call
        # A 200 response means the token was accepted
        if resp.ok:
            return True, resp.json()          # success: return (True, my user info)
        # Anything else means the URL or token is wrong
        return False, resp.status_code        # failure: return (False, the status code)

    def list_posts_page(self, author_id, limit, offset):
        """Gets one page of posts written by a specific author."""
        params = {"author": author_id, "limit": limit, "offset": offset}  # one "page" of results
        resp = requests.get(f"{self.base}/api/v1/posts", headers=self.headers, params=params)
        resp.raise_for_status()   # raises an exception if the request failed
        return resp.json()        # the list of posts on this page

    def get_all_posts_by_author(self, author_id):
        """Pages through every post by one author until there are no more pages left."""
        all_posts = []   # will collect posts from every page
        offset = 0       # how many posts to skip; starts at the beginning

        while True:  # keep looping until we explicitly break out below
            page = self.list_posts_page(author_id, PAGE_SIZE, offset)  # fetch one page

            # No posts came back, so we've reached the end
            if not page:
                break  # stop the loop, nothing left to fetch

            all_posts.extend(page)  # add this page's posts to the running total

            # If the page came back smaller than what we asked for,
            # that means this was the last page
            if len(page) < PAGE_SIZE:
                break  # stop the loop, this was the final (partial) page

            # Otherwise, move forward to request the next page
            offset += PAGE_SIZE  # skip past the posts we already have next time

        return all_posts  # every post by this author, across all pages

    def list_comments(self, post_id):
        """Gets every comment on a post (the API returns them all in one response)."""
        resp = requests.get(f"{self.base}/api/v1/posts/{post_id}/comments", headers=self.headers)
        resp.raise_for_status()   # raises an exception if the request failed
        return resp.json()        # the full list of comments on this post

    def post_comment(self, post_id, body):
        """Posts a comment/reply on a post.

        Returns one of:
          ("ok", comment_json)   - the reply was accepted
          ("closed", None)       - the server returned 423: the check-in window is closed
          ("error", detail)      - any other failure
        """
        resp = requests.post(                    # send the reply to the server
            f"{self.base}/api/v1/posts/{post_id}/comments",
            headers=self.headers,                # include our auth token
            json={"body": body},                 # the comment text itself
        )

        if resp.status_code == 423:
            return "closed", None                # window is closed - not a crash, just a status

        if not resp.ok:
            return "error", f"HTTP {resp.status_code}: {resp.text}"  # some other failure

        return "ok", resp.json()                  # success - return the created comment

    def download_attachment(self, download_url, destination_path):
        """Downloads one attachment's file bytes and saves them to destination_path."""
        # The API may return a full URL or just a path - handle both
        if download_url.startswith("http"):
            url = download_url                     # already a complete URL
        else:
            url = f"{self.base}{download_url}"      # relative path, so add the base URL

        resp = requests.get(url, headers=self.headers, stream=True)  # stream = download in chunks
        resp.raise_for_status()   # raises an exception if the download failed

        with open(destination_path, "wb") as f:      # open the destination file for writing bytes
            for chunk in resp.iter_content(chunk_size=8192):  # read the response a little at a time
                f.write(chunk)                        # write each chunk to disk


def collect_instructor_posts(client, instructor_id):
    """Builds a clean list of dictionaries with everything Task 1 needs to save."""
    posts = client.get_all_posts_by_author(instructor_id)  # every post by the instructor, all pages

    collected = []             # will hold the cleaned-up post dictionaries
    for post in posts:         # go through each raw post from the API
        collected.append({
            "id": post["id"],                              # unique post id
            "title": post["title"],                        # the post's title
            "body": post["body"],                          # the FULL body text, not a preview
            "tags": post["tags"],                          # list of tags on the post
            "created_at": post["created_at"],              # when it was created
            "updated_at": post["updated_at"],              # when it was last edited
            "attachments": post.get("attachments", []),    # list of attached files (may be empty)
        })
    return collected           # the finished list, ready to save or filter


def is_checkin(post):
    """A post counts as a check-in if 'check-in' appears anywhere in its title."""
    return "check-in" in post["title"].lower()   # lowercase makes the match case-insensitive


def filter_checkin_posts(posts):
    """Returns only the instructor posts that are check-ins.

    This only ever looks at the instructor posts we already collected
    (see collect_instructor_posts), so it can never match another
    student's post - only the title text decides which of THOSE are check-ins.
    """
    return [post for post in posts if is_checkin(post)]   # keep only posts where is_checkin is True


def has_already_replied(client, post_id, my_user_id):
    """Checks whether my_user_id already left a comment on this post."""
    comments = client.list_comments(post_id)   # every comment currently on this post
    return any(comment["author_id"] == my_user_id for comment in comments)  # True if any match my id


def reply_to_checkins(client, checkin_posts, my_user_id):
    """Replies to each open check-in exactly once. Returns a list of result dicts."""
    results = []   # will hold one outcome dict per check-in post

    for post in checkin_posts:   # go through each detected check-in
        try:
            # Step 8's duplicate check: never post a second reply to the same check-in
            if has_already_replied(client, post["id"], my_user_id):
                results.append({"post_id": post["id"], "title": post["title"], "outcome": "skipped_duplicate"})
                continue   # move on to the next post without posting anything

            reply_body = f'Checking in for "{post["title"]}"'  # the comment text we will post
            # We attempt exactly once - a 423 means the window is closed for this run,
            # and the next scheduled run (not a retry loop here) is what tries again
            outcome, detail = client.post_comment(post["id"], reply_body)  # attempt the reply

            if outcome == "ok":
                results.append({"post_id": post["id"], "title": post["title"], "outcome": "replied"})
            elif outcome == "closed":
                results.append({"post_id": post["id"], "title": post["title"], "outcome": "window_closed"})
            else:
                results.append({"post_id": post["id"], "title": post["title"], "outcome": "error", "detail": detail})
        except requests.RequestException as e:
            # A network problem on THIS post (timeout, connection drop, etc.) must not
            # stop the loop - other check-ins may still be inside their reply window
            results.append({"post_id": post["id"], "title": post["title"], "outcome": "error", "detail": str(e)})

    return results   # one outcome per check-in post, for printing/logging


def sanitize_filename(filename):
    """Strips any directory parts so a malicious filename can't write outside artifact/files/."""
    return os.path.basename(filename.replace("\\", "/"))  # normalize slashes, then keep only the name


def download_all_attachments(client, posts):
    """Downloads every attachment for every post. Returns (success_count, failures)."""
    # Make sure the destination folder exists before we try to save anything into it
    os.makedirs(FILES_DIR, exist_ok=True)

    success_count = 0   # counts how many attachments downloaded successfully
    failures = []        # collects details about any that failed

    for post in posts:                                  # go through every collected post
        for attachment in post.get("attachments", []):  # go through every attachment on that post
            filename = attachment.get("filename", f"attachment_{attachment.get('id')}")
            # Strip any directory parts before the filename ever touches a file path
            clean_filename = sanitize_filename(filename)

            # Prefix with post id + attachment id so two attachments that happen to
            # share the same filename never overwrite each other
            safe_name = f"{post['id']}_{attachment['id']}_{clean_filename}"  # unique name on disk
            destination_path = os.path.join(FILES_DIR, safe_name)            # real path to save to
            # Path relative to the artifact/ folder, so collected.json stays portable
            relative_path = os.path.join("files", safe_name)                 # path stored in the JSON

            try:
                client.download_attachment(attachment["download_url"], destination_path)  # do the download
                # Record where this attachment landed so collected.json can point to it
                attachment["local_path"] = relative_path   # note where the file ended up
                attachment["downloaded"] = True             # mark this attachment as successful
                success_count += 1                          # bump the success counter
            except (requests.RequestException, OSError) as e:
                # Record the failure instead of letting the whole program crash,
                # and instead of silently pretending everything worked
                attachment["local_path"] = None             # no file exists for this attachment
                attachment["downloaded"] = False             # mark this attachment as failed
                failures.append({
                    "post_id": post["id"],                   # which post this attachment was on
                    "attachment_id": attachment.get("id"),   # which attachment failed
                    "filename": filename,                    # its original filename
                    "error": str(e),                         # what went wrong
                })

    return success_count, failures   # summary for the caller to print/log


def save_collected_json(posts, instructor_id):
    """Writes the full instructor-post collection to artifact/collected.json."""
    os.makedirs(ARTIFACT_DIR, exist_ok=True)   # make sure artifact/ exists before writing into it

    data = {
        "instructor_id": instructor_id,   # whose posts these are
        "post_count": len(posts),         # quick sanity-check count
        "posts": posts,                    # the full list of collected post dictionaries
    }

    with open(COLLECTED_JSON_PATH, "w", encoding="utf-8") as f:  # open/overwrite the JSON file
        # indent=2 keeps it human-readable; ensure_ascii=False keeps text as-typed
        json.dump(data, f, indent=2, ensure_ascii=False)          # write the data as JSON


# Checks if this file is being run directly instead of being imported
if __name__ == "__main__":
    # Stops the program early with a clear message if a required setting is missing
    if not BASE_URL:
        raise SystemExit("PRACTICE_API_URL is not set.")     # can't build any URL without this
    if not TOKEN:
        raise SystemExit("PRACTICE_API_TOKEN is not set.")   # can't authenticate without this
    if not INSTRUCTOR_ID:
        raise SystemExit("INSTRUCTOR_ID is not set.")        # can't filter posts without this

    client = PracticeHubClient(BASE_URL, TOKEN)   # build the API client using our settings

    # Simple test: confirm we can authenticate without ever printing the token
    ok, result = client.check_connection()          # try the "who am I?" call
    if ok:
        print(f"Connected to {BASE_URL} - authenticated as user id {result.get('id')}")
    else:
        raise SystemExit(f"Connection/authentication failed (status code {result})")

    # Fetch the instructor's posts once - both Task 1 and Task 2 need this list.
    # If this fails there is nothing else we can do this run, so we exit cleanly
    # with a message instead of letting a raw traceback come out of pagination.
    try:
        instructor_posts = collect_instructor_posts(client, INSTRUCTOR_ID)  # all instructor posts
    except requests.RequestException as e:
        raise SystemExit(f"Failed to fetch instructor posts: {e}")   # exit cleanly, no traceback
    print(f"Collected {len(instructor_posts)} posts by instructor id {INSTRUCTOR_ID}")

    # Task 2 runs FIRST and is wrapped on its own: replies are time-sensitive
    # (the 423 window), while downloading/saving below is not. This way a slow
    # or failing download can never cost us a reply we could have gotten in.
    checkin_posts = filter_checkin_posts(instructor_posts)   # only the check-in posts
    print(f"Found {len(checkin_posts)} check-in post(s):")
    for post in checkin_posts:
        print(f"  - post {post['id']}: \"{post['title']}\"")   # list each check-in found

    my_user_id = result.get("id")   # my own user id, used to spot my own past replies
    try:
        reply_results = reply_to_checkins(client, checkin_posts, my_user_id)  # do the actual replying
    except requests.RequestException as e:
        print(f"ERROR: could not process check-in replies this run: {e}")  # log it, don't crash
        reply_results = []   # nothing to report below

    for r in reply_results:                       # print a line explaining what happened per post
        if r["outcome"] == "replied":
            print(f"  - post {r['post_id']} (\"{r['title']}\"): replied")
        elif r["outcome"] == "skipped_duplicate":
            print(f"  - post {r['post_id']} (\"{r['title']}\"): already replied, skipped")
        elif r["outcome"] == "window_closed":
            print(f"  - post {r['post_id']} (\"{r['title']}\"): reply window closed (423), skipped")
        else:
            print(f"  - post {r['post_id']} (\"{r['title']}\"): ERROR - {r['detail']}")

    # Task 1: download every attachment and save collected.json.
    # Not time-sensitive, so it runs after replies and is isolated in its own
    # try/except - a problem here should never look like Task 2 failed.
    try:
        success_count, failures = download_all_attachments(client, instructor_posts)  # get all files
        print(f"Downloaded {success_count} attachment(s) to {FILES_DIR}/")

        if failures:
            print(f"WARNING: {len(failures)} attachment(s) failed to download:")
            for failure in failures:                # explain each failed download
                print(f"  - post {failure['post_id']}, attachment {failure['attachment_id']} "
                      f"({failure['filename']}): {failure['error']}")

        save_collected_json(instructor_posts, INSTRUCTOR_ID)   # write artifact/collected.json
        print(f"Saved collection to {COLLECTED_JSON_PATH}")
    except (requests.RequestException, OSError) as e:
        print(f"ERROR: could not finish collecting attachments/JSON this run: {e}")  # log, don't crash
