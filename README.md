# checkinbotKyleHorn

## What this project does

This project is a scheduled bot that talks to the Practice Hub REST API on
my behalf. GitHub Actions runs it automatically on a cron schedule.

Each run does two jobs:

1. **Collect** every post authored by the instructor (paging through all
   results), saving the title, full body, tags, timestamps, and post id for
   each one into `artifact/collected.json`, and downloading every attached
   file into `artifact/files/`.
2. **Reply to check-ins** — instructor posts whose title contains
   "check-in" (case-insensitive) — by posting a comment, while skipping any
   check-in it has already replied to and handling a closed reply window
   (HTTP 423) without crashing.

Data source used: **Practice Hub REST API**.

## Requirements

- Python 3

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## How to run (in terminal run)

```bash
python checkinbot.py
```

This will:
1. Connect to the Practice Hub API using `PRACTICE_API_URL` and
   `PRACTICE_API_TOKEN`.
2. Page through every post and keep only the ones authored by
   `INSTRUCTOR_ID`.
3. Save those posts to `artifact/collected.json` and download every
   attachment into `artifact/files/`.
4. Find any instructor posts that are check-ins and reply to the ones that
   haven't been replied to yet (skipping ones already replied to, and
   handling a closed reply window gracefully).

Locally, these environment variables must be set before running:

```bash
$env:PRACTICE_API_URL = "https://practice.fhsucyber.com"
$env:PRACTICE_API_TOKEN = "your-token-here"
$env:INSTRUCTOR_ID = "7"
```

In GitHub Actions, the same three values are supplied as repository
secrets/variables (`PRACTICE_API_TOKEN`, `PRACTICE_API_URL` as secrets,
`INSTRUCTOR_ID` as a variable) and the workflow in
`.github/workflows/checkinbot.yml` runs the program on a schedule, then
commits any changes to `artifact/` back into the repo.

## Help

Common problems and fixes:

- **`PRACTICE_API_URL is not set` / `PRACTICE_API_TOKEN is not set` /
  `INSTRUCTOR_ID is not set`** — one of the required environment variables
  is missing from your terminal session (locally) or from the repo's
  secrets/variables (in GitHub Actions).
- **`Connection/authentication failed`** — the token or URL is wrong.
  Double-check the values without printing the token itself anywhere.
- **HTTP 423 on a reply** — this is expected behavior, not a bug. It means
  the check-in's reply window is currently closed; the program logs it and
  moves on without crashing. The next scheduled run will try again while
  the window may still be open.
- **`Collected 0 posts` / `Found 0 check-in post(s)`** — this just means
  the instructor hasn't posted anything (or any check-ins) yet.

## Authors

Contributors names and contact info

Kyle Horn (kchorn@mail.fhsu.edu)

## AI Usage
What AI did: I used Claude Code to scaffold the project structure and write the first draft of each function in checkinbot.py step by step — the paginated post-fetching loop, the attachment downloader, the check-in title matcher, the duplicate-reply check, the 423 handling, and the GitHub Actions workflow YAML. Claude also looked up the Practice Hub API's actual pagination parameters and comment endpoint from its OpenAPI schema before writing code against them, rather than guessing.

What I did: I directed the whole build one step at a time instead of asking for the finished bot up front — deciding the order (connect → collect → download → detect → dedupe → reply → review → automate), reviewing each piece before moving on, and running a full requirements check against the assignment before touching GitHub Actions. I also set up the actual repo secrets/variables in GitHub, ran the manual workflow trigger myself, and read the run output to confirm it worked.

What I changed: After Claude's own review pass flagged that attachment filenames weren't sanitized (a file named with ../ could theoretically write outside artifact/files/), I asked for that fix specifically rather than accepting the original download code as final. I also trimmed and reworded parts of the generated README to match my own preferred format and removed sections I felt were unnecessary.
