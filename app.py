import streamlit as st
from streamlit.components.v1 import html
from PIL import Image
import os, base64, json, uuid
from io import BytesIO

# Optional back camera component
try:
    from streamlit_back_camera_input import back_camera_input
    HAS_BACK_CAM = True
except ImportError:
    HAS_BACK_CAM = False

# Layout config
st.set_page_config(layout="wide")
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Logo
try:
    img_logo = Image.open("logo.png")
    st.image(img_logo, width=250)
except Exception:
    pass

# Panel definitions (cm)
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}

# Load textures
textures = {}
materials = []
for folder in [os.getcwd(), os.path.join(os.getcwd(), "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Photo input
source_opts = ["Upload"]
if HAS_BACK_CAM:
    source_opts.append("Back Camera")
source_opts.append("Camera")
source = st.radio("Photo source", source_opts, horizontal=True)

photo = None
if source == "Upload":
    up = st.file_uploader("Upload photo", type=["png","jpg","jpeg"])
    if up: photo = up.read()
elif source == "Back Camera":
    cam = back_camera_input()
    if cam: photo = cam.getvalue()
else:
    cam2 = st.camera_input("Take photo")
    if cam2: photo = cam2.getvalue()
if not photo:
    st.stop()

# Encode image and scale
b64 = base64.b64encode(photo).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", 100.0, 2000.0, 400.0)
scale = 800.0 / wall_width

# Sidebar controls
st.sidebar.header("Configuratie")
sz_add = st.sidebar.selectbox("Grootte", list(sizes.keys()))
mat_add = st.sidebar.selectbox("Materiaal", materials)
if st.sidebar.button("Voeg paneel toe"):
    st.session_state.panels.append({
        "id": uuid.uuid4().hex[:6],
        "x": 100, "y": 100,
        "rotation": 0,
        "size": sz_add, "mat": mat_add
    })
    st.experimental_rerun()

sel_rot = st.sidebar.selectbox("Roteer paneel", ["--"] + [p["id"] for p in st.session_state.panels])
if st.sidebar.button("Rotate 90°") and sel_rot != "--":
    for p in st.session_state.panels:
        if p["id"] == sel_rot:
            p["rotation"] = (p.get("rotation", 0) + 90) % 360
            break
    st.experimental_rerun()

sel_del = st.sidebar.selectbox("Verwijder paneel", ["--"] + [p["id"] for p in st.session_state.panels])
if st.sidebar.button("Verwijder") and sel_del != "--":
    st.session_state.panels = [p for p in st.session_state.panels if p["id"] != sel_del]
    st.experimental_rerun()

# Prepare divs & scripts
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p["size"]]
    w_px, h_px = w_cm * scale, h_cm * scale
    rad = "50%" if p["size"] == "MOON" else "0%"
    img_data = textures.get(p["mat"], "")
    style = (
        f"top:{p['x']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px;"
        f"transform:rotate({p['rotation']}deg); border-radius:{rad};"
        f"background:url(data:image/jpeg;base64,{img_data}) repeat;"
    )
    divs.append(f"<div class='panel' id='{p['id']}' style='{style}'></div>")
    scripts.append(f"initDrag('{p['id']}');")

# JS for drag & export
js_code_sync = r"""
(function(){
  const arr = [];
  document.querySelectorAll('.panel').forEach(el => {
    const m = el.style.transform.match(/rotate\(([-0-9.]+)deg\)/);
    arr.push({
      id: el.id,
      x: parseInt(el.style.left) || 0,
      y: parseInt(el.style.top) || 0,
      rotation: m ? parseFloat(m[1]) : 0
    });
  });
  return JSON.stringify(arr);
})()
"""
drag_js = r"""
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  const startDrag=(x,y)=>{dragging=true; dx=x-el.offsetLeft; dy=y-el.offsetTop; if(!window._z)window._z=10; el.style.zIndex=++window._z};
  const moveDrag=(x,y)=>{if(dragging){el.style.left=(x-dx)+'px'; el.style.top=(y-dy)+'px'}};
  const endDrag=()=>{dragging=false};
  el.onmousedown=e=>{e.preventDefault(); startDrag(e.clientX,e.clientY)};
  window.onmousemove=e=>moveDrag(e.clientX,e.clientY);
  window.onmouseup=endDrag;
  el.ontouchstart=e=>{let t=e.touches[0]; startDrag(t.clientX,t.clientY)};
  window.ontouchmove=e=>{let t=e.touches[0]; moveDrag(t.clientX,t.clientY)};
  window.ontouchend=endDrag;
}
"""
export_js = r"""
document.getElementById('exportBtn').onclick = () => {
  const img = document.querySelector('#wall img');
  const W = img.naturalWidth || img.width;
  const H = img.naturalHeight || img.height;
  const sc = W/800;
  const cnv = document.createElement('canvas'); cnv.width=W; cnv.height=H;
  const ctx = cnv.getContext('2d');
  const base = new Image(); base.src = img.src;
  base.onload = () => {
    ctx.drawImage(base,0,0,W,H);
    let cnt = 0;
    document.querySelectorAll('.panel').forEach(el => {
      const nm = new Image(); nm.src=el.style.background.split(',')[1];
      nm.onload = () => {
        const pw=el.offsetWidth*sc, ph=el.offsetHeight*sc;
        const px=parseFloat(el.style.left)*sc, py=parseFloat(el.style.top)*sc;
        let a=0; const m=/rotate\(([-0-9.]+)deg\)/.exec(el.style.transform);
        if(m) a=parseFloat(m[1])*Math.PI/180;
        ctx.save(); ctx.translate(px+pw/2,py+ph/2); ctx.rotate(a);
        const pat=ctx.createPattern(nm,'repeat'); ctx.fillStyle=pat;
        if(el.style.borderRadius==='50%') {let r=Math.max(pw,ph)/2; ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill()} else ctx.fillRect(-pw/2,-ph/2,pw,ph);
        ctx.restore(); if(++cnt===document.querySelectorAll('.panel').length){const url=cnv.toDataURL();
          const a=document.createElement('a'); a.href=url; a.download='composition.png'; a.click();}
      };
    });
  };
};
"""

# Render canvas
html(f"""
<style>
  #wall {{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem}}
  .panel {{position:absolute;cursor:move}}
</style>
<button id='exportBtn'>Genereer compositie</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{b64}' style='width:800px' />
  {''.join(divs)}
</div>
<script>
{drag_js}
{''.join(scripts)}
{export_js}
</script>
""", height=880)

# Sync positions after render
try:
    from streamlit_js_eval import streamlit_js_eval
    res = streamlit_js_eval(js_expressions=[js_code_sync], key="sync_after")
    raw = res[0] if isinstance(res, list) else res
    if isinstance(raw, str) and raw.strip():
        positions = json.loads(raw)
        for pos in positions:
            for p in st.session_state.panels:
                if p["id"] == pos.get("id"):
                    p["x"] = pos.get("x", p["x"])
                    p["y"] = pos.get("y", p["y"])
                    p["rotation"] = pos.get("rotation", p.get("rotation",0))
except Exception:
    pass

# Share session code
st.write("Share session code:")
st.text_area("Base64", base64.b64encode(json.dumps({"panels":st.session_state.panels}).encode()).decode(), height=100)
