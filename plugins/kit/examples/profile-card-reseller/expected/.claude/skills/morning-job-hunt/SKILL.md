---
name: morning-job-hunt
description: >
  Run the morning job hunt: find postings from the last day that fit the user's target roles, tailor a copy of their base resume for each good one, save PDFs, and update the tracker. Use when the user says "do my morning job hunt", "usual morning job search", "find me jobs", or "tailor my resume for this posting".
---

# Morning job hunt

The search criteria live in this skill; `workspace.config` gives the output folder (`resumes_out`), the tracker file (`job_tracker`) and the base resume (`base_resume`).

## Criteria

- Roles: entry-level data analyst, financial analyst, BI analyst. The exact target is still open, so include all three and say which fits best.
- Location and remote preference: ask the user the first time, then write the answer here.
- Posted within the last day. Check the posting's own date, not the list's.
- Entry level: skip roles that ask for several years of experience.

## Steps

1. **Search** each job board the user names for postings updated in the last day.
2. **Check freshness.** Open each posting and read its posted date. Skip anything older than a day, and anything already in the tracker.
3. **Pick** the postings that match the target roles. Say in one line why each one fits.
4. **Tailor** a copy of the base resume for each pick. Never edit the base. Rewrite the summary and the first skills line for the posting, and reorder bullets so the most relevant come first. Never invent experience. Use `python-docx` through `uv run --with python-docx`.
5. **Save** each copy as a PDF in `<resumes_out>/<YYYY-MM-DD>/`, named `<Company> - <Role>.pdf`. On Windows, Word does the PDF conversion.
6. **Track.** Add one row per posting to the tracker CSV: date, company, role, link, posted date, fit note, resume file, status `tailored`.
7. **Report** in a short list: company, role, why it fits, and where the resume is. Ask before applying to anything.

This runs when the user asks, so a missed morning doesn't break anything.
