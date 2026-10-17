# Contributing

Thanks for taking a look! Nextfix is a small project, so the process is simple.

## Report a bug or suggest an idea

Open an [issue](https://github.com/the-neyro/nextfix/issues/new/choose) with the matching template. For bugs, the
steps to reproduce and the URL you audited (if it is public) help most.

## Change code

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q        # tests, no network needed
```

- One topic per pull request, with a short description of what changed and how you checked it.
- Add or adjust tests for new behaviour; all tests must pass (they also run on GitHub Actions).
- Keep modules small and names clear. Code comments and the user interface are in German, commit messages in
  English.
- No paid APIs and no scraping of Google results: Nextfix stays free to run.
