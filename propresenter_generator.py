#!/usr/bin/env python3
"""TC Church - image-aware ProPresenter 7 (.pro) generator (standalone)."""
import os, sys, re, uuid, glob
HERE=os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE,"ppgen"),HERE):
    if _p not in sys.path: sys.path.insert(0,_p)
def _load():
    global P,cue_pb2,action_pb2,slide_pb2,G,B
    import presentation_pb2 as P
    import cue_pb2,action_pb2,slide_pb2
    import graphicsData_pb2 as G
    import basicTypes_pb2 as B
try: _load()
except Exception:
    from grpc_tools import protoc
    PROTO=os.path.join(HERE,"proto"); PP=os.path.join(HERE,"ppgen"); os.makedirs(PP,exist_ok=True)
    protoc.main([""]+["-I"+PROTO,"--python_out="+PP]+[os.path.basename(f) for f in glob.glob(os.path.join(PROTO,"*.proto"))])
    _load()
SLIDE_W,SLIDE_H=1920.0,1080.0
def new_uuid():
    u=B.UUID(); u.string=str(uuid.uuid4()); return u
CP={0x2018:"91",0x2019:"92",0x201C:"93",0x201D:"94",0x2013:"96",0x2014:"97",0x2026:"85",0x00A0:"a0",0x2022:"95"}
def rtf_escape(s):
    out=[]
    for ch in s:
        o=ord(ch)
        if ch=='\\': out.append('\\\\')
        elif ch=='{': out.append('\\{')
        elif ch=='}': out.append('\\}')
        elif o in CP: out.append("\\'"+CP[o])
        elif o<128: out.append(ch)
        else:
            c=o if o<32768 else o-65536; out.append('\\u%d?'%c)
    return ''.join(out)
def rect_path(path):
    path.closed=True
    for (x,y) in [(0,0),(1,0),(1,1),(0,1)]:
        bp=path.points.add()
        bp.point.x=float(x); bp.point.y=float(y); bp.q0.x=float(x); bp.q0.y=float(y); bp.q1.x=float(x); bp.q1.y=float(y)
    path.shape.type=G.Graphics.Path.Shape.TYPE_RECTANGLE
def make_slide(elements,black_bg):
    s=slide_pb2.Slide(); s.uuid.CopyFrom(new_uuid()); s.size.width=SLIDE_W; s.size.height=SLIDE_H
    if black_bg:
        s.background_color.red=0; s.background_color.green=0; s.background_color.blue=0; s.background_color.alpha=1.0
    else: s.background_color.alpha=0.0
    for e in elements: s.elements.append(e)
    return s
BOOK=r'(?:[1-3]\s*)?[A-Z][a-zA-Z]+'
CIT=re.compile(BOOK+r'\.?\s+\d+:\d+(?:\s*[-–]\s*\d+)?')
W,H=SLIDE_W,SLIDE_H

_QUOTE = re.compile(r'[“"](.+?)[”"]', re.DOTALL)


_OPEN_Q = "“\"‘"


def drop_leadin(verse):
    """Remove a spoken lead-in: the clause before the first opening quote when
    that clause ends with a colon (e.g. 'Paul responded with:' / 'he puts it
    well in chapter 3:'). Biblical intros end with a comma ('Peter replied,'),
    so those are kept."""
    k = next((i for i, ch in enumerate(verse) if ch in _OPEN_Q), -1)
    if k <= 0:
        return verse
    lead = verse[:k].rstrip()
    if lead.endswith(":") and len(lead) <= 80:
        return verse[k:]
    return verse


