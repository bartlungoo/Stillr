import streamlit as st
from PIL import Image
import os, base64, json, uuid
from io import BytesIO

# Optional back camera component
try:
    from streamlit_back_camera_input import back_camera_input
    HAS_BACK_CAM = True
except ImportError:
    HAS_BACK_CAM = False

# Ensure wide layout and minimal padding
st.set_page_config(layout="wide")
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Display logo if exists
if os.path.exists("logo.png"):
    st.image("logo.png", width=250)

# Panel size definitions (cm)
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}

# Load textures into memory
textures, materials = {}, []
root = os.getcwd()
for folder in [root, os.path.join(root, "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Initialize session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Photo input selection
targets = ["Upload"]
if HAS_BACK_CAM:
    targets.append("Back Camera")
targets.append("Camera")
source = st.radio("Photo source", targets, horizontal=True)

photo_bytes = None
if source == "Upload":
    upload_file = st.file_uploader("Upload photo", type=["jpg","jpeg","png"])
    if upload_file:
        photo_bytes = upload_file.read()
elif source == "Back Camera":
    img = back_camera_input()
    if img:
        photo_bytes = img.getvalue()
else:
    cap = st.camera_input("Take photo")
    if cap:
        photo_bytes = cap.getvalue()

if not photo_bytes:
    st.info("Upload of maak een foto om te beginnen.")
    st.stop()

# Encode and compute scale
img_b64 = base64.b64encode(photo_bytes).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)
scale = 800.0 / wall_width

# Sync drag positions (requires streamlit-js-eval)
has_eval = False
try:
    from streamlit_js_eval import streamlit_js_eval
    has_eval = True
except ImportError:
    st.sidebar.warning("Installeer streamlit-js-eval>=0.1.2 voor drag-persistentie.")

if has_eval:
    js_code = r"""(function(){
  const arr = [];
  document.querySelectorAll('.panel').forEach(el=>{
    const m = el.style.transform.match(/rotate\(([-0-9.]+)deg\)/);
    arr.push({
      id: el.id,
      x: parseInt(el.style.left) || 0,
      y: parseInt(el.style.top) || 0,
      rotation: m ? parseFloat(m[1]) : 0
    });
  });
  return JSON.stringify(arr);
})()"""
    try:
        res = streamlit_js_eval(js_expressions=[js_code], key="sync_pos")
        raw = res[0] if isinstance(res, list) else res
        positions = json.loads(raw)
        for pos in positions:
            for p in st.session_state.panels:
                if p["id"] == pos.get("id"):
                    if pos.get("x") is not None: p["x"] = pos["x"]
                    if pos.get("y") is not None: p["y"] = pos["y"]
                    if pos.get("rotation") is not None: p["rotation"] = pos["rotation"]
    except Exception as e:
        st.error(f"Kon paneelposities niet synchroniseren: {e}")

# Sidebar controls: toevoegen, roteren, verwijderen
st.sidebar.header("Configuratie")
with st.sidebar.form("add_panel"):
    sz = st.selectbox("Grootte", list(sizes.keys()))
    mat = st.selectbox("Materiaal", materials)
    if st.form_submit_button("Voeg paneel toe"):
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6],
            "x": 100, "y": 100,
            "rotation": 0,
            "size": sz, "mat": mat
        })
with st.sidebar.form("rotate_panel"):
    sel = st.selectbox("Roteer paneel", ["--"] + [p["id"] for p in st.session_state.panels])
    if st.form_submit_button("Rotate 90°") and sel != "--":
        for p in st.session_state.panels:
            if p["id"] == sel:
                p["rotation"] = (p.get("rotation",0) + 90) % 360
with st.sidebar.form("delete_panel"):
    sel2 = st.selectbox("Verwijder paneel", ["--"] + [p["id"] for p in st.session_state.panels])
    if st.form_submit_button("Verwijder") and sel2 != "--":
        st.session_state.panels = [p for p in st.session_state.panels if p["id"] != sel2]

# Build HTML panels and JS inits
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p["size"]]
    w_px, h_px = w_cm * scale, h_cm * scale
    radius = "50%" if p["size"] == "MOON" else "0%"
    img_data = textures[p["mat"]]
    style = (
        f"top:{p['y']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px;"
        f"transform:rotate({p['rotation']}deg); border-radius:{radius};"
        f"background:url(data:image/jpeg;base64,{img_data}) repeat;")
    divs.append(f"<div class='panel' id='{p['id']}' style='{style}'></div>")
    scripts.append(f"initDrag('{p['id']}');")

# Define JS for drag & export

drag_js = """
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

export_js = """
document.getElementById('exportBtn').onclick=()=>{
  const img=document.querySelector('#wall img'); const W=img.naturalWidth||img.width; const H=img.naturalHeight||img.height;
  const sc=W/800; const cnv=document.createElement('canvas'); cnv.width=W; cnv.height=H;
  const ctx=cnv.getContext('2d');
  const base=new Image(); base.src=img.src; base.onload=()=>{
    ctx.drawImage(base,0,0,W,H); let cnt=0;
    document.querySelectorAll('.panel').forEach(el=>{
      const nm=new Image(); nm.src=el.style.background.split(',')[1]; nm.onload=()=>{
        const pw=el.offsetWidth*sc, ph=el.offsetHeight*sc;
        const px=parseFloat(el.style.left)*sc, py=parseFloat(el.style.top)*sc;
        let a=0; const m=/rotate\(([-0-9.]+)deg\)/.exec(el.style.transform); if(m) a=parseFloat(m[1])*Math.PI/180;
        ctx.save(); ctx.translate(px+pw/2,py+ph/2); ctx.rotate(a);
        const pat=ctx.createPattern(nm,'repeat'); ctx.fillStyle=pat;
        if(el.style.borderRadius==='50%') {let r=Math.max(pw,ph)/2; ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill()} 
        else ctx.fillRect(-pw/2,-ph/2,pw,ph);
        ctx.restore(); if(++cnt===document.querySelectorAll('.panel').length){const url=cnv.toDataURL();
          const a=document.createElement('a'); a.href=url; a.download='composition.png'; a.click();}
      }
    });
  }
};
"""

# Render canvas
html(f"""
<style>
  #wall {{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem}}
  .panel {{position:absolute;cursor:move}}
</style>
<button id='exportBtn'>Genereer compositie</button>
<div id='wall'><img src='data:image/jpeg;base64,{img_b64}' style='width:800px'/>{''.join(divs)}</div>
<script>{drag_js}{''.join(scripts)}{export_js}</script>
""", height=880)

# Session share code
st.write("Share session code:")
st.text_area("Base64", base64.b64encode(json.dumps({"panels":st.session_state.panels}).encode()).decode(), height=100)
