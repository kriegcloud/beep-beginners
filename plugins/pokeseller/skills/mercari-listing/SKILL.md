---
name: mercari-listing
description: >
  Draft a Mercari listing for a trading card and fill in the Mercari form in
  Chrome, without publishing it. Use when the user says "list this card",
  "make a Mercari listing for <card>", "draft listings for the cards in Ready",
  or asks to check a listing draft.
---

# Mercari listing

The user sets the price and presses List. You never type a price and never
press List, Publish or Save changes on a live listing.

## Where things are

- Rules: `listing-rules.toml` in the PokeSeller folder. Read it first. The
  example in this plugin (`${CLAUDE_PLUGIN_ROOT}/listing-rules.example.toml`)
  shows every field.
- Photos: the `card_inbox_ready` path in `workspace.config`, one folder per
  card.
- Drafts: `PokeSeller/listings/<date>-<card>.md`. If the folder has a lister
  script (such as `card_lister.py`), use it to make the draft, then save its
  output as a draft file.

## Steps

1. **Draft.** Write the draft with `Title:`, `Condition:`, `Price:` (left
   empty), and `Description:` lines. Saving it runs the listing checker
   automatically. Fix whatever it reports and save again. To check a draft by
   hand, run `uv run --script "${CLAUDE_PLUGIN_ROOT}/hooks/listing_check.py" <draft>`.
2. **Open Mercari in Chrome** with Claude in Chrome, where the user is signed
   in. Don't use the built-in browser; it can't upload photos.
3. **Start from the saved template** named in `[mercari] template_name`.
4. **Photos.** Upload from the card's folder, with the cleanest front shot of
   the slab first, because the first photo becomes the cover.
5. **Title.** Replace Mercari's suggested title with the draft's title.
6. **Description.** Put the card-specific lines above the template's standard
   text.
7. **Condition and shipping** come from the draft. For graded slabs, the rules
   file sets both.
8. **Stop.** Leave the price empty. Tell the user the listing is ready for a
   price, and name the card. Don't press List.

## When unsure

For anything about money or publishing (prices, offers, deleting or
relisting), ask one short question first. For small unclear details, pick the
sensible default and say what you assumed.