def parse_scripture(text):
    """Return (REFERENCE upper-cased, verse in ORIGINAL sentence case).
    Robust to a quoted verse plus a trailing parenthetical citation, e.g.
    Matthew 7:24-27 - "..." (Matthew 7:24-25, NIV): uses the FIRST citation as
    the reference and the FIRST quoted block as the verse."""
    t = ' '.join(text.split())
    cits = list(CIT.finditer(t))
    qm = _QUOTE.search(t)
    if cits and qm and len(qm.group(1)) > 15:
        ref = cits[0].group(0)
        verse = qm.group(1)
    elif cits:
        m = cits[-1]; ref = m.group(0)
        qm2 = re.search(r'[“"](.+?)[”"]\s*$', t[m.end():]) or re.search(r'[“"](.+)$', t[m.end():])
        verse = qm2.group(1) if qm2 else t[m.end():].lstrip(' –-:') or t
    else:
        ref = ''; verse = t
    verse = drop_leadin(verse.strip())          # remove spoken lead-in clause
    verse = verse.strip().strip('“”"').strip()
    # Drop leaked citation labels like "(Verse 13)" / "Verse 44:".
    verse = re.sub(r'\(?\s*[Vv]erse\s+\d{1,3}\s*:?\s*\)?', '', verse)
    # Strip verse-number / footnote markers ONLY. A marker is a 1-3 digit run at
    # a verse boundary: at the start, or right after end punctuation (with or
    # without a space), e.g. "...prayer. 43 Everyone" or "...hearts,47 praising".
    # Numbers that are part of the wording (e.g. "the 12 disciples") are kept.
    verse = re.sub(r'^\s*\d{1,3}\s+', '', verse)
    verse = re.sub(r'(?<=[.,;:!?”"’])\s*\d{1,3}(?=\s)', '', verse)
    verse = re.sub(r'\s{2,}', ' ', verse).strip()
    verse = verse.replace(' / ', '\n')
    return ref.upper().replace('  ', ' '), verse
FILL = G.Media.DrawingProperties.SCALE_BEHAVIOR_FILL
MIDC = G.Media.DrawingProperties.SCALE_ALIGNMENT_MIDDLE_CENTER

def classify_color(hx):
    """Tolerant color match, so slightly different shades still count.
      'red'  -> Scripture (e.g. FF0000, EE0000, C00000)
      'blue' -> main point (e.g. 0070C0, royal blues)
    Purple (7030A0) and orange (BF4E14) return None, so references and
    application text are never mistaken for points or Scripture."""
    hx = (hx or "").strip().lstrip("#")
    if len(hx) != 6:
        return None
    try:
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    except ValueError:
        return None
    if r >= 150 and g <= 50 and b <= 60:          # strong red (not orange)
        return "red"
    if r <= 90 and b >= 110 and b >= g - 20:       # blue (not purple/navy)
        return "blue"
    return None


def extract_exact(docx_path):
    """Points come from BLUE-classified runs only (not the whole paragraph).
    Scripture = any paragraph containing RED-classified text (whole paragraph)."""
    import zipfile
    from xml.etree import ElementTree as ET
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    def qn(t): return f"{{{W}}}{t}"
    root = ET.fromstring(zipfile.ZipFile(docx_path).read("word/document.xml"))
    items = []
    for p in root.iter(qn("p")):
        runs = []
        for r in p.iter(qn("r")):
            rpr = r.find(qn("rPr")); col = None
            if rpr is not None:
                c = rpr.find(qn("color"))
                if c is not None:
                    col = (c.get(qn("val")) or "").upper()
            txt = "".join(t.text or "" for t in r.iter(qn("t")))
            if txt:
                runs.append((col, txt))
        if not runs:
            continue
        kinds = {classify_color(c) for c, _ in runs if c}
        if "red" in kinds:
            full = " ".join("".join(t for _, t in runs).split())
            if full:
                items.append(("scripture", full))
            continue
        blue = " ".join("".join(t for c, t in runs if classify_color(c) == "blue").split())
        if blue:
            items.append(("main", blue))
    return items

