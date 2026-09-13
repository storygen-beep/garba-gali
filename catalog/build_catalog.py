"""Build the Ghaghra Gali catalogue: an A5 lookbook and an A4 counter sheet.

Stock comes from the same Supabase tables the booking app uses, so the catalogue
can never disagree with the app about what is in the collection. Photos come from
catalog/photos/<CODE>.<ext> — originals, not the app's compressed copies.

    python3 build_catalog.py                 # both PDFs from real stock
    python3 build_catalog.py --demo 8        # add placeholder cards to judge layout
    python3 build_catalog.py --only lookbook

Prices are deliberately absent: the catalogue circulates on WhatsApp and prices
change; the code on each card is what a customer quotes back to you.
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# WeasyPrint reaches pango through ctypes; on macOS that lives in /opt/homebrew/lib,
# which is not on the default search path. Must be set before the import, and cannot
# be exported from a shell — SIP strips DYLD_* across an exec of a system binary.
if sys.platform == "darwin":
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

from PIL import Image, ImageOps  # noqa: E402
from weasyprint import HTML  # noqa: E402

HERE = Path(__file__).resolve().parent
SECRETS = Path.home() / "Documents" / "garba_gali" / "secrets" / "supabase.env"
PHOTO_DIR = HERE / "photos"
OUT_DIR = HERE / "out"
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".heic", ".HEIC", ".JPG", ".JPEG", ".PNG")
QUALITY = 82   # raised with --quality for a print run

SHOP = {
    "name": "Ghaghra Gali",
    "tagline": "Chaniya cholis on rent",
    "season": "Navratri 2026 · 11–19 October",
    "phone": "",          # filled from --phone
    "instagram": "",      # filled from --instagram
    "address": "",        # filled from --address
}

COLOURS = {
    "Red": "#C0243C", "Maroon": "#7A1530", "Pink": "#D6417A", "Orange": "#E0701E",
    "Yellow": "#E3B21C", "Green": "#2E8B57", "Teal": "#0F7C7C", "Blue": "#2748A8",
    "Purple": "#6B3FA0", "Black": "#262124", "White": "#EDE8E0", "Multicolour": "#C0243C",
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def read_secrets():
    env = {}
    if SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def fetch_stock():
    """Every lehenga in the shop, ordered by code."""
    env = read_secrets()
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        print("No Supabase credentials found; building from photos only.")
        return []
    req = urllib.request.Request(
        f"{url}/rest/v1/lehengas?select=code,title,colour,size,photo_path,photos&order=created_at.asc",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def find_photo(item):
    """Local file first (print copies live in catalog/photos), then the app storage."""
    stored = item.get("photo_path")
    if stored and (PHOTO_DIR / stored).exists():
        return PHOTO_DIR / stored
    for key in (item.get("code"), item.get("title")):
        for ext in PHOTO_EXT:
            if key and (PHOTO_DIR / f"{key}{ext}").exists():
                return PHOTO_DIR / f"{key}{ext}"
    if stored:
        env = read_secrets()
        cached = PHOTO_DIR / stored
        try:
            urllib.request.urlretrieve(f"{env['SUPABASE_URL']}/storage/v1/object/public/photos/{stored}", cached)
            return cached
        except Exception:
            return None
    return None


def prepared_photo(path, target_px, cache, crop=True):
    """Crop to 4:5, resize to the printed size at 300 dpi, embed as JPEG.

    WeasyPrint has no WebP filter and inflates such images inside the PDF, so
    everything becomes JPEG here regardless of what came in.
    """
    key = (str(path), target_px, crop)
    if key in cache:
        return cache[key]
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)          # honour the phone's rotation flag
    img = img.convert("RGB")
    # Never upscale: enlarging past the source adds bytes and no detail.
    target_px = min(target_px, img.width)
    if crop:
        img = ImageOps.fit(img, (target_px, int(target_px * 1.25)), Image.LANCZOS, centering=(0.5, 0.4))
    else:
        # A full-length garment must not lose its hem, so the lookbook keeps the whole frame.
        img.thumbnail((target_px, target_px * 3), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    cache[key] = uri
    return uri


def qr_svg(text):
    """QR for a WhatsApp link, drawn as SVG rectangles — no image library needed."""
    try:
        import qrcode
    except ImportError:
        return ""
    q = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(text)
    q.make(fit=True)
    m = q.get_matrix()
    n = len(m)
    cells = "".join(
        f'<rect x="{x}" y="{y}" width="1" height="1"/>'
        for y, row in enumerate(m) for x, on in enumerate(row) if on
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
            f'shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="#fff"/>'
            f'<g fill="#241B1E">{cells}</g></svg>')


MANDALA = '''<svg class="mandala" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <circle cx="32" cy="32" r="30" fill="#9E1236"/>
  <circle cx="32" cy="32" r="24" fill="none" stroke="#E3A21A" stroke-width="2.5" stroke-dasharray="2 4.3"/>
  <g fill="#FDF7EE" stroke="#E3A21A" stroke-width="1.5">
    <circle cx="46" cy="32" r="3.2"/><circle cx="41.9" cy="41.9" r="3.2"/><circle cx="32" cy="46" r="3.2"/>
    <circle cx="22.1" cy="41.9" r="3.2"/><circle cx="18" cy="32" r="3.2"/><circle cx="22.1" cy="22.1" r="3.2"/>
    <circle cx="32" cy="18" r="3.2"/><circle cx="41.9" cy="22.1" r="3.2"/>
  </g>
  <circle cx="32" cy="32" r="7.5" fill="#FDF7EE" stroke="#E3A21A" stroke-width="3"/>
</svg>'''


def attrs_html(item):
    bits = []
    if item.get("colour"):
        dot = COLOURS.get(item["colour"], "#8C7E83")
        # An SVG circle, because an empty inline-block collapses in this renderer.
        bits.append(f'<svg class="dot" viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg">'
                    f'<circle cx="5" cy="5" r="5" fill="{dot}"/></svg>{esc(item["colour"])}')
    if item.get("size"):
        bits.append(esc(item["size"]))
    return " · ".join(bits)


def photo_html(item, target_px, cache, crop=True):
    path = item.get("_photo")
    if not path:
        return '<span class="missing">photo to come</span>'
    return f'<img src="{prepared_photo(path, target_px, cache, crop)}" alt="{esc(item["title"])}">'


LOGO = HERE.parent / "assets" / "logo.png"


def logo_block():
    """The shop's logo carries the name, so the cover sets no wordmark of its own."""
    if LOGO.exists():
        uri = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
        return f'<img class="logo" src="{uri}" alt="{esc(SHOP["name"])}">'
    return f'{MANDALA}<h1>{esc(SHOP["name"])}</h1>'


