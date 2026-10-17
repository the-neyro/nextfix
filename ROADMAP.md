# Roadmap

What comes next, and what Nextfix deliberately will not do. No dates: Nextfix is a side project, and the order can
change when real users report problems. Ideas and bugs: [issues](https://github.com/the-neyro/nextfix/issues).

## Planned

- **Windows, officially.** The installer already runs on Windows; the tests do not pass there reliably yet (one
  background-import test times out, and the whole run is much slower). Once they are green every time, Windows
  becomes a supported platform.
- **Plain-language fix guides.** Every task explains in a few steps, without jargon, how to fix it yourself,
  including where the field is in WordPress (Yoast, Rank Math).
- **Easier Claude setup.** The installer prints the ready-made `claude mcp add` command with your real path.
- **Install from releases.** The one-line installer fetches the latest release instead of the development branch.
- **Referring domains from open data.** A rough count of linking domains from the Common Crawl web graph, if it
  works without paid APIs and without huge downloads for every user.

## Deliberately not planned

- **Competitor rankings and keyword positions of other sites.** That data only comes from scraping Google (against
  its terms of service) or from paid databases. Nextfix uses Search Console and Bing, which you already own.
- **A backlink database.** Building one means crawling the whole web; renting one costs money every month. Domain
  authority comes from Open PageRank instead.
- **A cloud version.** Nextfix runs on your computer, your data stays there, and it costs nothing to run.
- **Tracking or telemetry.** Nextfix sends nothing about you or your projects anywhere. The only outside requests
  are the websites you audit, search suggestions from Google and Bing during keyword research, and the free
  services you set up yourself (Search Console, Bing Webmaster Tools, Open PageRank).