# ---- refined layout (1920x1080) --------------------------------------------
# Points: big BebasNeue caps, centered, brush motif beneath.
PT_POINT = 96
POINT_BOX   = (160.0, 180.0, 1600.0, 720.0)      # dead-center on the slide
# Scripture: sentence-case centered verse, brush divider, tracked orange ref.
PT_VERSE, PT_REF = 58, 34
VERSE_MID   = (210.0, 180.0, 1500.0, 720.0)       # dead-center (no line/ref)
VERSE_BOX   = (210.0, 176.0, 1500.0, 470.0)       # raised (final slide w/ ref)
SCRIP_BRUSH = (795.0, 704.0, 330.0, 16.0)
REF_BOX     = (210.0, 748.0, 1500.0, 84.0)


ALIGN_TAG  = {"left": "\\ql", "center": "\\qc", "right": "\\qr"}


def _p_enum(align):
    P = G.Graphics.Text.Attributes.Paragraph
    return {"left": P.ALIGNMENT_LEFT, "center": P.ALIGNMENT_CENTER,
            "right": P.ALIGNMENT_RIGHT}[align]


def make_rtf_align(text, fs_halfpt, font, swiss, rgb, align, tracking=0, bold=False):
    """RTF with selectable horizontal alignment (ql/qc/qr), multi-line aware,
    optional character tracking (\\expndtw twips), and optional bold."""
    fdef = "\\fswiss" if swiss else "\\fnil"
    qtag = ALIGN_TAG[align]
    trk = ("\\expnd%d\\expndtw%d " % (tracking // 5, tracking)) if tracking else ""
    bt = "\\b " if bold else ""
    r, g, b = rgb
    cc = "\\c%d\\c%d\\c%d" % (round(r/255*100000), round(g/255*100000), round(b/255*100000))
    header = ("{\\rtf1\\ansi\\ansicpg1252\\cocoartf2870\n"
              "\\cocoatextscaling0\\cocoaplatform0{\\fonttbl\\f0%s\\fcharset0 %s;}\n"
              "{\\colortbl;\\red255\\green255\\blue255;\\red%d\\green%d\\blue%d;}\n"
              "{\\*\\expandedcolortbl;;\\csgenericrgb%s;}\n"
              "\\deftab1680\n"
              "\\pard\\pardeftab1680%s\\pardirnatural\\partightenfactor0\n\n"
              "\\f0%s\\fs%d \\cf2 %s\\CocoaLigature0 "
              % (fdef, font, r, g, b, cc, qtag, bt, fs_halfpt, trk))
    lines = text.split("\n"); parts = [header]
    for i, ln in enumerate(lines):
        if i > 0:
            parts.append("\\\n\\pard\\pardeftab1680%s\\pardirnatural\\partightenfactor0\n%s\\cf2 %s" % (qtag, bt, trk))
        parts.append(rtf_escape(ln))
    parts.append("}")
    return "".join(parts).encode("utf-8")


def divider_pos(align):
    """Place the divider under the text edge matching the alignment."""
    x, y, w, h = SCRIP_BRUSH
    if align == "left":
        x = VERSE_MID[0]
    elif align == "right":
        x = VERSE_MID[0] + VERSE_MID[2] - w
    return (x, y, w, h)


def divider_element(rgb, pos):
    """Native tapered ellipse used as an orange brush-style divider.
    A native shape (not an image) so it always renders — no media path."""
    el = slide_pb2.Slide.Element(); el.info = 4
    ge = el.element; ge.uuid.CopyFrom(new_uuid()); ge.name = "Divider"
    ge.bounds.origin.x = pos[0]; ge.bounds.origin.y = pos[1]
    ge.bounds.size.width = pos[2]; ge.bounds.size.height = pos[3]
    ge.opacity = 1.0
    # rectangle-bounds path, rendered as an ellipse -> tapered lens/stroke look
    ge.path.closed = True
    for (x, y) in [(0, 0), (1, 0), (1, 1), (0, 1)]:
        bp = ge.path.points.add()
        bp.point.x = float(x); bp.point.y = float(y)
        bp.q0.x = float(x); bp.q0.y = float(y)
        bp.q1.x = float(x); bp.q1.y = float(y)
    ge.path.shape.type = G.Graphics.Path.Shape.TYPE_ELLIPSE
    f = ge.fill; f.enable = True
    f.color.red = rgb[0] / 255.0; f.color.green = rgb[1] / 255.0
    f.color.blue = rgb[2] / 255.0; f.color.alpha = 1.0
    ge.stroke.enable = False
    return el


# ---------- luminance-driven color choice -----------------------------------
def analyze(path):
    """Return (mean_luminance 0-255) of the region where text sits."""
    from PIL import Image
    im = Image.open(path).convert("RGB").resize((80, 45))
    x0, x1, y0, y1 = 12, 68, 9, 36            # central text zone
    tot = n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = im.getpixel((x, y))
            tot += 0.2126 * r + 0.7152 * g + 0.0722 * b
            n += 1
    return tot / n


def pick_palette(bg_lum):
    """Choose a modern text palette based on how dark/light the background is."""
    if bg_lum < 110:                       # dark background -> warm near-white
        body = (245, 241, 231)             # warm white
        accent = (232, 132, 63)            # series orange (reference accent)
        shadow_rgb = (0, 0, 0); shadow_op = 0.55
    else:                                  # light background -> deep navy ink
        body = (16, 28, 51)                # deep navy
        accent = (200, 86, 17)             # burnt orange
        shadow_rgb = (255, 255, 255); shadow_op = 0.0
    return body, accent, shadow_rgb, shadow_op


def img_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return float(im.width), float(im.height)


# ---------- element builders ------------------------------------------------
def bg_media_element(rel_path, natural, name="Background"):
    """Full-slide image fill (scale to fill), placed as the bottom layer."""
    el = slide_pb2.Slide.Element(); el.info = 0
    ge = el.element; ge.uuid.CopyFrom(new_uuid()); ge.name = name
    ge.bounds.origin.x = 0.0; ge.bounds.origin.y = 0.0
    ge.bounds.size.width = W; ge.bounds.size.height = H
    ge.opacity = 1.0
    rect_path(ge.path)
    f = ge.fill; f.enable = True
    m = f.media
    m.uuid.CopyFrom(new_uuid())
    m.url.platform = B.URL.PLATFORM_MACOS
    if not os.environ.get("PP_PORTABLE"):
        m.url.absolute_string = "file://" + rel_path["abs"].replace(" ", "%20")
    if rel_path["docrel"] is not None:          # portable path when under Documents
        m.url.local.root = B.URL.LocalRelativePath.ROOT_USER_DOCUMENTS
        m.url.local.path = rel_path["docrel"]
    d = m.image.drawing
    d.scale_behavior = FILL
    d.scale_alignment = MIDC
    d.natural_size.width = natural[0]; d.natural_size.height = natural[1]
    ge.stroke.enable = False
    return el


def text_element(name, text, bounds, pt, font, swiss, align, info, rgb, shadow,
                 tracking=0, bold=False, shrink=False):
    el = slide_pb2.Slide.Element(); el.info = info
    ge = el.element; ge.uuid.CopyFrom(new_uuid()); ge.name = name
    ge.bounds.origin.x = bounds[0]; ge.bounds.origin.y = bounds[1]
    ge.bounds.size.width = bounds[2]; ge.bounds.size.height = bounds[3]
    ge.opacity = 1.0
    rect_path(ge.path)
    ge.fill.enable = False
    ge.stroke.enable = False; ge.stroke.width = 3.0
    # subtle drop shadow for legibility over any background
    srgb, sop = shadow
    if sop > 0:
        sh = ge.shadow
        sh.enable = True
        sh.style = G.Graphics.Shadow.STYLE_DROP
        sh.angle = 315.0; sh.offset = 5.0; sh.radius = 9.0
        sh.opacity = sop
        sh.color.red = srgb[0] / 255.0; sh.color.green = srgb[1] / 255.0
        sh.color.blue = srgb[2] / 255.0; sh.color.alpha = 1.0
    t = ge.text
    t.rtf_data = make_rtf_align(text, pt * 2, font, swiss, rgb, align, tracking, bold)
    t.vertical_alignment = G.Graphics.Text.VERTICAL_ALIGNMENT_MIDDLE
    t.scale_behavior = (G.Graphics.Text.SCALE_BEHAVIOR_SCALE_FONT_DOWN if shrink
                        else G.Graphics.Text.SCALE_BEHAVIOR_NONE)
    at = t.attributes
    at.font.name = font; at.font.size = float(pt); at.font.bold = bold
    at.font.family = ("Bebas Neue" if font.startswith("Bebas") else "Helvetica")
    at.text_solid_fill.red = rgb[0] / 255.0; at.text_solid_fill.green = rgb[1] / 255.0
    at.text_solid_fill.blue = rgb[2] / 255.0; at.text_solid_fill.alpha = 1.0
    at.paragraph_style.alignment = _p_enum(align)
    at.paragraph_style.line_height_multiple = 1.0
    at.paragraph_style.text_list.SetInParent()
    return el


# ---------- passage grouping + balanced chunking ----------------------------
def group_passages(items):
    """Merge CONSECUTIVE scripture paragraphs into one passage so the reference
    lands once, on the final slide. A new citation (different from the current
    one) starts a new passage; a point slide always ends the current passage.
    Returns a list of ('main', text) and ('passage', ref, combined_verse)."""
    out, buf, cur_ref = [], [], ""

    def flush():
        nonlocal buf, cur_ref
        if buf:
            out.append(("passage", cur_ref, " ".join(buf)))
            buf, cur_ref = [], ""

    for typ, txt in items:
        if typ == "main":
            flush(); out.append(("main", txt)); continue
        ref, verse = parse_scripture(txt)
        if buf and ref and cur_ref and ref != cur_ref:
            flush()
        if not buf:
            cur_ref = ref
        elif ref and not cur_ref:
            cur_ref = ref
        if verse.strip():
            buf.append(verse.strip())
    flush()
    return out


def _sentences(text):
    """Split into sentences, keeping any closing quote after . ? !"""
    out, start, i, n = [], 0, 0, len(text)
    while i < n:
        if text[i] in ".?!":
            j = i + 1
            while j < n and text[j] in "”\"’'":
                j += 1
            if j >= n or text[j] == " ":
                out.append(text[start:j].strip()); start = j; i = j; continue
        i += 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _hard_split(s, maxc):
    """Fallback: split one very long sentence at word boundaries."""
    out, cur = [], ""
    for w in s.split():
        if cur and len(cur) + 1 + len(w) > maxc:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def balance_chunks(text, maxc=210):
    """Pack whole SENTENCES onto each slide so breaks land at full stops, never
    mid-clause. A single over-long sentence is word-split as a last resort, and
    a stray short tail is merged back so no slide has just a few words."""
    text = " ".join(text.split())
    if len(text) <= maxc:
        return [text]
    chunks, cur = [], ""
    for s in _sentences(text):
        if len(s) > maxc:
            if cur:
                chunks.append(cur); cur = ""
            chunks.extend(_hard_split(s, maxc)); continue
        if cur and len(cur) + 1 + len(s) > maxc:
            chunks.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) < maxc * 0.35:
        chunks[-2] = chunks[-2] + " " + chunks[-1]; chunks.pop()
    return chunks


# ---------- build -----------------------------------------------------------
def build(items, title, out_path, bg_ref, bg_nat, title_ref, title_nat,
          body, accent, shadow, align="center"):
    pres = P.Presentation()
    pres.uuid.CopyFrom(new_uuid()); pres.name = title
    pres.application_info.platform = B.ApplicationInfo.PLATFORM_MACOS
    pres.application_info.platform_version.major_version = 14
    pres.application_info.application = B.ApplicationInfo.APPLICATION_PROPRESENTER
    pres.application_info.application_version.major_version = 21
    pres.application_info.application_version.minor_version = 3
    pres.application_info.application_version.build = "352518178"
    pres.background.color.alpha = 1.0
    pres.content_destination = P.Presentation.CONTENT_DESTINATION_GLOBAL
    cg = pres.cue_groups.add()
    cg.group.uuid.CopyFrom(new_uuid()); cg.group.name = title.upper(); cg.group.color.alpha = 1.0

    def add_slide(elements, label):
        cue = cue_pb2.Cue(); cue.uuid.CopyFrom(new_uuid()); cue.isEnabled = True
        cue.completion_action_type = cue_pb2.Cue.COMPLETION_ACTION_TYPE_LAST
        act = cue.actions.add(); act.uuid.CopyFrom(new_uuid()); act.isEnabled = True
        act.type = action_pb2.Action.ACTION_TYPE_PRESENTATION_SLIDE
        act.label.text = label; act.label.color.alpha = 1.0
        sl = make_slide(elements, False)     # transparent bg; media covers it
        act.slide.presentation.base_slide.CopyFrom(sl)
        pres.cues.append(cue); cg.cue_identifiers.append(cue.uuid)

    # 1) Title slide = title image ALONE
    add_slide([bg_media_element(title_ref, title_nat, "Title Image")], "Title")

    # 2) Points + scripture, over the background image (rendered front-to-back,
    #    so the background media element is always LAST / behind the text).
    for entry in group_passages(items):
        if entry[0] == "main":
            txt = entry[1]
            txt_el = text_element("", txt.replace(" / ", "\n").upper(),
                                  POINT_BOX, PT_POINT, "Helvetica",
                                  True, align, 2, body, shadow,
                                  bold=True, shrink=True)
            add_slide([txt_el, bg_media_element(bg_ref, bg_nat)], "Point")
        else:
            _, ref, verse = entry
            pieces = balance_chunks(verse, 200)
            for j, piece in enumerate(pieces):
                last = (j == len(pieces) - 1)
                vbox = VERSE_BOX if (last and ref) else VERSE_MID
                els = [text_element("Verse", piece, vbox, PT_VERSE,
                                    "Helvetica", True, align, 3, body, shadow,
                                    shrink=True)]
                # Divider + reference ONLY on the final slide of the passage.
                if last and ref:
                    els.append(divider_element(accent, divider_pos(align)))
                    els.append(text_element("Reference", ref, REF_BOX, PT_REF,
                                            "Helvetica", True, align, 3, accent,
                                            shadow, tracking=200))
                els.append(bg_media_element(bg_ref, bg_nat))   # background LAST
                add_slide(els, ref or "Scripture")

    with open(out_path, "wb") as f:
        f.write(pres.SerializeToString())
    return len(pres.cues)


def ref_for(mac_abs):
    """mac_abs = the image's real absolute path on the user's Mac.
    docrel is the path relative to ~/Documents when the file lives there
    (portable), else None (absolute path only)."""
    marker = "/Documents/"
    i = mac_abs.find(marker)
    docrel = mac_abs[i + len(marker):] if i != -1 else None
    return {"abs": mac_abs, "docrel": docrel}


if __name__ == "__main__":
    if len(sys.argv) < 8:
        print(__doc__); sys.exit(1)
    # *_read: readable (sandbox) paths for analysis; *_mac: real Mac paths
    docx, title, out, bg_read, title_read, bg_mac, title_mac = sys.argv[1:8]
    align = (sys.argv[8].lower() if len(sys.argv) > 8 else "center")
    if align not in ("left", "center", "right"):
        sys.exit("align must be one of: left, center, right")

    bg_lum = analyze(bg_read)
    body, accent, srgb, sop = pick_palette(bg_lum)
    shadow = (srgb, sop)

    bg_ref = ref_for(bg_mac)
    title_ref = ref_for(title_mac)
    bg_nat = img_size(bg_read)
    title_nat = img_size(title_read)

    items = extract_exact(docx)
    n = build(items, title, out, bg_ref, bg_nat, title_ref, title_nat,
              body, accent, shadow, align)
    print(f"Wrote {out}: {n} slides ({align} aligned)")
    print(f"  bg luminance={bg_lum:.0f}  body={body}  accent={accent}  shadow_opacity={sop}")
