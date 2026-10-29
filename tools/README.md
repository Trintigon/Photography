# tools

    python3 tools/build.py            # rewrite every generated page
    python3 tools/build.py --check    # fail if any page is out of date

`index.html` is the only page written by hand, and it is also the template:
every other page lifts its head, brand mark, header, footer and lightbox out of
it at build time. Change the header once and the whole site follows — never edit
a generated page, it gets overwritten.

| page | from |
| --- | --- |
| `index.html` | hand-written, except the selected strip (`data/gallery.json` → `home`) |
| `portfolio.html` | `data/gallery.json` → `frames` |
| `biweekly.html` | `data/biweekly.json` |
| `contact.html` | `tools/partials/contact.html` |
| `about` `education` `tips` `resume` `ap-work` | `data/pages.json` |

The shared look lives in `assets/site.css` and `assets/site.js`, which every
page links. The script guards the page-specific pieces, so the filter bar and
the contact form can be missing without it throwing.

## The gallery is generated, not hand-written

`data/gallery.json` is the single source of truth for the Portfolio page and
for the short strip on the home page. One entry per photograph:

```json
{
  "id": "kyoto-bus",          // images/kyoto-bus.jpg
  "group": "travel",          // photojournalism | travel | landscapes | portraits
  "shape": "tile--wide",      // must match the file's aspect ratio
  "mods": [],                 // tile--bleed, tile--drop
  "alt": "A city bus crossing an empty Kyoto junction",
  "caption": "A city bus crosses an empty intersection beneath a no-entry sign.",
  "place": "", "date": "",
  "song": { "artist": "", "track": "", "url": "" }
}
```

## Shapes

| class | columns | aspect | use for |
| --- | --- | --- | --- |
| `tile--full` | 12 | 3:2 | landscape, given the whole row |
| `tile--wide` | 8 | 3:2 | landscape, pairs with a 4 |
| `tile--half` | 6 | 3:2 | landscape, pairs with a 6 |
| `tile--tall` | 4 | 2:3 | upright |
| `tile--sq` | 4 | 1:1 | square, small |
| `tile--sq6` | 6 | 1:1 | square, larger |

**The shape has to match the file's real aspect ratio** or the frame gets
cropped. `tile--bleed` runs a frame past the page gutter; `tile--drop` knocks
one out of line. Both are deliberate breaks — used sparingly, and ignored on
mobile.

Categories render in the order set by `GROUP_ORDER` in `build.py`, and within a
category in the order they appear in the JSON. A category is its own grid, so it
does not have to total a multiple of 12 — but the build prints each one's column
total, and a ragged tail means the last row does not fill. Adding a category
means adding it to `GROUP_ORDER`; the filter buttons are generated from it.

The `home` list at the top of the file is the strip on the home page. It
references frames by id and may give them a different shape, since a six-frame
strip tiles differently from a full category.

## Text pages

`data/pages.json` drives the five written tabs. Each starts as a shell:

```json
{ "slug": "tips", "nav": "Tips", "eyebrow": "Advice", "title": "Tips",
  "note": "What shows on the page until it is written." }
```

To fill one in, add a `body` array of paragraphs. The build renders those
instead and drops the placeholder styling:

```json
{ "slug": "tips", ..., "body": ["First paragraph.", "Second paragraph."] }
```

## Captions

Wire-service cutlines, not titles: a dateline, then one present-tense sentence
saying what is in the frame and nothing that isn't.

- `caption` → the sentence, with the dateline above it
- `place` + `date` → the dateline, rendered `PLACE — DATE`
- either one on its own → that one alone
- both empty → the group name stands in, so the line is never blank
- no `caption` → the old group name and running number

`alt` stays separate and stays short. A screen reader reads the alt text *and*
the cutline, so the two should not be the same sentence.

## Biweekly

`data/biweekly.json` drives `biweekly.html` — the class log, one photograph
every other week. Oldest first in the file; the page shows them newest first
and numbers them in posting order, so No. 01 stays No. 01 forever.

```json
{
  "id": "w03-motion",     // images/biweekly/w03-motion.jpg
  "date": "2026-10-06",   // rendered "6 October 2026"; any other text passes through
  "prompt": "Motion",     // the assignment, optional
  "place": "Washington, DC",
  "caption": "One sentence — what is in the frame.",
  "alt": "Short description for a screen reader"
}
```

To add one: drop the JPEG in `images/biweekly/`, add the entry, run the build.
No shape to pick — the build reads the file's real dimensions and the frame
takes its own proportions, capped at 78% of screen height so a tall photograph
still fits on screen. `place` and `caption` are both optional; with neither, the
frame stands on its own.

`biweekly.html` borrows its head, brand mark, header and footer from
`index.html` at build time, so edit those in `index.html` and rebuild — never in
`biweekly.html`, which is overwritten.
