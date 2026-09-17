#!/usr/bin/env python3
"""Regenerate the Work grid in index.html from data/gallery.json.

The JSON is the single source of truth. Edit it (or let the labelling tool
write it), run this, commit. Nothing about the gallery is hand-edited in
index.html any more.

    python3 tools/build.py          # rewrite index.html
    python3 tools/build.py --check  # verify only, non-zero exit if stale
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gallery.json"
PAGE = ROOT / "index.html"

SPAN = {"tile--full": 12, "tile--wide": 8, "tile--half": 6,
        "tile--tall": 4, "tile--sq": 4, "tile--sq6": 6}
GROUP_ORDER = ["city", "land", "people"]


def caption(f, n):
    """Group label + number until a real title exists; then the title, and a
    place/year line if given. A frame explicitly titled 'untitled' gets no
    caption text at all — an untitled photograph should not announce it."""
    t = f.get("title", "").strip()
    if not t:
        return f'<span>{f["group"].title()}</span><b>No. {n:02d}</b>'
    if t.lower() == "untitled":
        return ""
    meta = " · ".join(x for x in (f.get("place", "").strip(),
                                  str(f.get("year", "")).strip()) if x)
    return (f'<span>{meta}</span>' if meta else "") + f'<b>{t}</b>'


def song_attrs(f):
    s = f.get("song") or {}
    artist, track = s.get("artist", "").strip(), s.get("track", "").strip()
    if not (artist and track):
        return ""
    a = f' data-artist="{esc(artist)}" data-track="{esc(track)}"'
    if s.get("url", "").strip():
        a += f' data-song-url="{esc(s["url"].strip())}"'
    return a


def esc(v):
    return (v.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def build():
    frames = json.loads(DATA.read_text())["frames"]
    seen, blocks, n = set(), [], 0

    for g in GROUP_ORDER:
        rows = [f for f in frames if f["group"] == g]
        if not rows:
            continue
        cols = sum(SPAN[f["shape"]] for f in rows)
        figs = []
        for f in rows:
            if f["id"] in seen:
                sys.exit(f"duplicate frame id: {f['id']}")
            seen.add(f["id"])
            if not (ROOT / "images" / f"{f['id']}.jpg").exists():
                sys.exit(f"missing image: images/{f['id']}.jpg")
            n += 1
            cls = " ".join(["tile", f["shape"]] + f.get("mods", []) + ["reveal"])
            d = f' data-d="{n % 3}"' if n % 3 else ""
            cap = caption(f, n)
            cap = f"\n        <figcaption>{cap}</figcaption>" if cap else ""
            figs.append(
                f'      <figure class="{cls}"{d} tabindex="0"{song_attrs(f)}>\n'
                f'        <img src="images/{f["id"]}.jpg" alt="{esc(f["alt"])}" loading="lazy">\n'
                f'        <svg viewBox="0 0 91.93 100" class="mark tile__mark" aria-hidden="true"><use href="#mark"/></svg>'
                f'{cap}\n'
                f'      </figure>')
        blocks.append((g, len(rows), cols,
                       f'    <div class="grid" data-group="{g}">\n'
                       + "\n\n".join(figs) + "\n    </div>"))

    body = ('  <div class="groups" id="groups">\n'
            + "\n\n".join(b[3] for b in blocks) + "\n  </div>")
    page = PAGE.read_text()
    new = re.sub(r'  <div class="groups" id="groups">\n.*?\n  </div>',
                 lambda _: body, page, count=1, flags=re.S)
    if new == page and body not in page:
        sys.exit("could not find the groups container in index.html")
    return new, blocks, n


if __name__ == "__main__":
    new, blocks, n = build()
    check = "--check" in sys.argv
    if check:
        if new != PAGE.read_text():
            sys.exit("index.html is stale — run tools/build.py")
        print("index.html matches data/gallery.json")
    else:
        PAGE.write_text(new)
    for g, count, cols, _ in blocks:
        print(f"  {g:<7} {count:>2} frames  {cols:>3} cols"
              + ("" if cols % 12 == 0 else f"   (ragged tail {cols % 12})"))
    print(f"  {n} frames total")
