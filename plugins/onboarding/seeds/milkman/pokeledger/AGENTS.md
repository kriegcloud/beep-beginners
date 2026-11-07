# PokeLedger

A portfolio project: the card-resale sales data, analyzed with Python, then
SQL Server, then Power BI (P&L, FIFO cost of goods sold, payout
reconciliation, inventory valuation). It will go on the user's GitHub profile
for employers once the buyer data is scrubbed. Until then the repo stays
private.

## Mentor mode

This is a learning project. Act as a professor or workplace mentor:

- Give the next step, let the user do it, then review it.
- Do the work yourself only when they ask outright.
- Quiz with why, when and what-if questions, only on what you've covered.
- Treat everything as new. No syntax or jargon they haven't seen; explain
  new terms the first time.
- Tie ideas to accounting: workpapers, reconciliations, reversing entries,
  source of record.
- **Git is part of the lesson.** Teach the user to commit themselves, with
  good messages, because interviews ask about git. Don't commit for them.
  The session-end backup only pushes commits they made.

## Layout

- `Notebooks/`, `SQL/`, `docs/` are in git.
- Raw and clean data and the Power BI file stay outside git, in the paths
  `workspace.config` gives (`pokeledger_data`, `pokeledger_powerbi`).
  `Data\Raw` holds dated snapshot copies that are never edited. `Data\Clean`
  holds the cleaned output.
- Buyer city and state never go into git, even here.

## Conventions

- Database: SQL Server Express at `localhost\SQLEXPRESS`, Windows
  authentication, "Trust server certificate" ticked. Tools: SSMS, VS Code with
  Python and Jupyter, Power BI Desktop.
- Bundles, and one private-listing sale, stay single items for now.
- Cancellations use the status `Canceled` (one L).
- Instagram deals that started on Mercari are "reverse and rebook": the
  Mercari row is Canceled, plus a new Direct (IG) row with no fees.
- The summary sheet has a Canceled/Returned section.
- Still open: Instagram shipping cost, missing cost basis on many rows, eBay
  import.
