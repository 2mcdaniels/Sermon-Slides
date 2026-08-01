#!/usr/bin/env python3
"""TC Church - Design Studio (v1).

A generative art-direction engine: given a sermon (title, series, theme, tone,
imagery, points, scripture), it develops a creative direction and renders
professional 1920x1080 slides in THREE distinct concepts, then a cohesive slide
system for the chosen concept. Backgrounds are original generative artwork
(color fields, atmospheric gradients, geometric/symbolic forms) so nothing looks
like a PowerPoint theme. Typography uses a curated premium kit with automatic,
safe substitution.

Text on the exported ProPresenter slides stays live (Helvetica); these renders
are the DESIGN (backgrounds + the intended typographic layout).
"""
import os, math, random, colorsys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps

W, H = 1920, 1080
SS = 2                                   # supersample for crisp edges
MARGIN = 130                             # base text-safe margin (title-safe 16:9)

GF = "/usr/share/fonts/truetype/google-fonts"
LATO = "/usr/share/fonts/truetype/lato"
LIB = "/usr/share/fonts/truetype/liberation"
DEJ = "/usr/share/fonts/truetype/dejavu"

# Curated premium kit (open-source; bundle these with the app for parity).
FONTS = {
    "geo_bold":   f"{GF}/Poppins-Bold.ttf",
    "geo_med":    f"{GF}/Poppins-Medium.ttf",
    "geo_reg":    f"{GF}/Poppins-Regular.ttf",
    "geo_light":  f"{GF}/Poppins-Light.ttf",
    "black":      f"{LATO}/Lato-Black.ttf",
    "heavy":      f"{LATO}/Lato-Heavy.ttf",
    "semibold":   f"{LATO}/Lato-Semibold.ttf",
    "reg":        f"{LATO}/Lato-Regular.ttf",
    "light":      f"{LATO}/Lato-Light.ttf",
    "thin":       f"{LATO}/Lato-Thin.ttf",
    "serif":      f"{GF}/Lora-Variable.ttf",
    "serif_it":   f"{GF}/Lora-Italic-Variable.ttf",
    "cond_bold":  f"{LIB}/LiberationSansNarrow-Bold.ttf",
}
_FCACHE = {}
_FONT_DIR = os.environ.get("DS_FONT_DIR")   # bundle fonts with the app for deploy
def font(key, size):
    path = FONTS.get(key, FONTS["reg"])
    if _FONT_DIR:
        cand = os.path.join(_FONT_DIR, os.path.basename(path))
        if os.path.exists(cand):
            path = cand
    k = (path, int(size * SS))
    if k not in _FCACHE:
        try:
            _FCACHE[k] = ImageFont.truetype(path, int(size * SS))
        except Exception:
            _FCACHE[k] = ImageFont.truetype(FONTS["reg"], int(size * SS))
    return _FCACHE[k]


# --------------------------------------------------------------------------- #
#  CREATIVE DIRECTION                                                          #
# --------------------------------------------------------------------------- #
# Each palette is a full art direction: base + partner (for gradients), ink,
# secondary ink, accent, and whether it's a light or dark scheme.
PALETTES = {
    "midnight":  dict(bg=(14,22,40),  bg2=(8,13,26),   ink=(244,241,233), sub=(150,164,190), accent=(232,140,66),  light=False),
    "ember":     dict(bg=(24,17,15),  bg2=(12,9,8),    ink=(245,238,229), sub=(168,150,138), accent=(224,106,58),  light=False),
    "forest":    dict(bg=(16,34,29),  bg2=(9,20,17),   ink=(238,240,229), sub=(150,170,156), accent=(214,150,80),  light=False),
    "plum":      dict(bg=(30,18,38),  bg2=(17,10,24),  ink=(240,235,240), sub=(168,150,176), accent=(232,120,150), light=False),
    "slate":     dict(bg=(22,26,32),  bg2=(12,15,19),  ink=(238,240,244), sub=(150,160,172), accent=(96,168,224),  light=False),
    "bone":      dict(bg=(240,236,226),bg2=(224,218,205),ink=(28,30,34),  sub=(110,110,104), accent=(200,86,40),   light=True),
    "dawn":      dict(bg=(244,231,216),bg2=(226,196,168),ink=(46,32,40),  sub=(128,104,104), accent=(198,92,58),   light=True),
    "deepsea":   dict(bg=(10,28,38),  bg2=(6,17,24),   ink=(232,242,244), sub=(132,168,178), accent=(94,196,190),  light=False),
}

