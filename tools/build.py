#!/usr/bin/env python3
"""Regenerate the generated parts of the site.

  data/gallery.json   ->  the Work grid inside index.html
  data/biweekly.json  ->  the whole of biweekly.html

The JSON is the single source of truth. Edit it (or let the labelling tool
write it), run this, commit. Nothing generated is hand-edited.

biweekly.html takes its head, brand mark, header and footer from index.html,
so the two pages cannot drift: change the header in index.html, rebuild, and
the log page follows.

    python3 tools/build.py          # rewrite index.html and biweekly.html
    python3 tools/build.py --check  # verify only, non-zero exit if stale
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gallery.json"
PAGE = ROOT / "index.html"
LOG_DATA = ROOT / "data" / "biweekly.json"
LOG_PAGE = ROOT / "biweekly.html"
LOG_IMAGES = ROOT / "images" / "biweekly"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

SPAN = {"tile--full": 12, "tile--wide": 8, "tile--half": 6,
        "tile--tall": 4, "tile--sq": 4, "tile--sq6": 6}
GROUP_ORDER = ["city", "land", "people"]


def caption(f, n):
    """A wire-service cutline: a dateline, then one sentence of what is in the
    frame. The dateline is 'PLACE — DATE' once both are filled in, and falls
    back to the group label while they are empty, so the line is never blank.
    A frame with no cutline yet keeps the old group + number placeholder."""
    c = f.get("caption", "").strip()
    if not c:
        return f'<span>{f["group"].title()}</span><b>No. {n:02d}</b>'
    dateline = " — ".join(x for x in (f.get("place", "").strip(),
                                      str(f.get("date", "")).strip()) if x)
    return (f'<span>{esc(dateline or f["group"].title())}</span>'
            f'<p>{esc(c)}</p>')


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


# ---------------------------------------------------------------- biweekly

def jpeg_size(path):
    """Width and height straight out of the JPEG's SOF marker, so the img can
    carry width/height attributes and the page stops jumping as photos load.
    No Pillow: this has to run anywhere, including a bare checkout."""
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            return None
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            while b == b"\xff":
                b = f.read(1)
            if not b:
                return None
            marker = b[0]
            if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue  # standalone markers, no length field
            head = f.read(2)
            if len(head) < 2:
                return None
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                sof = f.read(5)
                if len(sof) < 5:
                    return None
                return (int.from_bytes(sof[3:5], "big"),
                        int.from_bytes(sof[1:3], "big"))
            f.seek(int.from_bytes(head, "big") - 2, 1)


def longdate(iso):
    """2026-09-22 -> 22 September 2026. Anything else is passed through, so a
    hand-written 'Week 3' still renders."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso.strip())
    if not m:
        return iso.strip()
    y, mo, d = (int(x) for x in m.groups())
    if not 1 <= mo <= 12:
        return iso.strip()
    return f"{d} {MONTHS[mo - 1]} {y}"


def lift(page, pattern, what):
    m = re.search(pattern, page, re.S)
    if not m:
        sys.exit(f"could not find the {what} in index.html")
    return m.group(0)


def relink(html):
    """The front page's own-page anchors have to become links back to it."""
    html = html.replace('href="biweekly.html"', 'href="biweekly.html" aria-current="page"')
    html = re.sub(r'href="#(work|about|contact)"', r'href="index.html#\1"', html)
    return html.replace('href="#top"', 'href="index.html"')


