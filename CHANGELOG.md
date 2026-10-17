# Changelog

All notable changes to Nextfix. Dates are in ISO format (YYYY-MM-DD).

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
