# Roadmap

What comes next, and what Nextfix deliberately will not do. No dates: Nextfix is a side project, and the order can
change when real users report problems. Ideas and bugs: [issues](https://github.com/the-neyro/nextfix/issues).

## Planned

- **Windows, officially.** Installer and the double-click start file already work on Windows and are checked
  automatically; the tests do not pass there reliably yet (one background-import test times out, and the whole run
  is much slower). Once they are green every time, Windows becomes a supported platform.
- **Plain-language guides for the remaining tasks.** The ten most common tasks already have them (see below); the
  other checks still explain the fix in shorter, more technical words.
- **Referring domains from open data.** A rough count of linking domains from the Common Crawl web graph, if it
  works without paid APIs and without huge downloads for every user.

## Done

- **Plain-language fix guides with WordPress hints** for the ten most common tasks: what to do without jargon, and
  where the field is in WordPress (Yoast, Rank Math, block editor). Shown on the issue page, in the task list and in
  the PDF (0.2.0, #19).
- **Easier Claude setup.** The installer prints the ready-made `claude mcp add` command with your real path
  (0.2.0, #17).
- **Install from releases.** The one-line installer checks out the newest release; `NEXTFIX_BRANCH=main` for the
  development version (0.2.0, #17).
- **Double-click start on Windows**, `Nextfix starten.bat`, like `Nextfix starten.command` on the Mac (0.2.0, #18).

## Deliberately not planned

- **Competitor rankings and keyword positions of other sites.** That data only comes from scraping Google (against
  its terms of service) or from paid databases. Nextfix uses Search Console and Bing, which you already own.
- **A backlink database.** Building one means crawling the whole web; renting one costs money every month. Domain
  authority comes from Open PageRank instead.
- **A cloud version.** Nextfix runs on your computer, your data stays there, and it costs nothing to run.
- **Tracking or telemetry.** Nextfix sends nothing about you or your projects anywhere. The only outside requests
  are the websites you audit, search suggestions from Google and Bing during keyword research, and the free
  services you set up yourself (Search Console, Bing Webmaster Tools, Open PageRank).