def view_thumbs(item, cache):
    """The back and detail shots, small, so one piece still means one page."""
    extra = [v for v in (item.get("photos") or []) if v != item.get("photo_path")]
    out = []
    for v in extra[:2]:
        path = PHOTO_DIR / v
        if not path.exists():
            continue
        out.append(f'<img src="{prepared_photo(path, 320, cache)}" alt="">')
    return f'<div class="views">{"".join(out)}</div>' if out else ""


def cover_html():
    return f'''<section class="cover bandhani">
  <div class="cover-art">
    <div class="cover-plate">
      {logo_block()}
      <p class="tagline">{esc(SHOP["tagline"])}</p>
      <p class="season">{esc(SHOP["season"])}</p>
    </div>
  </div>
  <div class="cover-foot">{esc(" · ".join(x for x in (SHOP["phone"], SHOP["instagram"]) if x))}</div>
  <div class="hem"></div>
</section>'''


def back_html(qr):
    contact = " · ".join(x for x in (SHOP["phone"], SHOP["instagram"], SHOP["address"]) if x)
    qr_block = f'''<div class="ask">
      <div class="qr">{qr}</div>
      <p><b>Ask on WhatsApp</b>Scan, then send the number of the piece you want —
      for example “No. 07”. We will tell you the rent and whether it is free on your night.</p>
    </div>''' if qr else ""
    return f'''<section class="back">
  <div class="hem"></div>
  <div class="body">
    <h2>How renting works</h2>
    <ol>
      <li><strong>Pick your piece and your night.</strong> Quote the number on the card.</li>
      <li><strong>Pay an advance to hold it.</strong> Until the advance is paid the piece stays open to everyone.</li>
      <li><strong>Collect it the evening of your garba</strong>, with the balance and a refundable deposit.</li>
      <li><strong>Return it by 10 AM the next morning.</strong> Late returns hold up the next booking.</li>
      <li>Bring an ID at pickup. Rent is charged per night.</li>
    </ol>
    {qr_block}
  </div>
  <div class="contact"><b>{esc(SHOP["name"])}</b> · {esc(contact)}</div>
  <div class="hem"></div>
</section>'''