def entry_html(e, n, total):
    stem = e["id"]
    src = LOG_IMAGES / f"{stem}.jpg"
    if not src.exists():
        sys.exit(f"missing image: images/biweekly/{stem}.jpg")
    size = jpeg_size(src)
    if not size:
        sys.exit(f"could not read the size of images/biweekly/{stem}.jpg")
    dim = f' width="{size[0]}" height="{size[1]}"'
    ar = f' style="--ar:{size[0] / size[1]:.4f}"'
    meta = [f'<span class="entry__no">No. {n:02d}</span>']
    if e.get("prompt", "").strip():
        meta.append(f'<span class="entry__prompt">{esc(e["prompt"].strip())}</span>')
    if e.get("date", "").strip():
        meta.append(f'<span class="entry__date">{esc(longdate(e["date"]))}</span>')

    cap = ""
    if e.get("caption", "").strip():
        place = esc(e.get("place", "").strip())
        cap = ("\n          <figcaption>"
               + (f"<span>{place}</span>" if place else "")
               + f'<p>{esc(e["caption"].strip())}</p></figcaption>')

    # the newest frame is the one above the fold, so it is the one not deferred
    lazy = "" if n == total else ' loading="lazy"'
    return (f'      <article class="entry reveal"{ar}>\n'
            f'        <div class="entry__meta">{"".join(meta)}</div>\n'
            f'        <figure class="tile entry__frame" tabindex="0">\n'
            f'          <span class="entry__shot">\n'
            f'            <img src="images/biweekly/{stem}.jpg" alt="{esc(e.get("alt", ""))}"'
            f'{dim}{lazy}>\n'
            f'            <svg viewBox="0 0 91.93 100" class="mark tile__mark" aria-hidden="true"><use href="#mark"/></svg>\n'
            f'          </span>{cap}\n'
            f'        </figure>\n'
            f'      </article>')


def build_biweekly(index_html):
    entries = json.loads(LOG_DATA.read_text())["entries"]
    seen = set()
    for e in entries:
        if e["id"] in seen:
            sys.exit(f"duplicate biweekly id: {e['id']}")
        seen.add(e["id"])

    total = len(entries)
    # newest first on the page, but numbered in the order they were posted
    body = "\n\n".join(entry_html(e, total - i, total)
                       for i, e in enumerate(reversed(entries)))
    if not entries:
        body = '      <p class="log__empty">Nothing posted yet.</p>'

    head = lift(index_html, r'<meta charset="utf-8">.*?<link rel="stylesheet" href="assets/site\.css">', "head")
    head = head.replace("<title>Eli — Photography</title>", "<title>Biweekly — Eli</title>")
    head = head.replace('<meta name="description" content="Eli — photographer, Washington DC.">',
                        '<meta name="description" content="Biweekly — a new photograph every other week.">')
    head = head.replace('<meta property="og:title" content="Eli — Photography">',
                        '<meta property="og:title" content="Biweekly — Eli">')
    head = head.replace('<meta property="og:description" content="Portrait, landscape and street.">',
                        '<meta property="og:description" content="A new photograph every other week.">')

    sprite = lift(index_html, r'<!-- Brand mark\..*?</svg>\n', "brand mark sprite")
    header = relink(lift(index_html, r'<header class="header".*?</header>', "header"))
    footer = relink(lift(index_html, r'<footer class="footer">.*?</footer>', "footer"))
    lightbox = lift(index_html, r'<div class="lightbox".*?\n</div>', "lightbox")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>

{sprite}
{header}

<!-- ============================ PAGE HEAD ============================ -->
<section class="page-head" id="top">
  <div class="reveal">
    <svg viewBox="0 0 91.93 100" class="mark head__mark" aria-hidden="true"><use href="#mark"/></svg>
    <span class="eyebrow">Photography class</span>
    <h1 class="h-display">Biweekly</h1>
    <p class="lede">One new frame every other week.</p>
  </div>
</section>

<!-- ============================ LOG ============================ -->
<!-- Generated from data/biweekly.json by tools/build.py — do not edit by hand -->
<section class="section section--log">
  <div class="log" id="log">
{body}
  </div>
</section>

{footer}

{lightbox}

<script src="assets/site.js"></script>

</body>
</html>
"""


if __name__ == "__main__":
    new, blocks, n = build()
    log_page = build_biweekly(new)
    log_n = len(json.loads(LOG_DATA.read_text())["entries"])
    check = "--check" in sys.argv

    if check:
        stale = []
        if new != PAGE.read_text():
            stale.append("index.html")
        if not LOG_PAGE.exists() or log_page != LOG_PAGE.read_text():
            stale.append("biweekly.html")
        if stale:
            sys.exit(f"stale: {', '.join(stale)} — run tools/build.py")
        print("index.html and biweekly.html match their data")
    else:
        PAGE.write_text(new)
        LOG_PAGE.write_text(log_page)

    for g, count, cols, _ in blocks:
        print(f"  {g:<7} {count:>2} frames  {cols:>3} cols"
              + ("" if cols % 12 == 0 else f"   (ragged tail {cols % 12})"))
    print(f"  {n} frames total")
    print(f"  biweekly {log_n} {'entry' if log_n == 1 else 'entries'}")
