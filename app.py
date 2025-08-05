import streamlit as st
from PIL import Image, ImageDraw
import os, base64, json, uuid
from io import BytesIO
from streamlit.components.v1 import html

# Ensure page config is first
st.set_page_config(layout="wide")

# Display logo
try:
    logo = Image.open("logo.png")
    st.image(logo, width=250)
except FileNotFoundError:
    pass
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Panel sizes in cm
sizes = {"M": (47.5,95), "L": (95,95), "XL": (190,95), "MOON": (95,95)}

# Load textures
textures, materials = {}, []
root = os.getcwd()
for folder in [root, os.path.join(root, "Textures")]:
    if os.path.isdir(folder):
        for file in os.listdir(folder):
            if file.lower().endswith((".jpg",".jpeg",".png")):
                key = os.path.splitext(file)[0]
                path = os.path.join(folder, file)
                with open(path, "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sidebar: load/save & rotate/delete
st.sidebar.header("Configuration")
# Load session
sf = st.sidebar.file_uploader("Load session (.json)", type=["json"])
if sf:
    data = json.load(sf)
    st.session_state.panels = data.get("panels", [])
# Save session
st.sidebar.download_button("Save session", json.dumps({"panels": st.session_state.panels}), file_name="session.json")

# Rotate form
with st.sidebar.form("rotate_form"):
    sel = st.selectbox("Rotate panel", ["--"] + [p["id"] for p in st.session_state.panels])
    if st.form_submit_button("Rotate 90°") and sel!="--":
        for p in st.session_state.panels:
            if p["id"] == sel:
                p["rotation"] = (p.get("rotation",0) + 90) % 360

# Delete form
with st.sidebar.form("delete_form"):
    sel2 = st.selectbox("Delete panel", ["--"] + [p["id"] for p in st.session_state.panels])
    if st.form_submit_button("Delete") and sel2!="--":
        st.session_state.panels = [p for p in st.session_state.panels if p["id"]!=sel2]

# Photo input and main UI
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)
method = st.radio("Photo source", ["Upload","Camera"], horizontal=True)
photo = None
if method=="Upload":
    up = st.file_uploader("Upload photo", type=["jpg","jpeg","png"])
    if up: photo = up.read()
else:
    cam = st.camera_input("Take photo")
    if cam: photo = cam.getvalue()

if not photo:
    st.info("Provide a photo to start.")
    st.stop()

photo_b64 = base64.b64encode(photo).decode()
scale_ui = 800.0 / wall_width

# Add panel form
glm, gls = st.columns(2)
with st.form("add_panel"):
    size = gls.selectbox("Size", list(sizes.keys()))
    mat = glm.selectbox("Material", materials)
    if st.form_submit_button("Add panel"):
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6],
            "x":100, "y":100, "rotation":0,
            "size":size, "mat":mat
        })

# Build HTML & JS for drag
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm,h_cm = sizes[p["size"]]
    w,h = scale_ui*w_cm, scale_ui*h_cm
    rad = '50%' if p['size']=='MOON' else '0%'
    src = textures.get(p['mat'],'')
    off,blur = max(1,int(scale_ui*2)), int(scale_ui*2)*2
    shadow=f"{off}px {off}px {blur}px rgba(0,0,0,0.25)"
    divs.append(f"<div class=\"panel\" id=\"{p['id']}\" data-id=\"{p['id']}\" data-img=\"data:image/jpeg;base64,{src}\" style='top:{p['y']}px;left:{p['x']}px;width:{w}px;height:{h}px;transform:rotate({p['rotation']}deg);border-radius:{rad};box-shadow:{shadow};background-image:url(data:image/jpeg;base64,{src});background-repeat:repeat;background-size:auto;'></div>")
    scripts.append(f"initDrag('{p['id']}');")

# Inject HTML
html(f"""
<style>#wall{{position:relative;width:800px;border:1px solid #ccc;}}.panel{{position:absolute;cursor:move;}}</style>
<button id='exportBtn'>Generate composition</button>
<button id='savePosBtn'>Save positions</button>
<div id='wall'><img src='data:image/jpeg;base64,{photo_b64}' style='width:800px;' />{''.join(divs)}</div>
<script>
function initDrag(id){{
  let el=document.getElementById(id),dx,dy,drag=false;
  el.onmousedown=e=>{{drag=true;dx=e.clientX-el.offsetLeft;dy=e.clientY-el.offsetTop}};
  window.onmousemove=e=>{{if(drag){{el.style.left=(e.clientX-dx)+'px';el.style.top=(e.clientY-dy)+'px';}}}};
  window.onmouseup=()=>{{drag=false;}};
}}
{''.join(scripts)}
// Save positions back to Python
const saveBtn=document.getElementById('savePosBtn');
saveBtn.onclick=()=>{{
  const panels=document.querySelectorAll('.panel');
  const data=[];
  panels.forEach(el=>{{
    data.push({ id:el.dataset.id, x:parseInt(el.style.left), y:parseInt(el.style.top), rotation: parseInt(el.style.transform.match(/rotate\(([-0-9]+)deg\)/)[1]) });
  }});
  const out=JSON.stringify(data);
  document.dispatchEvent(new CustomEvent('positionsSaved',{{detail:out}}));
}};
</script>
""",height=800)

# Listen for positionsSaved event via streamlit_js_eval
# Requires installation: pip install streamlit-js-eval
try:
    from streamlit_js_eval import streamlit_js_eval
    saved = streamlit_js_eval(js_expressions=["window.positionsData"], key="pos");
    if saved:
        newpos = json.loads(saved)
        for p in st.session_state.panels:
            for np in newpos:
                if np['id']==p['id']:
                    p['x'],p['y'],p['rotation']=np['x'],np['y'],np['rotation']
except ImportError:
    st.warning("Install streamlit-js-eval for drag persistence: pip install streamlit-js-eval")

# Export composition
# ... existing export JS ...
