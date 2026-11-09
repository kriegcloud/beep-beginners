---
name: card-listing
description: >
  Draft a marketplace listing for a trading card and fill in the form in Chrome, without publishing it. Use when the user says "list this card", "make a listing for <card>", "draft listings for the cards in Ready", or asks to check a listing draft.
---

# Card listing

The user sets the price and presses List. You never type a price and never press List, Publish or Save changes on a live listing.

## Where things are

- Photos: the `card_inbox_ready` path in `workspace.config`, one folder per card.
- Drafts: `card-sales/listings/<date>-<card>.md`. If the folder has a lister script, use it to make the draft, then save its output as a draft file.

## Rules for every listing

- English only. Never put Japanese characters in a listing, even for Japanese cards. Use the English card name and say "Japanese" in words.
- Graded slabs: condition is always Good. The shipping line is always "Slab ships in a bubble mailer with protection." Never put the grading cert number in the title or description; the grade line is just the grade, such as "Graded PSA 8 NM-MT".
- Start from the user's saved template (Trading Cards > Single Cards, brand Pokemon, their standard closing text). Card-specific lines go above the template text.

## Steps

1. **Draft.** Write the draft with `Title:`, `Condition:`, `Price:` (left empty) and `Description:` lines. Check it against the rules above before moving on.
2. **Open the marketplace in Chrome** with Claude in Chrome, where the user is signed in. Don't use the built-in browser; it can't upload photos.
3. **Start from the saved template.**
4. **Photos.** Upload from the card's folder, cleanest front shot of the slab first, because the first photo becomes the cover.
5. **Title.** Replace the site's suggested title with the draft's title.
6. **Description.** Put the card-specific lines above the template's standard text.
7. **Condition and shipping** come from the draft.
8. **Stop.** Leave the price empty. Tell the user the listing is ready for a price, and name the card. Don't press List.

## When unsure

For anything about money or publishing (prices, offers, deleting or relisting), ask one short question first. For small unclear details, pick the sensible default and say what you assumed.
