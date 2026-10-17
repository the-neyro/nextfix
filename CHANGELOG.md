# Changelog

All notable changes to Nextfix. Dates are in ISO format (YYYY-MM-DD).

## 0.1.0 – 2026-10-17

First public version. Nextfix is young: it has been tested on macOS against a handful of real websites and a
fictional demo site, not yet on Windows or Linux desktops.

### Added
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
- Tasks show their impact (high / medium / low) instead of “+4.2 points”, because no formula can predict what a fix
  does to rankings (#4).
- README rewritten in English (#1).

### Fixed
- Hidden (“intentional”) issues no longer show up in CSV export, crawl comparison and PDF examples (#2).
