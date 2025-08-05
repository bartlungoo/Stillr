import streamlit as st
from streamlit.components.v1 import html
from PIL import Image
import os, base64, json, uuid
from io import BytesIO

# Try import back camera component
try:
    from streamlit_back_camera_input import back_camera_input
    HAS_BACK_CAM = True
except ImportError:
    HAS_BACK_CAM = False

# Try import JS-eval component
try:
    from streamlit_js_eval import streamlit_js_eval
    HAS_JS_EVAL = True
except ImportError:
    HAS_JS_EVAL = False

# Page config and styling
st.set_page_config(layout="wide")
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Display logo if present
if os.path.exists("logo.png"):
    try:
        st.image(Image.open("logo.png"), width=250)
    except:
        pass

# Panel size definitions (cm)
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

# Initialize session state for panels
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sync code snippet
sync_code = r"""
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

def sync_positions():
    if not HAS_JS_EVAL:
        st.sidebar.warning("Installeer streamlit-js-eval voor drag-persistentie.")
        return
    try:
        res = streamlit_js_eval(js_expressions=[sync_code], key=f"sync_{uuid.uuid4().hex}")
        raw = res[0] if isinstance(res, list) else res
        if isinstance(raw, str) and raw.strip():
            positions = json.loads(raw)
            for pos in positions:
                for p in st.session_state.panels:
                    if p['id'] == pos.get('id'):
                        p['x'] = pos.get('x', p['x'])
                        p['y'] = pos.get('y', p['y'])
                        p['rotation'] = pos.get('rotation', p['rotation'])
    except Exception as e:
        st.sidebar.error(f"Fout bij synchroniseren: {e}")

# Photo input picker
sources = ["Upload"] + (["Back Camera"] if HAS_BACK_CAM else []) + ["Camera"]
source = st.radio("Photo source", sources, horizontal=True)
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

# Prepare image and scale
b64_img = base64.b64encode(photo_bytes).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", min_value=100.0, max_value=2000.0, value=400.0)
scale = 800.0 / wall_width

# Sidebar controls
st.sidebar.header("Configuratie")
# Sync button before any modifications
action = st.sidebar.selectbox("Actie", ["--","Sync posities","Voeg paneel toe","Rotate 90°","Verwijder paneel"] )
if action == "Sync posities":
    sync_positions()
elif action == "Voeg paneel toe":
    sync_positions()
    idx = len(st.session_state.panels)
    offset = 100 + idx * 20
    st.session_state.panels.append({
        "id": uuid.uuid4().hex[:6],
        "x": offset, "y": offset,
        "rotation": 0,
        "size": st.sidebar.selectbox("Grootte", list(sizes.keys()), key="add_sz"),
        "mat": st.sidebar.selectbox("Materiaal", materials, key="add_mat")
    })
elif action == "Rotate 90°":
    sync_positions()
    sel = st.sidebar.selectbox("Selecteer ID om te roteren", [p['id'] for p in st.session_state.panels], key="rot_sel")
    for p in st.session_state.panels:
        if p['id'] == sel:
            p['rotation'] = (p.get('rotation',0)+90)%360
            break
elif action == "Verwijder paneel":
    sync_positions()
    sel = st.sidebar.selectbox("Selecteer ID om te verwijderen", [p['id'] for p in st.session_state.panels], key="del_sel")
    st.session_state.panels = [p for p in st.session_state.panels if p['id']!=sel]

# Build HTML panels
divs, scripts = [], []
for z,p in enumerate(st.session_state.panels):
    w_cm,h_cm = sizes[p['size']]
    w_px,h_px = w_cm*scale,h_cm*scale
    radius = '50%' if p['size']=='MOON' else '0%'
    img_data = textures.get(p['mat'],"")
    divs.append(
        f"<div class='panel' id='{p['id']}' style='top:{p['y']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px; "
        f"transform:rotate({p['rotation']}deg); border-radius:{radius}; z-index:{z}; "
        f"background-image:url(data:image/jpeg;base64,{img_data}); background-repeat:repeat; background-size:auto;'></div>"
    )
    scripts.append(f"initDrag('{p['id']}');")

# JS for drag
drag_js = r"""
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  const start=(x,y)=>{dragging=true;dx=x-el.offsetLeft;dy=y-el.offsetTop;el.style.zIndex=parseInt(el.style.zIndex)+1;};
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
# JS for export
export_js = r"""
document.getElementById('exportBtn').onclick=()=>{
  const img=document.querySelector('#wall img');const W=img.naturalWidth||img.width;const H=img.naturalHeight||img.height;
  const sc=W/800;const c=document.createElement('canvas');c.width=W;c.height=H;const ctx=c.getContext('2d');
  const base=new Image();base.src=img.src;base.onload=()=>{ctx.drawImage(base,0,0,W,H);let cnt=0;document.querySelectorAll('.panel').forEach(el=>{const nm=new Image();nm.src=el.style.backgroundImage.slice(5,-2);nm.onload=()=>{const pw=el.offsetWidth*sc,ph=el.offsetHeight*sc;const px=parseFloat(el.style.left)*sc,py=parseFloat(el.style.top)*sc;let a=0;const m=/rotate\(([-0-9.]+)deg\)/.exec(el.style.transform);if(m)a=parseFloat(m[1])*Math.PI/180;ctx.save();ctx.translate(px+pw/2,py+ph/2);ctx.rotate(a);const pat=ctx.createPattern(nm,'repeat');ctx.fillStyle=pat;if(el.style.borderRadius==='50%'){let r=Math.max(pw,ph)/2;ctx.beginPath();ctx.arc(0,0,r,0,2*Math.PI);ctx.fill();}else ctx.fillRect(-pw/2,-ph/2,pw,ph);ctx.restore();if(++cnt===document.querySelectorAll('.panel').length){const url=c.toDataURL();const a=document.createElement('a');a.href=url;a.download='composition.png';a.click();}}});};};
"""

# Render canvas
html(f"""
<style>#wall{{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem}}.panel{{position:absolute;cursor:move}}</style>
<button id='exportBtn'>Genereer compositie</button>
<div id='wall'><img src='data:image/jpeg;base64,{b64_img}' style='width:800px'/>{''.join(divs)}</div>
<script>{drag_js}{''.join(scripts)}{export_js}</script>
""", height=880)

# Share session code
st.write("Share session code:")
st.text_area("Base64", base64.b64encode(json.dumps({"panels":st.session_state.panels}).encode()).decode(), height=100)