# Keyword -> palette bias, plus mood + motif hints for creative direction.
def creative_direction(sermon):
    """Return a dict describing the art direction for this sermon."""
    text = " ".join(str(sermon.get(k, "")) for k in
                    ("title", "series", "theme", "tone", "imagery")).lower()
    def has(*ws): return any(w in text for w in ws)

    if has("fire", "furnace", "refine", "burn", "revival", "passion", "zeal"):
        pal, motif = "ember", "ember"
    elif has("grace", "mercy", "sinner", "scum", "broken", "prodigal", "redemption", "cross"):
        pal, motif = "midnight", "halo"
    elif has("grow", "root", "tree", "seed", "harvest", "abide", "vine", "fruit", "garden"):
        pal, motif = "forest", "horizon"
    elif has("hope", "dawn", "light", "morning", "new", "advent", "promise", "wait"):
        pal, motif = "dawn", "sun"
    elif has("water", "deep", "sea", "wave", "storm", "ocean", "river", "flood"):
        pal, motif = "deepsea", "tide"
    elif has("king", "glory", "worship", "holy", "majesty", "throne", "worthy"):
        pal, motif = "plum", "rays"
    elif has("doubt", "question", "wander", "wilderness", "night", "grief"):
        pal, motif = "slate", "grid"
    else:
        pal, motif = "midnight", "arc"

    mood = "resolute"
    if has("hope", "joy", "peace", "grace", "rest", "comfort"): mood = "hopeful"
    if has("fire", "revival", "war", "battle", "urgent", "now"): mood = "urgent"
    if has("wonder", "mystery", "glory", "awe", "holy"): mood = "reverent"

    return dict(palette=pal, motif=motif, mood=mood,
                colors=PALETTES[pal], series=sermon.get("series", ""),
                title=sermon.get("title", ""))


# --------------------------------------------------------------------------- #
#  TEXTURE & COLOR HELPERS                                                     #
# --------------------------------------------------------------------------- #
def _lerp(a, b, t): return tuple(round(a[i] + (b[i]-a[i]) * t) for i in range(3))

def vgrad(size, top, bottom):
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        base.putpixel((0, y), _lerp(top, bottom, y/(h-1)))
    return base.resize((w, h))

def radial(size, inner, outer, cx=0.5, cy=0.42, r=0.9):
    w, h = size
    small = 320
    sw, sh = small, round(small*h/w)
    img = Image.new("RGB", (sw, sh))
    px = img.load()
    maxr = math.hypot(max(cx, 1-cx)*sw, max(cy, 1-cy)*sh) * r
    for y in range(sh):
        for x in range(sw):
            d = math.hypot(x-cx*sw, y-cy*sh)/maxr
            px[x, y] = _lerp(inner, outer, min(1, d))
    return img.resize((w, h), Image.LANCZOS)

def grain(img, amount=10):
    w, h = img.size
    n = Image.effect_noise((w, h), amount).convert("L")
    noise = Image.merge("RGB", (n, n, n))
    return ImageChops.overlay(img, noise)

def vignette(img, strength=0.55):
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-w*0.25, -h*0.25, w*1.25, h*1.25], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w*0.12))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, dark, mask.point(lambda v: int(255-(255-v)*strength)))

def soft_light(img, cx, cy, color, radius, opacity=0.5):
    w, h = img.size
    layer = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(radius*0.6))
    return ImageChops.screen(img, ImageChops.multiply(layer, Image.new("RGB",(w,h),
            (int(255*opacity),)*3)))


# --------------------------------------------------------------------------- #
#  TYPOGRAPHY                                                                  #
# --------------------------------------------------------------------------- #
def _tw(d, s, f): return d.textbbox((0, 0), s, font=f)[2]
def _th(f):
    a = f.getmetrics(); return a[0] + a[1]

