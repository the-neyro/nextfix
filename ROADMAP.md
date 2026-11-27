# Roadmap

What comes next, and what Nextfix deliberately will not do. No dates: Nextfix is a side project, and the order can
change when real users report problems. Ideas and bugs: [issues](https://github.com/the-neyro/nextfix/issues).

## Planned

Work in this order. Each stage has a checkable outcome before the next one expands the scope.

### 1. Finish the release candidate

- Review and integrate the follow-up fixes for empty compressed HTTP responses, organization-markup rechecks,
  and the slow-response task text into [PR #38](https://github.com/the-neyro/nextfix/pull/38).
- Check dependencies against published advisories and decide how release artifacts will be verified.
- Run the full tests, local test bench, and clean-install/update checks on the final release commit.
- **Ready when:** all seven CI jobs pass on that commit; installation and updating an existing project preserve
  its data; the maintainer approves the merge and release. The published release remains 0.2.3 until then.
- **Windows:** tests and installer passed on the PR's November 5 commit. Keep CI coverage and add a manual
  first-launch/update check before changing the supported-platform claim.

### 2. Make the audit → fix → recheck workflow dependable

- Exercise three or more consecutive audits: a finding, an interrupted or narrower crawl, and another recheck.
  Ensure unresolved findings remain visible until their original URLs are checked again or deliberately hidden.
- Test changed crawl limits, excluded checks, rendering modes, redirects, and missing resource measurements.
- Give users a clear next action for findings that were not rechecked, with the affected URLs and reason.
- **Ready when:** UI, REST, and MCP agree on current, confirmed-fixed, and unverified findings; skipped coverage
  cannot make the task list imply that the work is complete. Add regression cases to the existing test bench.

### 3. Validate prioritization and finish practical fix guides

- Validate a real Search Console import on an owned property: URL matching, date range, missing versus zero
  data, and partial coverage. Check the resulting task order in the browser against the imported rows.
- Extend plain-language guides to the most frequent remaining tasks, using beta findings to choose the order.
  Include the location of the CMS setting where it is known, plus how to verify the fix.
- **Ready when:** the first three recommended actions have evidence, affected pages, a clear instruction, and
  a repeatable check; the interface shows the source and period of traffic data.

### 4. Run a controlled beta and update the product website

- Audit 10–20 approved websites sequentially, covering small static sites, WordPress, shops, and JavaScript sites.
- Manually check each site's top three recommendations. Record false alarms, missed issues, unclear instructions,
  crawl failures, and time needed to complete one fix. Keep site-specific evidence out of the public repository.
- Fix reproducible blockers and turn them into local fixtures. Refresh demo numbers, screenshots, and website
  claims from the accepted release rather than copying old counts.
- **Ready when:** every top recommendation in the beta sample has been reviewed, no known release blockers
  remain, and another person can install the app, complete one task, and verify it without developer help.

### 5. Expand from observed demand

- Choose the next module from beta feedback: clearer task guidance, better own-site search data, or competitor
  content gaps from crawls. Keep missing data explicit; do not invent traffic or ranking estimates.
- **Referring domains from open data:** consider a separate Common Crawl feasibility experiment after approval.
  Establish coverage, freshness, local resource limits, and a useful no-data state before adding it to the app.
- **English UI and website:** after the core workflow passes the beta. Keep new UI text centralized meanwhile.
- **Ready when:** one scoped proposal has a user problem, data source, cost/resource limit, and acceptance case.
  Implement it as a separate feature branch.

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
