#!/usr/bin/env python3
"""Sermon -> ProPresenter web app for TC Church.
Upload a color-coded sermon .docx + a background image + a title image,
get back a zip with the .pro and the images ready to drop into ProPresenter.
"""
import os, re, sys, subprocess, tempfile, zipfile, io
from flask import Flask, request, send_file, render_template_string, abort

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024   # 64 MB uploads

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Sermon Slides</title>
<style>
 :root{--navy:#101c33;--orange:#e8843f;--cream:#f5f1e7}
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
   background:var(--navy);color:var(--cream);min-height:100vh}
 .wrap{max-width:640px;margin:0 auto;padding:40px 22px 80px}
 h1{font-size:30px;margin:0 0 6px} .sub{opacity:.75;margin:0 0 28px;line-height:1.5}
 label{display:block;margin:20px 0 7px;font-weight:600}
 input[type=text],select{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #33415e;
   background:#0b1424;color:var(--cream);font-size:16px}
 input[type=file]{width:100%;padding:12px;border-radius:10px;border:1px dashed #3a4a6a;
   background:#0b1424;color:var(--cream)}
 .hint{font-size:13px;opacity:.65;margin-top:5px}
 button{margin-top:30px;width:100%;padding:15px;border:0;border-radius:12px;background:var(--orange);
   color:#111;font-size:17px;font-weight:700;cursor:pointer}
 .card{background:#0b1424;border:1px solid #24304a;border-radius:16px;padding:26px}
 .err{background:#3a1414;border:1px solid #7a2a2a;padding:14px;border-radius:10px;margin-bottom:20px}
 code{background:#0b1424;padding:1px 6px;border-radius:6px}
 .foot{opacity:.6;font-size:13px;margin-top:26px;line-height:1.6}
</style></head><body><div class=wrap>
 <h1>Sermon &rarr; ProPresenter Slides</h1>
 <p class=sub>Upload a <b>color-coded</b> sermon (points in blue <code>0070C0</code>,
   Scripture in red <code>FF0000</code>) plus a background image and a title image.
   You&rsquo;ll get a <code>.pro</code> ready for ProPresenter 7.</p>
 {% if error %}<div class=err>{{ error }}</div>{% endif %}
 <form class=card method=post action="/generate" enctype="multipart/form-data">
   <label>Sermon title</label>
   <input type=text name=title placeholder="e.g. What Are We Doing Here - Christ" required>
   <label>Text alignment</label>
   <select name=align>
     <option value=center selected>Center (default)</option>
     <option value=left>Left</option>
     <option value=right>Right</option>
   </select>
   <label>Color-coded sermon (.docx)</label>
   <input type=file name=docx accept=".docx" required>
   <label>Background image</label>
   <input type=file name=background accept="image/*" required>
   <div class=hint>Fills every point &amp; Scripture slide. Text color is auto-chosen for it.</div>
   <label>Title image</label>
   <input type=file name=title_img accept="image/*" required>
   <div class=hint>Used alone as the opening slide.</div>
   <button type=submit>Build my slides</button>
 </form>
 <p class=foot>You get a zip: the <code>.pro</code>, a <code>ProPresenter Media</code> folder with your
   two images, and a short read-me. Put that folder in your <b>Documents</b>, then import the
   <code>.pro</code>. Requires the BebasNeue &amp; Helvetica fonts installed.</p>
</div></body></html>"""

def safe(name):
    name = re.sub(r'[\\/:*?"<>|]+', ' ', name).strip()
    return re.sub(r'\s+', ' ', name) or "Sermon"

@app.route("/")
def index():
    return render_template_string(PAGE, error=None)

@app.route("/healthz")
def healthz():
    return "ok"

@app.route("/generate", methods=["POST"])
def generate():
    title = safe(request.form.get("title", "").strip())
    align = request.form.get("align", "center")
    if align not in ("center", "left", "right"):
        align = "center"
    docx = request.files.get("docx")
    bg = request.files.get("background")
    ti = request.files.get("title_img")
    if not (docx and bg and ti and docx.filename):
        return render_template_string(PAGE, error="Please choose all three files."), 400

    with tempfile.TemporaryDirectory() as tmp:
        dpath = os.path.join(tmp, "sermon.docx"); docx.save(dpath)
        bgp = os.path.join(tmp, "background.png"); bg.save(bgp)
        tip = os.path.join(tmp, "title.png"); ti.save(tip)
        outpro = os.path.join(tmp, f"{title}.pro")
        rel = f"ProPresenter Media/{title}"
        bg_mac = f"/Users/pastor/Documents/{rel}/background.png"
        ti_mac = f"/Users/pastor/Documents/{rel}/title.png"
        env = dict(os.environ, PP_PORTABLE="1")
        try:
            r = subprocess.run(
                [sys.executable, os.path.join(HERE, "propresenter_generator.py"),
                 dpath, title, outpro, bgp, tip, bg_mac, ti_mac, align],
                cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return render_template_string(PAGE, error="Timed out building the slides."), 500
        if r.returncode != 0 or not os.path.exists(outpro):
            msg = (r.stderr or r.stdout or "Unknown error").strip().splitlines()[-1:]
            return render_template_string(PAGE, error="Couldn't build slides. " + " ".join(msg)), 500

        readme = (
            "HOW TO USE THESE SLIDES\n"
            "=======================\n\n"
            "1. Move the 'ProPresenter Media' folder (in this zip) into your Mac's\n"
            "   Documents folder. So you end up with:\n"
            f"      ~/Documents/{rel}/background.png\n"
            f"      ~/Documents/{rel}/title.png\n\n"
            "2. In ProPresenter 7, delete any previous copy of this presentation.\n\n"
            f"3. Import '{title}.pro' (drag it in, or File > Import).\n\n"
            "Notes:\n"
            " - Needs the BebasNeue and Helvetica fonts installed on this Mac.\n"
            " - If ProPresenter asks to locate media, point it at the two images\n"
            "   in the ProPresenter Media folder above.\n")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(outpro, f"{title}.pro")
            z.write(bgp, f"{rel}/background.png")
            z.write(tip, f"{rel}/title.png")
            z.writestr("READ ME FIRST.txt", readme)
        mem.seek(0)
        return send_file(mem, mimetype="application/zip", as_attachment=True,
                         download_name=f"{title} - ProPresenter.zip")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
