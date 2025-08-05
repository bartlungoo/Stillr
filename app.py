import streamlit as st
from streamlit.components.v1 import html
from PIL import Image
import os, base64, json, uuid
from io import BytesIO

# Optional components
try:
    from streamlit_back_camera_input import back_camera_input
    HAS_BACK_CAM = True
except ImportError:
    HAS_BACK_CAM = False

try:
    from streamlit_js_eval import streamlit_js_eval
    HAS_JS_EVAL = True
except ImportError:
    HAS_JS_EVAL = False

# Page setup
st.set_page_config(layout="wide")
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Load logo
if os.path.exists("logo.png"):
    st.image(Image.open("logo.png"), width=250)

# Panel definitions
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}

# Load textures
textures, materials = {}, []
for folder in [os.getcwd(), os.path.join(os.getcwd(), "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg",".jpeg",".png")):
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sync positions
def sync_positions():
    if not HAS_JS_EVAL:
        return
    js_code = r"""
(function(){
  const arr = [];
  document.querySelectorAll('.panel').forEach(el => {
    const m = /rotate\(([-0-9.]+)deg\)/.exec(el.style.transform);
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
    try:
        res = streamlit_js_eval(js_expressions=[js_code], key="sync")
        raw = res[0] if isinstance(res, list) else res
        if isinstance(raw, str) and raw.strip():
            positions = json.loads(raw)
            for pos in positions:
                for p in st.session_state.panels:
                    if p['id'] == pos.get('id'):
                        p['x'] = pos.get('x', p['x'])
                        p['y'] = pos.get('y', p['y'])
                        p['rotation'] = pos.get('rotation', p['rotation'])
    except Exception:
        pass

# Photo input
source_options = ["Upload"] + (["Back Camera"] if HAS_BACK_CAM else []) + ["Camera"]
source = st.radio("Photo source", source_options, horizontal=True)
photo_bytes = None
if source == "Upload":
    up = st.file_uploader("Upload photo", type=["jpg","jpeg","png"])
    if up: photo_bytes = up.read()
elif source == "Back Camera":
    img = back_camera_input()
    if img: photo_bytes = img.getvalue()
else:
    cap = st.camera_input("Take photo")
    if cap: photo_bytes = cap.getvalue()
if not photo_bytes:
    st.info("Upload of maak een foto om te beginnen.")
    st.stop()

b64_img = base64.b64encode(photo_bytes).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", 100.0, 2000.0, 400.0)
scale = 800.0 / wall_width

# Sidebar: Add Panel
st.sidebar.header("Paneel beheren")
with st.sidebar.expander("Nieuw paneel toevoegen"):
    sz = st.selectbox("Grootte", list(sizes.keys()), key="add_size")
    mat = st.selectbox("Materiaal", materials, key="add_mat")
    if st.button("Voeg paneel toe"):
        sync_positions()
        # Voeg paneel toe in gespreide positie
        offset = 50 + len(st.session_state.panels) * 30
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6],
            "x": offset, "y": offset,
            "rotation": 0,
            "size": sz, "mat": mat
        })

# Sidebar: Rotate and Delete
with st.sidebar.expander("Paneel roteren/verwijderen"):
    if st.session_state.panels:
        sync_positions()
        ids = [p['id'] for p in st.session_state.panels]
        sel = st.selectbox("Selecteer paneel", ids, key="sel_panel")
        if st.button("Roteer 90°"):
            for p in st.session_state.panels:
                if p['id'] == sel:
                    p['rotation'] = (p.get('rotation',0)+90)%360
                    break
        if st.button("Verwijder paneel"):
            st.session_state.panels = [p for p in st.session_state.panels if p['id'] != sel]

# Build panel divs
divs, scripts = [], []
for idx, p in enumerate(st.session_state.panels):
    w_cm, h_cm = sizes[p['size']]
    w_px, h_px = w_cm*scale, h_cm*scale
    radius = '50%' if p['size']=='MOON' else '0%'
    img_data = textures.get(p['mat'], '')
    divs.append(
        f"<div class='panel' id='{p['id']}'"
        f" style='position:absolute;top:{p['y']}px;left:{p['x']}px;"
        f"width:{int(w_px)}px;height:{int(h_px)}px;"
        f"transform:rotate({p['rotation']}deg);border-radius:{radius};"
        f"background-image:url(data:image/jpeg;base64,{img_data});background-repeat:repeat;'></div>"
    )
    scripts.append(f"initDrag('{p['id']}');")

# JavaScript for drag
drag_js = r"""
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  const start=(x,y)=>{dragging=true;dx=x-el.offsetLeft;dy=y-el.offsetTop;el.style.zIndex=1000;};
  const move=(x,y)=>{if(dragging){el.style.left=(x-dx)+'px';el.style.top=(y-dy)+'px';}};
  const end=()=>{dragging=false;};
  el.onmousedown=e=>{e.preventDefault();start(e.clientX,e.clientY);};
  window.onmousemove=e=>move(e.clientX,e.clientY);
  window.onmouseup=end;
  el.ontouchstart=e=>{let t=e.touches[0];start(t.clientX,t.clientY);};
  window.ontouchmove=e=>{let t=e.touches[0];move(t.clientX,t.clientY);};
  window.ontouchend=end;
}
"""

# JavaScript for export
export_js = r"""
document.getElementById('exportBtn').onclick=()=>{
  const img=document.querySelector('#wall img');const W=img.naturalWidth||img.width;const H=img.naturalHeight||img.height;
  const sc=W/800;const c=document.createElement('canvas');c.width=W;c.height=H;const ctx=c.getContext('2d');
  const base=new Image();base.src=img.src;base.onload=()=>{ctx.drawImage(base,0,0,W,H);let cnt=0;document.querySelectorAll('.panel').forEach(el=>{const nm=new Image();nm.src=el.style.backgroundImage.slice(5,-2);nm.onload=()=>{const pw=el.offsetWidth*sc,ph=el.offsetHeight*sc;const px=parseFloat(el.style.left)*sc,py=parseFloat(el.style.top)*sc;let a=0;const m=/rotate\(([-0-9.]+)deg\)/.exec(el.style.transform);if(m)a=parseFloat(m[1])*Math.PI/180;ctx.save();ctx.translate(px+pw/2,py+ph/2);ctx.rotate(a);const pat=ctx.createPattern(nm,'repeat');ctx.fillStyle=pat;if(el.style.borderRadius==='50%'){let r=Math.max(pw,ph)/2;ctx.beginPath();ctx.arc(0,0,r,0,2*Math.PI);ctx.fill();}else ctx.fillRect(-pw/2,-ph/2,pw,ph);ctx.restore();if(++cnt===document.querySelectorAll('.panel').length){const url=c.toDataURL();const a=document.createElement('a');a.href=url;a.download='composition.png';a.click();}}});};};
"""

# Render canvas and export button
html(f"""
<style>#wall{{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem}}"""
     f""" .panel{{cursor:move;z-index:1}}"""
     f"""</style>"""
     f"""<button id='exportBtn'>Genereer compositie</button>"""
     f"""<div id='wall'><img src='data:image/jpeg;base64,{b64_img}' style='width:800px'/>{''.join(divs)}</div>"""
     f"""<script>{drag_js}{''.join(scripts)}{export_js}</script>""", height=880)

# Share session code
st.write("Share session code:")
st.text_area("Base64", base64.b64encode(json.dumps({"panels":st.session_state.panels}).encode()).decode(), height=100)