def balanced_wrap(d, text, f, maxw, max_lines=4):
    """Wrap to fit maxw, then rebalance so line lengths are even and no orphan
    word sits alone on the last line. Returns list[str] or None if it can't fit
    within max_lines."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tw(d, t, f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    if any(_tw(d, ln, f) > maxw for ln in lines):
        return None
    if len(lines) > max_lines:
        return None
    # rebalance: if last line is a lone short word, pull a word down
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        prev = lines[-2].split()
        if len(prev) > 1:
            lines[-1] = prev[-1] + " " + lines[-1]
            lines[-2] = " ".join(prev[:-1])
    return lines

def fit_lines(d, text, key, maxw, max_lines, hi, lo):
    """Try to lay text out well: prefer good breaks at a large size; only shrink
    (down to lo) as a last resort. Returns (font, lines, size)."""
    for size in range(hi, lo-1, -3):
        f = font(key, size)
        lines = balanced_wrap(d, text.upper() if False else text, f, maxw*SS, max_lines)
        if lines:
            return f, lines, size
    f = font(key, lo)
    lines = balanced_wrap(d, text, f, maxw*SS, 12) or [text]
    return f, lines, lo

def draw_block(d, lines, f, x, y, fill, align="left", lh=1.06, tracking=0,
               box_w=None):
    """Draw multi-line text. align left/center/right within box (x is the box
    left; box_w needed for center/right)."""
    lh_px = _th(f) * lh
    for i, ln in enumerate(lines):
        w = _tw_tracked(d, ln, f, tracking)
        if align == "center":
            lx = x + (box_w - w)/2
        elif align == "right":
            lx = x + (box_w - w)
        else:
            lx = x
        _draw_tracked(d, ln, f, lx, y + i*lh_px, fill, tracking)
    return y + len(lines)*lh_px

def _tw_tracked(d, s, f, tr):
    if not tr: return _tw(d, s, f)
    return sum(_tw(d, ch, f) + tr for ch in s) - (tr if s else 0)

def _draw_tracked(d, s, f, x, y, fill, tr):
    if not tr:
        d.text((x, y), s, font=f, fill=fill); return
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += _tw(d, ch, f) + tr

def kicker(d, text, f, x, y, fill, tracking):
    _draw_tracked(d, text.upper(), f, x, y, fill, tracking)


# --------------------------------------------------------------------------- #
#  BACKDROP MOTIFS (generative, concept-specific)                             #
# --------------------------------------------------------------------------- #
def base_field(c, variant="flat"):
    """Base color field for a direction."""
    if variant == "atmos":
        img = radial((W, H), _lerp(c["bg"], c["bg2"], -0.2) if False else c["bg"],
                     c["bg2"], cx=0.32, cy=0.38, r=1.05)
    else:
        img = vgrad((W, H), _lerp(c["bg"], (255,255,255), 0.04), c["bg2"])
    return img

def motif_layer(img, c, motif, concept):
    """Draw the symbolic/geometric motif for abstract concept, subtle for others."""
    w, h = img.size
    ov = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(ov, "RGBA")
    acc = c["accent"]; ink = c["ink"]
    strong = concept == "abstract"
    a = 255 if strong else 60
    if motif in ("sun", "halo", "rays"):
        cx, cy = (w*0.30, h*0.42) if strong else (w*0.78, h*0.30)
        R = h*0.42 if strong else h*0.5
        for i, rr in enumerate([R, R*0.72, R*0.48]):
            col = acc if i == 0 else _lerp(acc, c["bg"], 0.35*i)
            d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=col+(a,), width=max(2,int(h*0.006)))
        if strong:
            d.ellipse([cx-R*0.30, cy-R*0.30, cx+R*0.30, cy+R*0.30], fill=acc+(255,))
    elif motif in ("horizon", "tide"):
        cy = h*0.62 if strong else h*0.8
        for i in range(5):
            yy = cy + i*h*0.05
            col = _lerp(acc, c["bg"], 0.15+0.16*i)
            d.line([(0, yy), (w, yy-h*0.02)], fill=col+(a,), width=max(2,int(h*0.004)))
        if strong:
            d.ellipse([w*0.58, cy-h*0.34, w*0.58+h*0.34, cy], outline=acc+(255,), width=int(h*0.01))
    elif motif == "arc":
        cx, cy = (w*0.34, h*1.15) if strong else (w*1.1, h*1.2)
        for rr in [h*1.0, h*0.8, h*0.6]:
            d.arc([cx-rr, cy-rr, cx+rr, cy+rr], 180, 360, fill=acc+(a,), width=max(2,int(h*0.006)))
    elif motif in ("grid", "ember"):
        step = int(w*0.05)
        col = (ink[0], ink[1], ink[2], 22 if not strong else 40)
        for x in range(0, w, step):
            d.line([(x, 0), (x, h)], fill=col, width=1)
        for y in range(0, h, step):
            d.line([(0, y), (w, y)], fill=col, width=1)
        if motif == "ember" and strong:
            random.seed(3)
            for _ in range(60):
                ex, ey = random.uniform(0, w), random.uniform(h*0.3, h)
                s = random.uniform(2, 6)
                d.ellipse([ex-s, ey-s, ex+s, ey+s], fill=acc+(random.randint(60,180),))
    out = ImageChops.screen(img, ov) if not c["light"] else ImageChops.multiply(
        img, Image.new("RGB",(w,h),(255,255,255)))
    if strong:
        out = Image.blend(img, ImageChops.screen(img, ov), 0.9)
    return out


# --------------------------------------------------------------------------- #
#  CONCEPT TITLE SLIDES                                                        #
# --------------------------------------------------------------------------- #
def _canvas():
    return Image.new("RGB", (W*SS, H*SS), (0, 0, 0))

def _finish(img):
    return img.resize((W, H), Image.LANCZOS)

def _upscale_bg(bg):
    return bg.resize((W*SS, H*SS), Image.LANCZOS)

def title_editorial(cd):
    """Concept A - bold typographic / editorial: flat premium field, oversized
    stacked title, kicker + rule, generous negative space."""
    c = cd["colors"]
    bg = base_field(c, "flat")
    bg = grain(bg, 7)
    img = _upscale_bg(bg); d = ImageDraw.Draw(img, "RGBA")
    ml = MARGIN
    # kicker (series)
    if cd["series"]:
        kf = font("semibold", 24)
        kicker(d, cd["series"], kf, ml*SS, (MARGIN-6)*SS, c["accent"], 8*SS)
    # title, huge, stacked, shrink-last
    box_w = W - MARGIN*2 - 40
    f, lines, size = fit_lines(d, cd["title"].upper(), "black", box_w, 4, 150, 78)
    total = _th(f)*1.02*len(lines)
    y = (H*SS - total)/2 + 20*SS
    y = draw_block(d, lines, f, ml*SS, y, c["ink"], "left", 1.02, box_w=box_w*SS)
    # rule + one-word accent underline
    d.rectangle([ml*SS, y+26*SS, (ml+96)*SS, y+34*SS], fill=c["accent"])
    return _finish(img)

def title_abstract(cd):
    """Concept B - abstract / symbolic: generative motif is the hero; title sits
    in deliberate negative space; lighter, geometric type."""
    c = cd["colors"]
    bg = base_field(c, "atmos")
    bg = motif_layer(bg, c, cd["motif"], "abstract")
    bg = grain(bg, 6)
    img = _upscale_bg(bg); d = ImageDraw.Draw(img, "RGBA")
    # title lower-right, right-aligned, in the calm zone
    box_w = W*0.52
    rx = W - MARGIN - box_w
    f, lines, size = fit_lines(d, cd["title"], "geo_bold", box_w, 4, 104, 60)
    total = _th(f)*1.08*len(lines)
    y = H - MARGIN - total - 40
    draw_block(d, lines, f, rx*SS, y*SS, c["ink"], "right", 1.08, box_w=box_w*SS)
    if cd["series"]:
        kf = font("semibold", 22)
        tw = _tw_tracked(d, cd["series"].upper(), kf, 7*SS)
        kicker(d, cd["series"], kf, (rx+box_w)*SS - tw, (y-46)*SS, c["accent"], 7*SS)
    return _finish(img)

def title_cinematic(cd):
    """Concept C - cinematic / atmospheric: deep gradient, light bloom, grain,
    vignette; elegant serif title low-left with lots of dark negative space."""
    c = cd["colors"]
    bg = radial((W, H), _lerp(c["bg"], c["accent"], 0.06), c["bg2"], cx=0.62, cy=0.30, r=1.1)
    bgb = bg.convert("RGB")
    img = _upscale_bg(bgb)
    img = img.resize((W, H), Image.LANCZOS)
    img = soft_light(img, int(W*0.66), int(H*0.30), c["accent"], int(H*0.55), 0.30)
    img = vignette(img, 0.5)
    img = grain(img, 9)
    img = img.resize((W*SS, H*SS), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    if cd["series"]:
        kf = font("semibold", 22)
        kicker(d, cd["series"], kf, MARGIN*SS, (H-MARGIN-150)*SS, c["accent"], 8*SS)
    box_w = W*0.66
    f, lines, size = fit_lines(d, cd["title"], "serif", box_w, 3, 116, 66)
    total = _th(f)*1.05*len(lines)
    y = H - MARGIN - total
    draw_block(d, lines, f, MARGIN*SS, y*SS, c["ink"], "left", 1.05, box_w=box_w*SS)
    return _finish(img)

CONCEPTS = {"editorial": title_editorial, "abstract": title_abstract,
            "cinematic": title_cinematic}


# --------------------------------------------------------------------------- #
#  SLIDE SYSTEM (for a chosen concept)                                         #
# --------------------------------------------------------------------------- #
def blank_bg(cd, concept):
    """Recomposed blank background: same palette/atmosphere as the concept, but
    intentionally quieted and pushed to the edges to leave clean center space."""
    c = cd["colors"]
    if concept == "cinematic":
        img = radial((W, H), _lerp(c["bg"], c["accent"], 0.04), c["bg2"], cx=0.5, cy=0.32, r=1.15)
        img = vignette(img, 0.45); img = grain(img, 8)
    elif concept == "abstract":
        img = base_field(c, "atmos")
        img = motif_layer(img, c, cd["motif"], "quiet")   # subtle, edge-pushed
        img = grain(img, 6)
    else:
        img = base_field(c, "flat"); img = grain(img, 7)
        d = ImageDraw.Draw(img); d.rectangle([0, H-14, W, H], fill=c["accent"])
    return img

def _content_bg(cd, concept):
    """Slightly darker/quieter background for text slides (guaranteed contrast)."""
    c = cd["colors"]
    img = blank_bg(cd, concept)
    scrim = Image.new("RGB", (W, H), c["bg2"])
    return Image.blend(img, scrim, 0.35 if not c["light"] else 0.0)

def point_slide(cd, concept, text, emphasize=None):
    c = cd["colors"]
    bg = _content_bg(cd, concept)
    img = bg.resize((W*SS, H*SS), Image.LANCZOS); d = ImageDraw.Draw(img, "RGBA")
    box_w = W - MARGIN*2
    f, lines, size = fit_lines(d, text.upper(), "black", box_w, 4, 118, 62)
    total = _th(f)*1.04*len(lines)
    y = (H*SS-total)/2
    draw_block(d, lines, f, MARGIN*SS, y, c["ink"], "left", 1.04, box_w=box_w*SS)
    d.rectangle([MARGIN*SS, (y-40*SS), (MARGIN+70)*SS, (y-32*SS)], fill=c["accent"])
    return _finish(img)

def scripture_slide(cd, concept, verse, ref, align="left"):
    c = cd["colors"]
    bg = _content_bg(cd, concept)
    img = bg.resize((W*SS, H*SS), Image.LANCZOS); d = ImageDraw.Draw(img, "RGBA")
    box_w = W - MARGIN*2
    f, lines, size = fit_lines(d, verse, "serif", box_w, 6, 66, 40)
    total = _th(f)*1.22*len(lines)
    y = (H*SS-total)/2 - 30*SS
    endy = draw_block(d, lines, f, MARGIN*SS, y, c["ink"], align, 1.22, box_w=box_w*SS)
    # divider + reference share the alignment (only on the final slide of a passage)
    if ref:
        rf = font("semibold", 26)
        ref_w = _tw_tracked(d, ref.upper(), rf, 6*SS)
        if align == "center":
            dx = MARGIN*SS + (box_w*SS - 90*SS)/2; rx = MARGIN*SS + (box_w*SS-ref_w)/2
        elif align == "right":
            dx = MARGIN*SS + box_w*SS - 90*SS; rx = MARGIN*SS + box_w*SS - ref_w
        else:
            dx = MARGIN*SS; rx = MARGIN*SS
        d.rectangle([dx, endy+34*SS, dx+90*SS, endy+40*SS], fill=c["accent"])
        _draw_tracked(d, ref.upper(), rf, rx, endy+58*SS, c["accent"], 6*SS)
    return _finish(img)


# --------------------------------------------------------------------------- #
#  FULL DECK (flat, finished slides that work anywhere)                        #
# --------------------------------------------------------------------------- #
def build_deck(entries, cd, concept="editorial", align="left"):
    """entries: list from the ProPresenter engine's group_passages(), i.e.
    ('main', text) or ('passage', ref, verse). balance_fn splits long passages.
    Returns list of (label, PIL.Image) - one per finished slide."""
    from math import inf
    slides = [("Title", CONCEPTS.get(concept, title_editorial)(cd))]
    for e in entries:
        if e[0] == "main":
            slides.append(("Point", point_slide(cd, concept, e[1])))
        else:
            _, ref, verse = e
            pieces = _split_passage(verse, 200)
            for j, piece in enumerate(pieces):
                last = (j == len(pieces) - 1)
                slides.append((ref if (last and ref) else "Scripture",
                               scripture_slide(cd, concept, piece, ref if last else "", align)))
    return slides


def _split_passage(text, maxc=200):
    """Sentence-aware split (mirrors the export engine) so flat slides match."""
    text = " ".join(text.split())
    if len(text) <= maxc:
        return [text]
    # manual sentence split (keeps closing quotes after . ? !)
    sents, start, i, n = [], 0, 0, len(text)
    while i < n:
        if text[i] in ".?!":
            j = i + 1
            while j < n and text[j] in "”\"’'":
                j += 1
            if j >= n or text[j] == " ":
                sents.append(text[start:j].strip()); start = j; i = j; continue
        i += 1
    if text[start:].strip():
        sents.append(text[start:].strip())
    out, cur = [], ""
    for s in sents:
        if len(s) > maxc:
            if cur: out.append(cur); cur = ""
            words, c2 = s.split(), ""
            for w in words:
                if c2 and len(c2)+1+len(w) > maxc: out.append(c2); c2 = w
                else: c2 = (c2+" "+w).strip()
            if c2: out.append(c2)
            continue
        if cur and len(cur)+1+len(s) > maxc: out.append(cur); cur = s
        else: cur = (cur+" "+s).strip()
    if cur: out.append(cur)
    if len(out) > 1 and len(out[-1]) < maxc*0.35:
        out[-2] += " " + out[-1]; out.pop()
    return out


# --------------------------------------------------------------------------- #
#  DESIGN-QUALITY CHECK                                                        #
# --------------------------------------------------------------------------- #
def halftone(size, dot, spacing=9, radius=2.4, opacity=34):
    """Fine print/riso dot texture for tactile feel (applied at 1x then upscaled)."""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for yy in range(0, h+spacing, spacing):
        for xx in range(0, w+spacing, spacing):
            d.ellipse([xx-radius, yy-radius, xx+radius, yy+radius], fill=dot+(opacity,))
    return layer

def apply_texture(img, c, kind="grain"):
    w, h = img.size
    if kind in ("halftone", "print"):
        ht = halftone((w, h), c["ink"] if not c["light"] else c["bg2"])
        img = Image.alpha_composite(img.convert("RGBA"), ht).convert("RGB")
    img = grain(img, 8)
    return img

def title_bold(cd, accent_word=None, style="auto", week=None):
    """Type-forward, textural title in the modern church-media vein: oversized
    condensed type filling the frame, a print texture, a structured kicker bar,
    and one accent word. `style`: 'bright' | 'dark' | 'auto'."""
    c = cd["colors"]
    dark = not c["light"] if style == "auto" else (style == "dark")
    # bold flat field (not a timid gradient)
    field = c["bg"] if dark else c["bg"]
    img1 = Image.new("RGB", (W, H), field)
    # subtle tonal vignette to add depth without a smooth gradient
    img1 = Image.blend(img1, vgrad((W, H), _lerp(field,(255,255,255),0.05 if dark else 0.10), _lerp(field,(0,0,0),0.10)), 0.5)
    img1 = apply_texture(img1.convert("RGB"), c, "halftone")
    img = _upscale_bg(img1); d = ImageDraw.Draw(img, "RGBA")
    ml = MARGIN
    top = MARGIN
    # kicker bar (structured metadata)
    if cd["series"]:
        kf = font("black", 22)
        label = cd["series"].upper() + (f"   •   WEEK {week}" if week else "")
        tw = _tw_tracked(d, label, kf, 5*SS)
        d.rectangle([ml*SS, (MARGIN-30)*SS, (ml)*SS+tw+40*SS, (MARGIN+6)*SS], fill=c["accent"])
        on = (20,18,16) if sum(c["accent"])>360 else (245,241,233)
        _draw_tracked(d, label, kf, (ml+20)*SS, (MARGIN-22)*SS, on, 5*SS)
        top = MARGIN + 56
    # oversized title that FILLS the frame (width AND height constrained), tight leading
    box_w = W - MARGIN*2
    avail_h = H - top - MARGIN
    LH = 0.9
    f, lines, size = fit_fill(d, cd["title"].upper(), "cond_bold", box_w, avail_h, 4, 300, 90, LH)
    lh = _th(f)*LH
    total = lh*len(lines)
    y = top*SS + (avail_h*SS - total)/2
    aw = (accent_word or "").upper()
    for i, ln in enumerate(lines):
        x = ml*SS
        if aw and aw in ln.split():
            for wtok in ln.split():
                col = c["accent"] if wtok == aw else c["ink"]
                d.text((x, y+i*lh), wtok, font=f, fill=col)
                x += _tw(d, wtok + " ", f)
        else:
            d.text((ml*SS, y+i*lh), ln, font=f, fill=c["ink"])
    return _finish(img)


def fit_fill(d, text, key, box_w, box_h, max_lines, hi, lo, lh=0.9):
    """Largest size where text wraps within max_lines AND the whole block fits
    box_h. Fills the frame without spilling."""
    for size in range(hi, lo-1, -4):
        f = font(key, size)
        lines = balanced_wrap(d, text, f, box_w*SS, max_lines)
        if not lines:
            continue
        if _th(f)*lh*len(lines) <= box_h*SS:
            return f, lines, size
    f = font(key, lo)
    lines = balanced_wrap(d, text, f, box_w*SS, max_lines+3) or [text]
    return f, lines, lo


def concrete(base, rough=1.0):
    """Grimy, textured field - layered multi-scale noise. For raw/gritty themes."""
    img = Image.new("RGB", (W, H), base)
    for sc, amt, op in [(1, 34, 0.45), (3, 60, 0.30), (9, 95, 0.22)]:
        n = Image.effect_noise((max(1, W//sc), max(1, H//sc)), int(amt*rough)).resize((W, H)).convert("L")
        img = Image.blend(img, ImageChops.overlay(img, Image.merge("RGB", (n, n, n))), op)
    return img

def light_shaft(img, color, x0=0.05, y0=0.0, angle=28, width=0.42, opacity=0.5):
    """A soft diagonal wash of light breaking across the frame (grace/redemption)."""
    w, h = img.size
    band = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(band)
    cx = x0*w; span = width*w
    d.polygon([(cx, 0), (cx+span, 0), (cx+span+math.tan(math.radians(angle))*h, h),
               (cx+math.tan(math.radians(angle))*h, h)], fill=255)
    band = band.filter(ImageFilter.GaussianBlur(w*0.10))
    glow = Image.new("RGB", (w, h), color)
    tinted = ImageChops.multiply(glow, band.point(lambda v: int(v*opacity)).convert("L")
                                 .convert("RGB"))
    return ImageChops.screen(img, tinted)


def title_grit(cd, headline=None):
    """Raw / gritty concept - for themes of filth, sin, brokenness meeting grace.
    Sooty textured field, a shaft of warm light, stark condensed type."""
    c = cd["colors"]
    bg = concrete(c["bg"], rough=1.1)
    bg = light_shaft(bg, c["accent"], x0=0.42, angle=22, width=0.30, opacity=0.55)
    bg = vignette(bg, 0.6)
    img = _upscale_bg(bg); d = ImageDraw.Draw(img, "RGBA")
    ml = MARGIN
    if cd["series"]:
        kf = font("semibold", 24)
        kicker(d, cd["series"], kf, ml*SS, (MARGIN-6)*SS, c["accent"], 9*SS)
    title = headline or cd["title"]
    box_w = W - MARGIN*2 - 40
    f, lines, size = fit_lines(d, title.upper(), "cond_bold", box_w, 3, 220, 120)
    total = _th(f)*0.96*len(lines)
    y = (H*SS-total)/2 + 10*SS
    y = draw_block(d, lines, f, ml*SS, y, c["ink"], "left", 0.96, box_w=box_w*SS)
    d.rectangle([ml*SS, y+22*SS, (ml+120)*SS, y+30*SS], fill=c["accent"])
    out = img.resize((W, H), Image.LANCZOS)
    return grain(out, 5)


# --------------------------------------------------------------------------- #
#  IMAGE INTELLIGENCE - build a direction FROM an uploaded image              #
# --------------------------------------------------------------------------- #
def analyze_image(path):
    """Study an uploaded image: dominant palette, most usable accent, overall
    scheme (light/dark), and the calmest/darkest region for text (text-safe
    zone as fractions x,y,w,h)."""
    im = Image.open(path).convert("RGB")
    small = im.resize((160, 90))
    q = small.quantize(6).convert("RGB")
    counts = sorted(q.getcolors(), reverse=True)
    palette = [c for _, c in counts]
    # accent = most saturated palette colour
    def sat(rgb):
        h_, s_, v_ = colorsys.rgb_to_hsv(*[v/255 for v in rgb]); return s_*v_
    accent = max(palette, key=sat)
    lum = lambda c: 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]
    base = min(palette, key=lum)
    ink = (245, 241, 233) if lum(base) < 120 else (24, 24, 28)
    # text-safe zone: scan a coarse grid, find the largest low-variance region
    g = small.convert("L")
    gw, gh = 16, 9
    cell = g.resize((gw, gh))
    px = list(cell.getdata())
    best = None
    for y in range(gh-3):
        for x in range(gw-6):
            vals = [px[(y+j)*gw + (x+i)] for j in range(3) for i in range(6)]
            var = max(vals)-min(vals); mean = sum(vals)/len(vals)
            score = var + abs(mean-40)*0.3     # prefer calm + darker areas
            if best is None or score < best[0]:
                best = (score, x/gw, y/gh, 6/gw, 3/gh)
    zone = best[1:]
    return dict(palette=palette, accent=accent, base=base, ink=ink,
                light=lum(base) >= 120, zone=zone)

def direction_from_image(path, sermon):
    """Creative direction driven by an uploaded image, not a keyword table."""
    a = analyze_image(path)
    colors = dict(bg=a["base"], bg2=tuple(max(0, v-14) for v in a["base"]),
                  ink=a["ink"], sub=tuple((a["ink"][i]+a["base"][i])//2 for i in range(3)),
                  accent=a["accent"], light=a["light"])
    return dict(palette="from-image", motif="none", mood="bespoke",
                colors=colors, series=sermon.get("series", ""),
                title=sermon.get("title", ""), zone=a["zone"], src=path)


def soft_scrim(img, darken=True, strength=0.34):
    """Mild wash, strongest through the vertical middle, so live text is legible
    over an uploaded textured/photo background without hiding the art."""
    w, h = img.size
    m = Image.new("L", (1, h))
    for y in range(h):
        t = abs(y - h/2)/(h/2)
        m.putpixel((0, y), int(255*((1-t)*0.85 + 0.12)))
    m = m.resize((w, h)).filter(ImageFilter.GaussianBlur(h*0.06))
    overlay = Image.new("RGB", (w, h), (0, 0, 0) if darken else (250, 248, 244))
    return Image.composite(overlay, img, m.point(lambda p: int(p*strength)))

def _shadow_text(d, xy, s, f, fill, dark, off=4):
    d.text((xy[0]+off, xy[1]+off), s, font=f, fill=dark)
    d.text(xy, s, font=f, fill=fill)

def point_on_image(blank_im, a, text, accent_word=None):
    """A bold main-point slide composed over an uploaded blank background,
    palette-matched, with a legibility scrim + shadow."""
    ink = (26, 24, 28) if a["light"] else (245, 242, 235)
    dark = (0, 0, 0, 150)
    base = soft_scrim(blank_im, darken=not a["light"], strength=0.36)
    img = base.resize((W*SS, H*SS), Image.LANCZOS); d = ImageDraw.Draw(img, "RGBA")
    ml = MARGIN; box_w = W - MARGIN*2
    f, lines, size = fit_fill(d, text.upper(), "cond_bold", box_w, H-2*MARGIN-70, 4, 150, 66, 0.98)
    lh = _th(f)*0.98; total = lh*len(lines); y = (H*SS-total)/2 + 14*SS
    d.rectangle([ml*SS, y-46*SS, (ml+80)*SS, y-38*SS], fill=a["accent"])
    aw = (accent_word or "").upper()
    for i, ln in enumerate(lines):
        x = ml*SS
        if aw and aw in ln.split():
            for w in ln.split():
                col = a["accent"] if w == aw else ink
                _shadow_text(d, (x, y+i*lh), w, f, col, dark, off=4*SS)
                x += _tw(d, w + " ", f)
        else:
            _shadow_text(d, (ml*SS, y+i*lh), ln, f, ink, dark, off=4*SS)
    return _finish(img)

def scripture_on_image(blank_im, a, verse, ref, align="left"):
    ink = (26, 24, 28) if a["light"] else (244, 241, 234)
    dark = (0, 0, 0, 140)
    base = soft_scrim(blank_im, darken=not a["light"], strength=0.40)
    img = base.resize((W*SS, H*SS), Image.LANCZOS); d = ImageDraw.Draw(img, "RGBA")
    box_w = W - MARGIN*2
    f, lines, size = fit_fill(d, verse, "geo_reg", box_w, H-2*MARGIN-140, 6, 60, 34, 1.24)
    lh = _th(f)*1.24; total = lh*len(lines); y = (H*SS-total)/2 - 26*SS
    for i, ln in enumerate(lines):
        w = _tw(d, ln, f)
        lx = MARGIN*SS + (box_w*SS-w)/2 if align == "center" else (MARGIN*SS + box_w*SS - w if align == "right" else MARGIN*SS)
        _shadow_text(d, (lx, y+i*lh), ln, f, ink, dark, off=3*SS)
    endy = y + total
    if ref:
        rf = font("semibold", 26); rw = _tw_tracked(d, ref.upper(), rf, 6*SS)
        if align == "center":
            dx = MARGIN*SS+(box_w*SS-90*SS)/2; rx = MARGIN*SS+(box_w*SS-rw)/2
        elif align == "right":
            dx = MARGIN*SS+box_w*SS-90*SS; rx = MARGIN*SS+box_w*SS-rw
        else:
            dx = MARGIN*SS; rx = MARGIN*SS
        d.rectangle([dx, endy+34*SS, dx+90*SS, endy+40*SS], fill=a["accent"])
        _draw_tracked(d, ref.upper(), rf, rx, endy+58*SS, a["accent"], 6*SS)
    return _finish(img)

def deck_from_uploads(title_path, blank_path, entries, align="left"):
    """Best-for-pastors path: use their uploaded TITLE as slide 1, and build
    coordinating point/Scripture slides on their uploaded BLANK background."""
    title_slide = _cover(Image.open(title_path))
    blank_im = _cover(Image.open(blank_path))
    a = analyze_image(blank_path)
    # carry the brand accent from the (richer) title art into the content slides
    at = analyze_image(title_path)
    def _sat(rgb):
        import colorsys; h, s, v = colorsys.rgb_to_hsv(*[x/255 for x in rgb]); return s*v
    if _sat(at["accent"]) > _sat(a["accent"]) + 0.08:
        a["accent"] = at["accent"]
    slides = [("Title", title_slide)]
    for e in entries:
        if e[0] == "main":
            slides.append(("Point", point_on_image(blank_im, a, e[1])))
        else:
            _, ref, verse = e
            for j, piece in enumerate(_split_passage(verse, 200)):
                last = (j == len(_split_passage(verse, 200)) - 1)
                slides.append((ref if (last and ref) else "Scripture",
                               scripture_on_image(blank_im, a, piece, ref if last else "", align)))
    return slides


def _cover(im):
    """Cover-fit any image to the 16:9 canvas (no distortion)."""
    im = im.convert("RGB"); iw, ih = im.size
    s = max(W/iw, H/ih)
    im = im.resize((round(iw*s), round(ih*s)), Image.LANCZOS)
    x = (im.width-W)//2; y = (im.height-H)//2
    return im.crop((x, y, x+W, y+H))

def _region_lum(im, box):
    r = im.crop(box).convert("L")
    return sum(r.getdata())/(r.width*r.height)

def directional_scrim(img, side="left", darken=True, strength=0.6):
    """Fade a dark (or light) wash toward one side so text stays legible over
    an arbitrary photo - exactly what a designer does by hand."""
    w, h = img.size
    row = Image.new("L", (w, 1))
    for x in range(w):
        t = x/(w-1); v = (1-t) if side == "left" else t
        row.putpixel((x, 0), int(255*(v**1.4)))
    mask = row.resize((w, h)).filter(ImageFilter.GaussianBlur(w*0.05))
    overlay = Image.new("RGB", (w, h), (0, 0, 0) if darken else (250, 248, 244))
    return Image.composite(overlay, img, mask.point(lambda p: int(p*strength)))

def title_on_upload(path, sermon, week=None):
    """Design a title slide AROUND an uploaded image: read its palette + the
    calmest area, put the title in the clear space with a legibility scrim, and
    pull the accent colour from the image itself."""
    im = _cover(Image.open(path))
    a = analyze_image(path)
    zx, zy, zw, zh = a["zone"]
    left = (zx + zw/2) < 0.5                     # place text on the calm side
    side = "left" if left else "right"
    lum = _region_lum(im, (int((0.04 if left else 0.5)*W), int(0.2*H),
                           int((0.5 if left else 0.96)*W), int(0.92*H)))
    light_bg = lum > 132
    ink = (26, 24, 28) if light_bg else (246, 243, 236)
    accent = a["accent"]
    if light_bg and 0.2126*accent[0]+0.7152*accent[1]+0.0722*accent[2] > 150:
        accent = tuple(int(v*0.6) for v in accent)      # keep accent legible on light
    im = directional_scrim(im, side, darken=not light_bg, strength=0.62)
    img = im.resize((W*SS, H*SS), Image.LANCZOS); d = ImageDraw.Draw(img, "RGBA")
    # text column clamped to the calm side, inside safe margins
    col_x = MARGIN if left else int(W*0.46)
    col_w = int((0.5 if left else 0.54)*W) - MARGIN + (0 if left else 0)
    col_w = max(300, min(col_w, W - MARGIN - col_x))
    top = MARGIN
    if sermon.get("series"):
        kf = font("black", 22)
        lab = sermon["series"].upper() + (f"   •   WEEK {week}" if week else "")
        tw = _tw_tracked(d, lab, kf, 5*SS)
        d.rectangle([col_x*SS, (MARGIN-30)*SS, col_x*SS+tw+40*SS, (MARGIN+6)*SS], fill=accent)
        on = (20,18,16) if sum(accent) > 360 else (245,241,233)
        _draw_tracked(d, lab, kf, (col_x+20)*SS, (MARGIN-22)*SS, on, 5*SS)
        top = MARGIN + 56
    avail_h = H - top - MARGIN
    f, lines, size = fit_fill(d, sermon["title"].upper(), "cond_bold", col_w, avail_h, 5, 200, 70, 0.92)
    lh = _th(f)*0.92; total = lh*len(lines); y = top*SS + (avail_h*SS-total)/2
    for i, ln in enumerate(lines):
        d.text((col_x*SS, y+i*lh), ln, font=f, fill=ink)
    d.rectangle([col_x*SS, y+total+22*SS, (col_x+100)*SS, y+total+30*SS], fill=accent)
    return _finish(img), dict(side=side, light_bg=light_bg, accent=accent, zone=a["zone"])


def quality_check(img, meta):
    """Inspect a rendered slide; return list of issue strings (empty = clean)."""
    issues = []
    small = img.resize((160, 90)).convert("L")
    px = list(small.getdata())
    # crude contrast in the central text band
    band = [px[y*160+x] for y in range(30, 60) for x in range(16, 144)]
    if band:
        rng = max(band) - min(band)
        if rng < 60:
            issues.append("low contrast in text area")
    ml = meta.get("lines", 0)
    if ml > meta.get("max_lines", 6):
        issues.append("too many lines / overcrowded")
    if meta.get("size", 99) <= meta.get("min_size", 0):
        issues.append("text shrunk to floor - consider shorter copy or new layout")
    if meta.get("align") and meta.get("ref_align") and meta["align"] != meta["ref_align"]:
        issues.append("scripture and reference alignment mismatch")
    return issues
