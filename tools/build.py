#!/usr/bin/env python3
"""Regenerate every generated page on the site.

  data/gallery.json   ->  the strip inside index.html, and all of portfolio.html
  data/biweekly.json  ->  all of biweekly.html
  data/pages.json     ->  about / education / tips / resume / ap-work
                          (contact.html is generated too, from index.html's own
                           contact markup)

index.html is the one page kept by hand, and it is also the template: every
other page lifts its head, brand mark, header, footer and lightbox straight out
of it. Change the header once, rebuild, and the whole site follows.

    python3 tools/build.py          # rewrite everything
    python3 tools/build.py --check  # verify only, non-zero exit if stale
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
GALLERY = ROOT / "data" / "gallery.json"
LOG_DATA = ROOT / "data" / "biweekly.json"
PAGES_DATA = ROOT / "data" / "pages.json"
LOG_IMAGES = ROOT / "images" / "biweekly"

SPAN = {"tile--full": 12, "tile--wide": 8, "tile--half": 6,
        "tile--tall": 4, "tile--sq": 4, "tile--sq6": 6}
GROUP_ORDER = ["photojournalism", "travel", "landscapes", "portraits"]

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def esc(v):
    return (v.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


# ----------------------------------------------------------------- captions

def caption(f, n):
    """A wire-service cutline: a dateline, then one sentence of what is in the
    frame. The dateline is 'PLACE — DATE' once both are filled in, and falls
    back to the category while they are empty, so the line is never blank.
    A frame with no cutline yet keeps the old category + number placeholder."""
    c = f.get("caption", "").strip()
    label = f["group"].title()
    if not c:
        return f'<span>{label}</span><b>No. {n:02d}</b>'
    dateline = " — ".join(x for x in (f.get("place", "").strip(),
                                      str(f.get("date", "")).strip()) if x)
    return f'<span>{esc(dateline or label)}</span><p>{esc(c)}</p>'


def song_attrs(f):
    s = f.get("song") or {}
    artist, track = s.get("artist", "").strip(), s.get("track", "").strip()
    if not (artist and track):
        return ""
    a = f' data-artist="{esc(artist)}" data-track="{esc(track)}"'
    if s.get("url", "").strip():
        a += f' data-song-url="{esc(s["url"].strip())}"'
    return a


def figure(f, shape, mods, n, indent="      "):
    cls = " ".join(["tile", shape] + list(mods) + ["reveal"])
    d = f' data-d="{n % 3}"' if n % 3 else ""
    cap = caption(f, n)
    cap = f'\n{indent}  <figcaption>{cap}</figcaption>' if cap else ""
    return (f'{indent}<figure class="{cls}"{d} tabindex="0"{song_attrs(f)}>\n'
            f'{indent}  <img src="images/{f["id"]}.jpg" alt="{esc(f["alt"])}" loading="lazy">\n'
            f'{indent}  <svg viewBox="0 0 91.93 100" class="mark tile__mark" aria-hidden="true"><use href="#mark"/></svg>'
            f'{cap}\n'
            f'{indent}</figure>')


# ----------------------------------------------------------------- gallery

def load_gallery():
    data = json.loads(GALLERY.read_text())
    frames, seen = data["frames"], set()
    for f in frames:
        if f["id"] in seen:
            sys.exit(f"duplicate frame id: {f['id']}")
        seen.add(f["id"])
        if not (ROOT / "images" / f"{f['id']}.jpg").exists():
            sys.exit(f"missing image: images/{f['id']}.jpg")
        if f["group"] not in GROUP_ORDER:
            sys.exit(f"{f['id']}: unknown category {f['group']!r}")
    by_id = {f["id"]: f for f in frames}
    for h in data.get("home", []):
        if h["id"] not in by_id:
            sys.exit(f"home strip references an unknown frame: {h['id']}")
    return data, by_id


def groups_block(data, by_id, which):
    """The generated #groups container. On the portfolio page that is one grid
    per category; on the home page it is the single unfiltered strip."""
    if which == "home":
        figs = [figure(by_id[h["id"]], h["shape"], [], i + 1)
                for i, h in enumerate(data.get("home", []))]
        inner = ('    <div class="grid">\n' + "\n\n".join(figs) + "\n    </div>")
        cols = sum(SPAN[h["shape"]] for h in data.get("home", []))
        return inner, [("home", len(figs), cols)]

    blocks, tally, n = [], [], 0
    for g in GROUP_ORDER:
        rows = [f for f in data["frames"] if f["group"] == g]
        if not rows:
            continue
        figs = []
        for f in rows:
            n += 1
            figs.append(figure(f, f["shape"], f.get("mods", []), n))
        blocks.append(f'    <div class="grid" data-group="{g}">\n'
                      + "\n\n".join(figs) + "\n    </div>")
        tally.append((g, len(rows), sum(SPAN[f["shape"]] for f in rows)))
    return "\n\n".join(blocks), tally


def swap_groups(page, inner):
    body = '  <div class="groups" id="groups">\n' + inner + "\n  </div>"
    new = re.sub(r'  <div class="groups" id="groups">\n.*?\n  </div>',
                 lambda _: body, page, count=1, flags=re.S)
    if new == page and body not in page:
        sys.exit("could not find the groups container")
    return new


# ----------------------------------------------------------------- template

def lift(page, pattern, what):
    m = re.search(pattern, page, re.S)
    if not m:
        sys.exit(f"could not find the {what} in index.html")
    return m.group(0)


def relink(html, slug):
    """Mark the tab for the page being generated."""
    return html.replace(f'href="{slug}.html"', f'href="{slug}.html" aria-current="page"')


def shell(index_html, slug, title, description, body):
    head = lift(index_html,
                r'<meta charset="utf-8">.*?<link rel="stylesheet" href="assets/site\.css">',
                "head")
    head = head.replace("<title>Eli — Photography</title>", f"<title>{esc(title)} — Eli</title>")
    head = re.sub(r'<meta name="description" content="[^"]*">',
                  f'<meta name="description" content="{esc(description)}">', head, count=1)
    head = re.sub(r'<meta property="og:title" content="[^"]*">',
                  f'<meta property="og:title" content="{esc(title)} — Eli">', head, count=1)
    head = re.sub(r'<meta property="og:description" content="[^"]*">',
                  f'<meta property="og:description" content="{esc(description)}">', head, count=1)

    sprite = lift(index_html, r'<!-- Brand mark\..*?</svg>\n', "brand mark sprite")
    header = relink(lift(index_html, r'<header class="header".*?</header>', "header"), slug)
    footer = relink(lift(index_html, r'<footer class="footer">.*?</footer>', "footer"), slug)
    lightbox = lift(index_html, r'<div class="lightbox".*?\n</div>', "lightbox")

    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n{head}\n</head>\n<body>\n\n'
            f'{sprite}\n{header}\n\n'
            f'<!-- Generated by tools/build.py — do not edit by hand -->\n'
            f'{body}\n\n{footer}\n\n{lightbox}\n\n'
            f'<script src="assets/site.js"></script>\n\n</body>\n</html>\n')


def page_head(eyebrow, title, lede=""):
    lede = f'\n    <p class="lede">{esc(lede)}</p>' if lede else ""
    return (f'<section class="page-head" id="top">\n'
            f'  <div class="reveal">\n'
            f'    <svg viewBox="0 0 91.93 100" class="mark head__mark" aria-hidden="true"><use href="#mark"/></svg>\n'
            f'    <span class="eyebrow">{esc(eyebrow)}</span>\n'
            f'    <h1 class="h-display">{esc(title)}</h1>{lede}\n'
            f'  </div>\n'
            f'</section>')


# ----------------------------------------------------------------- portfolio

def build_portfolio(index_html, data, by_id):
    inner, tally = groups_block(data, by_id, "portfolio")
    filters = "\n".join(
        f'    <button data-filter="{g}">{g.title()}</button>'
        for g, _, _ in tally)
    body = (f'{page_head("Selected", "Portfolio")}\n\n'
            f'<section class="section" id="work">\n'
            f'  <div class="filters reveal" id="filters">\n'
            f'    <button class="is-active" data-filter="all">All</button>\n'
            f'{filters}\n'
            f'  </div>\n\n'
            f'  <div class="groups" id="groups">\n{inner}\n  </div>\n'
            f'</section>')
    return shell(index_html, "portfolio", "Portfolio",
                 "Selected photographs — photojournalism, travel, landscapes and portraits.",
                 body), tally


# ----------------------------------------------------------------- contact

def build_contact(index_html):
    block = (ROOT / "tools" / "partials" / "contact.html").read_text().rstrip("\n")
    body = f'{page_head("Contact", "Get in touch")}\n\n{block}'
    return shell(index_html, "contact", "Contact",
                 "Get in touch — Eli, photographer, Washington DC.", body)


# ----------------------------------------------------------------- shells

def build_pages(index_html):
    out = []
    for p in json.loads(PAGES_DATA.read_text())["pages"]:
        paras = [x for x in p.get("body", []) if x.strip()]
        if paras:
            inner = "\n".join(f'    <p class="lede">{esc(x)}</p>' for x in paras)
        else:
            inner = (f'    <p class="lede placeholder">Not written yet — '
                     f'{esc(p["note"])}</p>')
        body = (f'{page_head(p["eyebrow"], p["title"])}\n\n'
                f'<section class="section">\n'
                f'  <div class="prose reveal">\n{inner}\n  </div>\n'
                f'</section>')
        out.append((ROOT / f'{p["slug"]}.html',
                    shell(index_html, p["slug"], p["title"], p["note"], body),
                    p["slug"], bool(paras)))
    return out


# ----------------------------------------------------------------- biweekly

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
    entries, seen = json.loads(LOG_DATA.read_text())["entries"], set()
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

    page = (f'{page_head("Photography class", "Biweekly", "One new frame every other week.")}\n\n'
            f'<section class="section section--log">\n'
            f'  <div class="log" id="log">\n{body}\n  </div>\n'
            f'</section>')
    return shell(index_html, "biweekly", "Biweekly",
                 "Biweekly — a new photograph every other week.", page), total


# ----------------------------------------------------------------- driver

def build():
    data, by_id = load_gallery()
    inner, home_tally = groups_block(data, by_id, "home")
    index_html = swap_groups(PAGE.read_text(), inner)

    files = [(PAGE, index_html)]
    portfolio, tally = build_portfolio(index_html, data, by_id)
    files.append((ROOT / "portfolio.html", portfolio))
    files.append((ROOT / "contact.html", build_contact(index_html)))
    log, log_n = build_biweekly(index_html)
    files.append((ROOT / "biweekly.html", log))
    shells = build_pages(index_html)
    files += [(path, text) for path, text, _, _ in shells]
    return files, tally, home_tally, log_n, shells


if __name__ == "__main__":
    files, tally, home_tally, log_n, shells = build()
    check = "--check" in sys.argv

    if check:
        stale = [p.name for p, text in files
                 if not p.exists() or p.read_text() != text]
        if stale:
            sys.exit(f"stale: {', '.join(stale)} — run tools/build.py")
        print("every generated page matches its data")
    else:
        for path, text in files:
            path.write_text(text)

    for g, count, cols in tally + home_tally:
        print(f"  {g:<16}{count:>2} frames {cols:>4} cols"
              + ("" if cols % 12 == 0 else f"   (ragged tail {cols % 12})"))
    print(f"  {sum(c for _, c, _ in tally)} frames in the portfolio")
    print(f"  biweekly {log_n} {'entry' if log_n == 1 else 'entries'}")
    written = ", ".join(s for _, _, s, done in shells if not done)
    if written:
        print(f"  still to write: {written}")
