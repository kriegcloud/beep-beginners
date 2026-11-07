---
name: morning-job-hunt
description: >
  Run the morning job hunt: find postings from the last day that fit the
  user's target roles, tailor a copy of their base resume for each good one,
  save PDFs, and update the tracker. Use when the user says "do my morning job
  hunt", "usual morning job search", "find me jobs", or "tailor my resume for
  this posting".
---

# Morning job hunt

The `job-hunt/AGENTS.md` file in the workspace holds the user's search
criteria: target roles, locations, sites, the base resume's path, and what
to skip. Read it first. `workspace.config` gives the output folder
(`resumes_out`) and the tracker file (`job_tracker`).

## Steps

1. **Search** each site in the criteria for postings updated in the last day.
   On Built In, use the `daysSinceUpdated=1` filter.
2. **Check freshness.** Open each posting and read its posted date (for
   example the `datePosted` field in the page data). Skip anything older than
   the criteria allow, and anything already in the tracker.
3. **Pick** the postings that match the target roles. Say in one line why
   each one fits.
4. **Tailor** a copy of the base resume for each pick. Never edit the base.
   Rewrite the summary and the first skills line for the posting, and reorder
   bullets so the most relevant come first. Never invent experience. Use
   `python-docx` through `uv run --with python-docx`.
5. **Save** each copy as a PDF in `<resumes_out>/<YYYY-MM-DD>/`, named
   `<Company> - <Role>.pdf`. On Windows, Word does the PDF conversion.
6. **Track.** Add one row per posting to the tracker CSV: date, company,
   role, link, posted date, fit note, resume file, status `tailored`.
7. **Report** in a short list: company, role, why it fits, and where the
   resume is. Ask before applying to anything.

## If the PC was off

This runs when the user asks, so a missed morning doesn't break anything. If
they ask for "this morning's" hunt later in the day, run it as normal.
