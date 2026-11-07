# PokeSeller

Card resale on Mercari, eBay and Instagram. **Operator mode.**

- The workbook in `pokeseller_data` (see `workspace.config`) is the source of
  record. Read it, don't restructure it. Make a dated backup copy before any
  script writes to it.
- `card_lister.py` drafts listings and strips Japanese characters.
  `config.json` holds listing settings such as `shipping_graded`.
  `import_sales.py` imports sales; eBay sales don't come in through it yet.
- Listing rules live in `listing-rules.toml`. The `mercari-listing` skill and
  the listing checker both read it.
- Use Claude in Chrome for Mercari (signed in there; photo uploads work).
  Never use the built-in browser for listings.
- Never type a price and never press List. The user prices and posts.
- Instagram deals that started on Mercari are "reverse and rebook": the
  Mercari row becomes Canceled, and a new Direct (IG) row is added with no
  fees.
- Cancellations use the status `Canceled`, spelled with one L.
