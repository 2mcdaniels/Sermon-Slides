#!/usr/bin/env python3
"""Sermon -> designed ProPresenter deck (website).
Pastor uploads a color-coded sermon + a title graphic + a blank background.
Returns a zip with (1) finished flat slide images that work anywhere, and
(2) an editable ProPresenter .pro with a one-click image installer."""
import os, re, sys, io, gc, zipfile, subprocess, tempfile
from flask import Flask, request, send_file, render_template_string

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("DS_FONT_DIR", os.path.join(HERE, "fonts"))
os.environ.setdefault("DS_SS", "1")  # native-res render to stay within 512MB
sys.path.insert(0, HERE)
import design_studio as ds
import propresenter_generator as sp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 96 * 1024 * 1024

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Sermon Slides</title>
<style>
 :root{--ink:#1d1d1f;--sub:#6e6e73;--line:#d2d2d7;--line2:#e8e8ed;--bg:#fbfbfd;--accent:#0071e3;--a2:#0060c8}
 *{box-sizing:border-box;-webkit-font-smoothing:antialiased}html,body{margin:0}
 body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Inter",Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
 .wrap{max-width:600px;margin:0 auto;padding:64px 24px 88px}
 .eyebrow{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 12px}
 h1{font-size:40px;line-height:1.08;letter-spacing:-.022em;font-weight:600;margin:0 0 12px}
 .lede{font-size:18px;color:var(--sub);margin:0 0 34px}
 .card{background:#fff;border:1px solid var(--line2);border-radius:20px;padding:30px}
 label.fld{display:block;font-size:13px;font-weight:600;margin:0 0 8px}.row{margin:0 0 22px}
 input[type=text]{width:100%;padding:13px 15px;font-size:16px;border:1px solid var(--line);border-radius:12px;outline:none}
 input[type=text]:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(0,113,227,.15)}
 .seg{display:flex;gap:4px;background:#f0f0f3;border-radius:12px;padding:4px}
 .seg input{position:absolute;opacity:0;pointer-events:none}
 .seg label{flex:1;text-align:center;padding:9px 0;font-size:15px;color:var(--sub);border-radius:9px;cursor:pointer}
 .seg input:checked+label{background:#fff;color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.12);font-weight:500}
 .file{display:flex;align-items:center;gap:13px;padding:15px;margin:0 0 12px;border:1px solid var(--line);border-radius:14px;cursor:pointer;position:relative}
 .file input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}
 .ico{flex:0 0 40px;height:40px;border-radius:10px;background:#f2f2f5;color:var(--sub);display:flex;align-items:center;justify-content:center}
 .file.has .ico{background:#eaf4ff;color:var(--accent)} .ft{flex:1;min-width:0}
 .fname{font-size:15px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.fhint{font-size:13px;color:var(--sub)}
 .pick{font-size:14px;font-weight:500;color:var(--accent)}
 button{margin-top:14px;width:100%;padding:15px;border:0;border-radius:14px;background:var(--accent);color:#fff;font-size:17px;font-weight:500;cursor:pointer}
 button:hover{background:var(--a2)}.foot{font-size:13px;color:var(--sub);margin:20px 2px 0;line-height:1.6}
 .err{background:#fff1f1;border:1px solid #ffd0d0;color:#b3261e;padding:13px 15px;border-radius:12px;margin:0 0 20px;font-size:14px}
 .overlay{position:fixed;inset:0;background:rgba(251,251,253,.93);backdrop-filter:blur(6px);display:none;align-items:center;justify-content:center;flex-direction:column;z-index:9}
 .overlay.on{display:flex}.spin{width:34px;height:34px;border:3px solid #e2e2e7;border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite}
 @keyframes sp{to{transform:rotate(360deg)}}.ol-t{margin-top:18px;font-size:17px;font-weight:500}.ol-s{margin-top:5px;font-size:14px;color:var(--sub)}
 @media(max-width:520px){h1{font-size:32px}.wrap{padding:40px 18px}.card{padding:22px}}
</style></head><body><div class=wrap>
 <p class=eyebrow>Sermon slide builder</p>
 <h1>Designed slides from your sermon.</h1>
 <p class=lede>Upload a color-coded sermon plus your title graphic and a blank background. Get a finished, on-brand deck.</p>
 {% if error %}<div class=err>{{ error }}</div>{% endif %}
 <form class=card method=post action="/generate" enctype="multipart/form-data" id=form>
  <input type=hidden name=dl_token id=dl_token>
  <div class=row><label class=fld for=title>Sermon title</label><input type=text id=title name=title placeholder="What Are We Doing Here?" required></div>
  <div class=row><label class=fld for=series>Series (optional)</label><input type=text id=series name=series placeholder="A Series About the Church"></div>
  <div class=row><label class=fld>Scripture alignment</label>
   <div class=seg><input type=radio id=al_l name=align value=left checked><label for=al_l>Left</label>
   <input type=radio id=al_c name=align value=center><label for=al_c>Center</label>
   <input type=radio id=al_r name=align value=right><label for=al_r>Right</label></div></div>
  <label class=file id=f_docx><input type=file name=docx accept=".docx" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7 stroke-linecap=round><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/></svg></span>
   <span class=ft><span class=fname data-def="Color-coded sermon">Color-coded sermon</span><span class=fhint>Word document (.docx)</span></span><span class=pick>Choose</span></label>
  <label class=file id=f_title><input type=file name=title_img accept="image/*" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7><rect x=3 y=3 width=18 height=18 rx=2/><path d="M3 15l4-4 5 5"/></svg></span>
   <span class=ft><span class=fname data-def="Title graphic">Title graphic</span><span class=fhint>Your finished series art (slide 1)</span></span><span class=pick>Choose</span></label>
  <label class=file id=f_bg><input type=file name=background accept="image/*" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7><rect x=3 y=3 width=18 height=18 rx=2/></svg></span>
   <span class=ft><span class=fname data-def="Blank background">Blank background</span><span class=fhint>Point & Scripture slides are built on this</span></span><span class=pick>Choose</span></label>
  <button type=submit>Build my deck</button>
 </form>
 <p class=foot>You get finished slide images that work in ProPresenter, Planning Center, or Keynote &mdash; plus an editable ProPresenter file with a one-click image installer. Points come from blue text, Scripture from red.</p>
</div>
<div class=overlay id=overlay><div class=spin></div><div class=ol-t>Designing your deck&hellip;</div><div class=ol-s>This can take up to a minute the first time.</div></div>
<script>
 document.querySelectorAll('.file').forEach(function(b){var inp=b.querySelector('input');var n=b.querySelector('.fname');
  inp.addEventListener('change',function(){if(inp.files.length){n.textContent=inp.files[0].name;b.classList.add('has')}else{n.textContent=n.dataset.def;b.classList.remove('has')}});});
 var form=document.getElementById('form'),ov=document.getElementById('overlay');
 form.addEventListener('submit',function(){var t=Math.random().toString(36).slice(2);document.getElementById('dl_token').value=t;ov.classList.add('on');
  var iv=setInterval(function(){if(document.cookie.indexOf('dl_done='+t)!==-1){clearInterval(iv);ov.classList.remove('on');document.cookie='dl_done=; Max-Age=0; path=/'}},500);
  setTimeout(function(){clearInterval(iv);ov.classList.remove('on')},170000);});
</script></body></html>"""

def safe(n):
    n = re.sub(r'[\\/:*?"<>|]+', ' ', n).strip(); return re.sub(r'\s+', ' ', n) or "Sermon"

@app.route("/")
def index(): return render_template_string(PAGE, error=None)
@app.route("/healthz")
def healthz(): return "ok"

def _finish_zip(z, pro_ok, outpro, title, rel, bp, tp, installer, readme):
    if pro_ok:
        z.write(outpro, f"Editable ProPresenter/{title}.pro")
        z.write(bp, f"Editable ProPresenter/{rel}/background.png")
        z.write(tp, f"Editable ProPresenter/{rel}/title.png")
        zi = zipfile.ZipInfo("Editable ProPresenter/Install images (double-click).command")
        zi.external_attr = (0o755 << 16); z.writestr(zi, installer)
    z.writestr("READ ME FIRST.txt", readme)


@app.route("/generate", methods=["POST"])
def generate():
    title = safe(request.form.get("title", "").strip())
    series = request.form.get("series", "").strip()
    align = request.form.get("align", "left")
    if align not in ("left", "center", "right"): align = "left"
    token = request.form.get("dl_token", "x")
    docx = request.files.get("docx"); tim = request.files.get("title_img"); bg = request.files.get("background")
    if not (docx and tim and bg and docx.filename):
        return render_template_string(PAGE, error="Please choose all three files."), 400
    with tempfile.TemporaryDirectory() as tmp:
        dp = os.path.join(tmp, "s.docx"); docx.save(dp)
        tp = os.path.join(tmp, "title.png"); tim.save(tp)
        bp = os.path.join(tmp, "background.png"); bg.save(bp)
        try:
            entries = sp.group_passages(sp.extract_exact(dp))
        except Exception as e:
            return render_template_string(PAGE, error="Couldn't read the sermon: " + str(e)), 500
        if not entries:
            return render_template_string(PAGE, error="No blue points or red Scripture found - is the sermon color-coded?"), 400
        # editable .pro (uploaded title + blank; portable media refs)
        outpro = os.path.join(tmp, f"{title}.pro")
        rel = f"ProPresenter Media/{title}"
        env = dict(os.environ, PP_PORTABLE="1")
        pro_ok = False
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, "propresenter_generator.py"),
                dp, title, outpro, bp, tp,
                f"/Users/pastor/Documents/{rel}/background.png",
                f"/Users/pastor/Documents/{rel}/title.png", align],
                cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
            pro_ok = (r.returncode == 0 and os.path.exists(outpro))
        except Exception:
            pro_ok = False
        installer = ("#!/bin/bash\ncd \"$(dirname \"$0\")\"\nDEST=\"$HOME/Documents/ProPresenter Media\"\n"
            "echo \"Installing background images...\"\nmkdir -p \"$DEST\"\ncp -R \"ProPresenter Media/.\" \"$DEST/\"\n"
            "echo \"Done. Now import the .pro in this folder into ProPresenter.\"\n")
        readme = ("WHAT'S IN THIS ZIP\n==================\n\n"
            "FINISHED SLIDES  (folder: Slides)\n"
            "  Ready-made 1920x1080 slide images. These always work: drop them into\n"
            "  ProPresenter (or Planning Center / Keynote) as media. Nothing to install.\n\n"
            "EDITABLE PROPRESENTER  (folder: Editable ProPresenter)\n"
            "  1. Double-click 'Install images (double-click).command'.\n"
            "  2. In ProPresenter, delete any old copy, then import the .pro.\n"
            "  (Editable text, but needs the images installed as above.)\n")
        mem = io.BytesIO()
        try:
            with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
                i = 0
                for lab, im in ds.deck_from_uploads_iter(tp, bp, entries, align):
                    i += 1
                    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=88)
                    z.writestr(f"Slides/{i:02d} {safe(lab)}.jpg", b.getvalue())
                    del im, b; gc.collect()
                _finish_zip(z, pro_ok, outpro, title, rel, bp, tp, installer, readme)
        except Exception as e:
            return render_template_string(PAGE, error="Design step failed: " + str(e)), 500
        mem.seek(0)
        resp = send_file(mem, mimetype="application/zip", as_attachment=True,
                         download_name=f"{title} - Slides.zip")
        resp.set_cookie("dl_done", token, max_age=200)
        return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
