#!/usr/bin/env python3
"""Sermon -> ProPresenter web app (clean, minimal UI)."""
import os, re, sys, subprocess, tempfile, zipfile, io
from flask import Flask, request, send_file, render_template_string

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Sermon Slides</title>
<style>
 :root{--ink:#1d1d1f;--sub:#6e6e73;--line:#d2d2d7;--line2:#e8e8ed;--bg:#fbfbfd;--accent:#0071e3;--accent2:#0060c8}
 *{box-sizing:border-box;-webkit-font-smoothing:antialiased}
 html,body{margin:0}
 body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Inter","Helvetica Neue",Arial,sans-serif;
   background:var(--bg);color:var(--ink);line-height:1.5}
 .wrap{max-width:600px;margin:0 auto;padding:72px 24px 96px}
 .eyebrow{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 14px}
 h1{font-size:44px;line-height:1.07;letter-spacing:-.022em;font-weight:600;margin:0 0 14px}
 .lede{font-size:19px;color:var(--sub);margin:0 0 40px;letter-spacing:-.01em}
 .card{background:#fff;border:1px solid var(--line2);border-radius:20px;padding:32px}
 label.fld{display:block;font-size:13px;font-weight:600;letter-spacing:.01em;color:var(--ink);margin:0 0 8px}
 input[type=text]{width:100%;padding:13px 15px;font-size:16px;color:var(--ink);background:#fff;
   border:1px solid var(--line);border-radius:12px;outline:none;transition:border .15s,box-shadow .15s}
 input[type=text]:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(0,113,227,.15)}
 .row{margin:0 0 24px}
 .seg{display:flex;gap:4px;background:#f0f0f3;border-radius:12px;padding:4px}
 .seg input{position:absolute;opacity:0;pointer-events:none}
 .seg label{flex:1;text-align:center;padding:9px 0;font-size:15px;color:var(--sub);border-radius:9px;cursor:pointer;transition:.15s}
 .seg input:checked+label{background:#fff;color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.12);font-weight:500}
 .file{display:flex;align-items:center;gap:14px;width:100%;padding:16px;margin:0 0 12px;
   border:1px solid var(--line);border-radius:14px;cursor:pointer;background:#fff;transition:.15s;position:relative}
 .file:hover{border-color:#b9b9c0}
 .file.drag{border-color:var(--accent);background:#f5faff}
 .file.has{border-color:#c7c7cc;background:#fbfbfd}
 .file input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}
 .ico{flex:0 0 40px;height:40px;border-radius:10px;background:#f2f2f5;display:flex;align-items:center;justify-content:center;color:var(--sub)}
 .file.has .ico{background:#eaf4ff;color:var(--accent)}
 .ft{flex:1;min-width:0}
 .fname{font-size:15px;font-weight:500;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .fhint{font-size:13px;color:var(--sub);margin-top:1px}
 .pick{flex:0 0 auto;font-size:14px;font-weight:500;color:var(--accent)}
 button{margin-top:14px;width:100%;padding:15px;border:0;border-radius:14px;background:var(--accent);
   color:#fff;font-size:17px;font-weight:500;letter-spacing:-.01em;cursor:pointer;transition:.15s}
 button:hover{background:var(--accent2)}
 button:active{transform:scale(.99)}
 .foot{font-size:13px;color:var(--sub);margin:22px 2px 0;line-height:1.6}
 .err{background:#fff1f1;border:1px solid #ffd0d0;color:#b3261e;padding:13px 15px;border-radius:12px;margin:0 0 22px;font-size:14px}
 .overlay{position:fixed;inset:0;background:rgba(251,251,253,.92);backdrop-filter:blur(6px);
   display:none;align-items:center;justify-content:center;flex-direction:column;z-index:9}
 .overlay.on{display:flex}
 .spin{width:34px;height:34px;border:3px solid #e2e2e7;border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite}
 @keyframes sp{to{transform:rotate(360deg)}}
 .ol-t{margin-top:18px;font-size:17px;font-weight:500}
 .ol-s{margin-top:5px;font-size:14px;color:var(--sub)}
 @media(max-width:520px){h1{font-size:34px}.wrap{padding:44px 18px 72px}.card{padding:22px}}
</style></head><body>
<div class=wrap>
 <p class=eyebrow>ProPresenter slide builder</p>
 <h1>Sermon to slides, in one step.</h1>
 <p class=lede>Upload a color-coded sermon with a background and title image. Get finished ProPresenter&nbsp;7 slides.</p>
 {% if error %}<div class=err>{{ error }}</div>{% endif %}
 <form class=card method=post action="/generate" enctype="multipart/form-data" id=form>
  <input type=hidden name=dl_token id=dl_token>
  <div class=row>
   <label class=fld for=title>Sermon title</label>
   <input type=text id=title name=title placeholder="What Are We Doing Here - Christ" required>
  </div>
  <div class=row>
   <label class=fld>Text alignment</label>
   <div class=seg>
    <input type=radio id=al_l name=align value=left><label for=al_l>Left</label>
    <input type=radio id=al_c name=align value=center checked><label for=al_c>Center</label>
    <input type=radio id=al_r name=align value=right><label for=al_r>Right</label>
   </div>
  </div>
  <label class=file id=f_docx>
   <input type=file name=docx accept=".docx" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7 stroke-linecap=round stroke-linejoin=round><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/><line x1=9 y1=13 x2=15 y2=13/><line x1=9 y1=17 x2=13 y2=17/></svg></span>
   <span class=ft><span class="fname" data-def="Color-coded sermon">Color-coded sermon</span><span class=fhint>Word document (.docx)</span></span>
   <span class=pick>Choose</span>
  </label>
  <label class=file id=f_bg>
   <input type=file name=background accept="image/*" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7 stroke-linecap=round stroke-linejoin=round><rect x=3 y=3 width=18 height=18 rx=2/><circle cx=8.5 cy=8.5 r=1.5/><path d="M21 15l-5-5L5 21"/></svg></span>
   <span class=ft><span class="fname" data-def="Background image">Background image</span><span class=fhint>Fills every slide</span></span>
   <span class=pick>Choose</span>
  </label>
  <label class=file id=f_title>
   <input type=file name=title_img accept="image/*" required>
   <span class=ico><svg width=20 height=20 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=1.7 stroke-linecap=round stroke-linejoin=round><rect x=3 y=3 width=18 height=18 rx=2/><path d="M3 15l4-4 5 5"/><path d="M14 14l2-2 5 5"/></svg></span>
   <span class=ft><span class="fname" data-def="Title image">Title image</span><span class=fhint>Opening slide</span></span>
   <span class=pick>Choose</span>
  </label>
  <button type=submit>Build slides</button>
 </form>
 <p class=foot>Points come from blue text, Scripture from red. You&rsquo;ll get a zip with the <code>.pro</code> and a media folder&mdash;drop it in Documents, then import. Needs BebasNeue and Helvetica installed.</p>
</div>
<div class=overlay id=overlay>
 <div class=spin></div>
 <div class=ol-t>Building your slides&hellip;</div>
 <div class=ol-s>This can take up to a minute the first time.</div>
</div>
<script>
 document.querySelectorAll('.file').forEach(function(box){
  var input=box.querySelector('input[type=file]');
  var name=box.querySelector('.fname');
  input.addEventListener('change',function(){
   if(input.files.length){name.textContent=input.files[0].name;box.classList.add('has');}
   else{name.textContent=name.dataset.def;box.classList.remove('has');}
  });
  ['dragenter','dragover'].forEach(function(ev){box.addEventListener(ev,function(e){e.preventDefault();box.classList.add('drag');});});
  ['dragleave','drop'].forEach(function(ev){box.addEventListener(ev,function(e){e.preventDefault();box.classList.remove('drag');});});
  box.addEventListener('drop',function(e){if(e.dataTransfer.files.length){input.files=e.dataTransfer.files;input.dispatchEvent(new Event('change'));}});
 });
 var form=document.getElementById('form'),overlay=document.getElementById('overlay');
 form.addEventListener('submit',function(){
  var t=Math.random().toString(36).slice(2);
  document.getElementById('dl_token').value=t;
  overlay.classList.add('on');
  var iv=setInterval(function(){
   if(document.cookie.indexOf('dl_done='+t)!==-1){clearInterval(iv);overlay.classList.remove('on');document.cookie='dl_done=; Max-Age=0; path=/';}
  },500);
  setTimeout(function(){clearInterval(iv);overlay.classList.remove('on');},120000);
 });
</script>
</body></html>"""

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
    token = request.form.get("dl_token", "x")
    docx = request.files.get("docx"); bg = request.files.get("background"); ti = request.files.get("title_img")
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
            "HOW TO USE THESE SLIDES\n=======================\n\n"
            "EASIEST WAY:\n"
            "  1. Double-click 'Install images (double-click).command'. It places the\n"
            "     background and title images where ProPresenter needs them.\n"
            "     (If macOS blocks it, right-click the file -> Open -> Open.)\n"
            "  2. In ProPresenter 7, delete any previous copy of this presentation,\n"
            f"     then import '{title}.pro'.\n\n"
            "MANUAL WAY (if you prefer):\n"
            "  1. Move the 'ProPresenter Media' folder into your Mac's Documents folder:\n"
            f"       ~/Documents/{rel}/background.png\n       ~/Documents/{rel}/title.png\n"
            f"  2. Delete any old copy in ProPresenter, then import '{title}.pro'.\n\n"
            "Needs BebasNeue and Helvetica fonts installed. If ProPresenter asks to\n"
            "locate media, point it at the two images in the ProPresenter Media folder.\n")
        installer = (
            "#!/bin/bash\n"
            "cd \"$(dirname \"$0\")\"\n"
            "DEST=\"$HOME/Documents/ProPresenter Media\"\n"
            "echo \"Installing sermon background images...\"\n"
            "mkdir -p \"$DEST\"\n"
            "cp -R \"ProPresenter Media/.\" \"$DEST/\"\n"
            "echo \"\"\n"
            "echo \"Done. Images are now in: $DEST\"\n"
            "echo \"\"\n"
            "echo \"Now open ProPresenter, delete any old copy of this presentation,\"\n"
            "echo \"and import the .pro file that came in this folder.\"\n"
            "echo \"\"\n"
            "echo \"You can close this window.\"\n")
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(outpro, f"{title}.pro")
            z.write(bgp, f"{rel}/background.png")
            z.write(tip, f"{rel}/title.png")
            z.writestr("READ ME FIRST.txt", readme)
            zi = zipfile.ZipInfo("Install images (double-click).command")
            zi.external_attr = (0o755 << 16)   # make it executable/double-clickable
            z.writestr(zi, installer)
        mem.seek(0)
        resp = send_file(mem, mimetype="application/zip", as_attachment=True,
                         download_name=f"{title} - ProPresenter.zip")
        resp.set_cookie("dl_done", token, max_age=120)
        return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