def build_lookbook(items, cache, qr, light=False):
    pages = [cover_html()]
    for it in items:
        pages.append(f'''<section class="piece">
  <div class="photo">{photo_html(it, 820 if light else 1100, cache, crop=False)}</div>
  <div class="plate">
    <div class="plate-text">
      <p class="name">{esc(it["title"])}</p>
      <p class="attrs">{attrs_html(it)}</p>
    </div>
    {view_thumbs(it, cache)}
    <div class="code"><span class="no">No.</span>{esc(it["ref"])}</div>
  </div>
</section>''')
    pages.append(back_html(qr))
    return f'<div class="book">{"".join(pages)}</div>'


def build_sheet(items, cache):
    per_page = 4
    pages = []
    for i in range(0, len(items), per_page):
        chunk = items[i:i + per_page]
        tiles = "".join(f'''<div class="tile">
      <div class="photo">{photo_html(it, 760, cache)}</div>
      <div class="line"><span class="name">{esc(it["title"])}</span><span class="code"><span class="no">No.</span>{esc(it["ref"])}</span></div>
      <div class="attrs">{attrs_html(it)}</div>
    </div>''' for it in chunk)
        pages.append(f'''<section class="sheet">
  <div class="sheet-head"><h2>{esc(SHOP["name"])}</h2><span class="season">{esc(SHOP["season"])}</span></div>
  <div class="grid">{tiles}</div>
</section>''')
    return "".join(pages)


def document(body):
    return f'''<!doctype html><html><head><meta charset="utf-8">
<title>{esc(SHOP["name"])} catalogue</title>
<link rel="stylesheet" href="style.css"></head><body>{body}</body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", type=int, default=0, help="add N placeholder cards to judge layout")
    ap.add_argument("--only", choices=["lookbook", "sheet"], help="build just one of the two")
    ap.add_argument("--phone", default="")
    ap.add_argument("--instagram", default="")
    ap.add_argument("--address", default="")
    ap.add_argument("--whatsapp", default="", help="digits for the wa.me QR, e.g. 919812345678")
    ap.add_argument("--quality", type=int, default=82, help="JPEG quality: 82 for WhatsApp, 90 for print")
    ap.add_argument("--light", action="store_true", help="smaller file for sharing on mobile data")
    ap.add_argument("--html", action="store_true", help="also write the HTML, for debugging")
    args = ap.parse_args()

    global QUALITY
    QUALITY = args.quality
    SHOP.update(phone=args.phone, instagram=args.instagram, address=args.address)
    OUT_DIR.mkdir(exist_ok=True)

    items = fetch_stock()
    for it in items:
        it["_photo"] = find_photo(it)
    for n in range(args.demo):
        items.append({"code": f"GG-{len(items) + 1:02d}", "title": "Sample piece",
                      "colour": list(COLOURS)[n % len(COLOURS)], "size": "M", "_photo": None})

    if not items:
        sys.exit("No stock found. Add lehengas in the app, or run with --demo 8.")

    # The shop keeps no codes, so the catalogue numbers the pieces itself. This is
    # what a customer quotes on WhatsApp, so it is printed large on every card.
    for n, it in enumerate(items, 1):
        it["ref"] = f"{n:02d}"

    with_photos = sum(1 for it in items if it["_photo"])
    print(f"{len(items)} pieces, {with_photos} with photos, {len(items) - with_photos} awaiting one")

    qr = qr_svg(f"https://wa.me/{args.whatsapp}?text=Hi%20Garba%20Gali,%20I%20would%20like%20to%20book%20No.%20") if args.whatsapp else ""
    cache = {}

    targets = []
    suffix = "-whatsapp" if args.light else ""
    if args.light:
        QUALITY = min(QUALITY, 70)
    if args.only != "sheet":
        targets.append(("lookbook", build_lookbook(items, cache, qr, light=args.light),
                        f"ghaghra-gali-lookbook{suffix}.pdf"))
    if args.only != "lookbook":
        targets.append(("sheet", build_sheet(items, cache), f"ghaghra-gali-counter-sheet{suffix}.pdf"))

    for label, body, filename in targets:
        html = document(body)
        if args.html:
            (OUT_DIR / f"{label}.html").write_text(html)
        out = OUT_DIR / filename
        HTML(string=html, base_url=str(HERE)).write_pdf(out, optimize_images=True, jpeg_quality=QUALITY, dpi=300)
        print(f"  {label}: {out}  ({out.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
