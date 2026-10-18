# Changelog

All notable changes to Nextfix. Dates are in ISO format (YYYY-MM-DD).

## Unreleased

### Changed
- Honest scoring, checked against Google Search Central and web.dev: “Little text” now weighs like a warning, not
  like an error (Google does not rank by length), and legal pages (imprint, privacy) no longer count. H1 equal to
  title and low text/HTML ratio are notices. Duplicate content, duplicate meta descriptions and meta refresh are
  warnings. Slow server response starts at 1.8 s (web.dev TTFB), not 1 s, and is a warning.
- Structured data: Organization and Person no longer have required fields (Google has none); Review needs
  reviewRating, JobPosting needs jobLocation or jobLocationType.
- Texts corrected: FAQ rich results are gone since May 2026, llms.txt is not used by Google, lang matters for
  screen readers rather than Google, sitemaps are optional for small sites, lab vs. field data for Core Web Vitals.
- Demo website: before 64.0 (was 48.7), after 90.6, tasks 8 → 3.
- “Blocked for Google” now reads robots.txt the way Googlebot does (not with Nextfix's own user agent) and explains
  that robots.txt only blocks fetching, while noindex keeps a page out of results.
- The load-time sample skips noindex pages; AI checks ignore noindex pages.
- ETag counts like Last-Modified; two identical canonical tags are no longer “multiple canonicals”.
- hreflang follows Google: two-letter language (ISO 639-1), region ISO 3166-1 alpha-2 (es-419 and en-UK are invalid).
- Google-Extended moved to the training crawlers (it does not affect Google Search).
- robots.txt: real format errors (missing colon, rule before User-agent) stay errors; unknown fields and the ignored
  `noindex:` are a new warning “Unknown fields in robots.txt”. Now 107 checks.
- New notices: render-blocking stylesheets (3+ files or 100 KB+ in the head), short cache lifetimes for JS/CSS
  (under 7 days), images without width and height (layout shift risk). Now 110 checks.
- Targets of canonical, hreflang and llms.txt links that no page links to are checked with HEAD after the crawl
  (max. 200). Canonicals or hreflang pointing to a 404 that is linked nowhere were missed before. The test bench
  now has no known gaps left.

### Added
- Test bench (“Prüfstand”): `python -m scripts.pruefstand` serves seven local test websites with a known truth for
  every check (must fire / must not fire, edge cases like 70/71 characters or 199/200 words), crawls them with the
  real Nextfix code into its own database and prints a table: correct, false alarms, misses, not testable locally.
  Runs in CI (`pytest --langsam`). `--export <folder>` writes the cases as static files for a second opinion.

### Fixed
- Mobile CLS was too good: Chrome flags layout shifts in the first ~500 ms as “recent input” under touch emulation,
  so they were dropped.
- robots.txt starting with a byte order mark (BOM): the first `User-agent` group was ignored, so its rules did not
  apply; same file was reported as broken. llms.txt with a BOM no longer counts as badly formatted.
- `<meta name="robots" content="none">` and `<meta name="googlebot" content="noindex">` now count as noindex.
- “H1 equals title” also matches when only the case of umlauts differs.
- Structured data follows Google: Article types have no required fields; Product needs `offers`, `review` or
  `aggregateRating` besides `name`.
- No “missing doctype” when an HTML comment comes first; no “obsolete plugin” for a file name containing “java”.
- “Internal links to redirects” only lists redirects that an internal link points to, not every step of a chain.
- hreflang: a target page without any hreflang now counts as missing return link.

## 0.2.2 – 2026-10-18

### Fixed
- Umlaut domains: links written as punycode (`xn--…`) now count as internal, so the crawl no longer stops at the
  home page of a domain like `bäckerei-müller.de`. Default ports (`:443`, `:80`) no longer make a link external (#23).
- Character sets: pages without a charset in the HTTP header are decoded with their `<meta charset>`, else UTF-8,
  else windows-1252. Older ISO-8859-1 sites no longer show broken umlauts in titles and word counts (#23).
- robots.txt is read like Google does: `*` and `$` wildcards, the longest rule wins and Allow wins ties (e.g.
  WordPress `Allow: /wp-admin/admin-ajax.php`). Also used for the “AI crawlers blocked” check (#23).
- Big files: PDFs, videos and error pages linked from a site are no longer downloaded; HTML is read up to 5 MB
  while the real size still counts for “HTML too large” (#23).

## 0.2.1 – 2026-10-18

### Fixed
- Pages with noindex no longer count for missing or duplicate titles and descriptions, headings, text ratio and
  duplicate content. Google does not show these pages, so they only produced false alarms (e.g. a clickable demo
  on noindex counted as 21 duplicate titles and 54 missing descriptions). Image alt texts still count (#21).

## 0.2.0 – 2026-10-17

Easier to install and to act on: the installer fetches the latest release and prints the Claude Code command,
Windows gets a double-click start file, and the ten most common tasks explain the fix in plain language with
WordPress hints. Windows is still not officially supported: installer and start file work there, the tests do not
pass reliably yet.

### Added
- Plain-language fix guides for the ten most common tasks (thin content, page titles, descriptions, image text,
  pages not found, broken links, sitemap) and a new `wordpress` hint per check (Yoast, Rank Math, block editor),
  shown on the issue page, in the task list (API and MCP `was_jetzt_tun`) and in the PDF (#19).
- Double-click start file for Windows, `Nextfix starten.bat`: first start runs the installer, then it starts
  Nextfix and opens the browser; checked automatically on Windows (#18).
- The installer prints a ready-made `claude mcp add` command with the real install path (#17).
- `ROADMAP.md`: what is planned and what is deliberately not planned (#16).

### Changed
- The one-line installer checks out the newest release tag instead of `main`; `NEXTFIX_BRANCH=main` (or any
  branch) for the development version. Running it again updates an existing install (#17).
- README explains why the MCP server is called `seo-tool` and keeps that name (#17).

## 0.1.0 – 2026-10-17

First public version. Nextfix is young: it has been used on macOS against a handful of real websites and a
fictional demo site. The tests run automatically on Linux and macOS; on Windows the installer works, but one test
still fails there.

### Added
- One-line install for macOS/Linux (`scripts/install.sh`) and Windows (`scripts/install.ps1`), checked
  automatically on all three systems (#13).
- Double-click start file for macOS, `Nextfix starten.command` (#9).
- MCP tool `was_jetzt_tun` and API endpoint `GET /api/crawls/{id}/aufgaben` for the “what to do now” task list,
  51 MCP tools in total (#12).
- Demo website variant with the first tasks fixed and `scripts/vorher_nachher.py`, which audits both: site health
  48.7 before, 90.6 after (#11).
- Changelog, contributing guide, issue templates and tests on GitHub Actions (#10).
- Domain authority via Open PageRank: value 0–10 per project and competitor, cached for 30 days, MCP tool
  `autoritaet_abrufen` (#7).
- Hint when a site looks like a JavaScript app that was crawled without rendering (#6).
- Optional JavaScript rendering in the crawler with Chromium, check for content that only appears with JavaScript
  (#5).
- Page speed (LCP, CLS, TBT on mobile) counts towards site health, optional measurement after every crawl (#3).
- Initial release: crawler, 106 checks in 8 areas, site health 0–100, “what to do now” task list, issue detail
  pages, history, CSV and PDF report, page speed in the lab, rankings from Google Search Console and Bing, keyword
  research, page optimization with page and AI score, “intentional” flag to hide deliberate cases, web UI, REST API
  and MCP server with 50 tools.

### Changed
- Title suggestions follow the title check on the website: keyword spelling from the title, filler parts like
  “Home” removed, brand kept, never empty parts, always a shortened suggestion for long titles (#8).
- Tasks show their impact (high / medium / low) instead of “+4.2 points”, because no formula can predict what a fix
  does to rankings (#4).
- README rewritten in English (#1).

### Fixed
- Pages with noindex no longer count as thin content, matching the suggested fix “or remove them from the
  index” (#14).
- Hidden (“intentional”) issues no longer show up in CSV export, crawl comparison and PDF examples (#2).
