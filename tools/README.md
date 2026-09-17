# tools

## The gallery is generated, not hand-written

`data/gallery.json` is the single source of truth for the Work section. One
entry per photograph:

```json
{
  "id": "kyoto-bus",          // images/kyoto-bus.jpg
  "group": "city",            // city | land | people
  "shape": "tile--wide",      // must match the file's aspect ratio
  "mods": [],                 // tile--bleed, tile--drop
  "alt": "A city bus crossing an empty Kyoto junction",
  "title": "", "place": "", "year": "",
  "song": { "artist": "", "track": "", "url": "" }
}
```

Then:

    python3 tools/build.py            # rewrite the grid in index.html
    python3 tools/build.py --check    # fail if index.html is out of date

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

Groups render in the order `city, land, people`, and within a group in the
order they appear in the JSON. A group no longer has to total a multiple of 12;
each is its own grid.

## Captions

- no `title` → the group name and a running number, as now
- `title` → the title, with `place · year` above it if given
- `title` set to `untitled` → no caption at all
