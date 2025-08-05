import streamlit as st
from PIL import Image
import os, base64, json, uuid
from io import BytesIO
from streamlit.components.v1 import html

# Ensure page config is first
st.set_page_config(layout="wide")

# Display logo if available
try:
    logo = Image.open("logo.png")
    st.image(logo, width=250)
except FileNotFoundError:
    pass

# Hide default padding
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Define panel sizes (width, height in cm)
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}

# Load textures from project root and Textures/ folder
textures = {}
materials = []
root = os.getcwd()
for folder in [root, os.path.join(root, "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                name = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[name] = base64.b64encode(f.read()).decode()
                materials.append(name)

# Initialize panels in session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sidebar: wall width, load/save, rotate, delete
st.sidebar.header("Configuration")
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)
# Load session
up_session = st.sidebar.file_uploader("Load session (.json)", type=["json"])
if up_session:
    data = json.load(up_session)
    st.session_state.panels = data.get("panels", [])
# Save session
st.sidebar.download_button("Save session", json.dumps({"panels": st.session_state.panels}), file_name="session.json")

# Rotate panel
tab1 = st.sidebar.form("rotate_form")
rid = tab1.selectbox("Rotate panel", ["--"] + [p["id"] for p in st.session_state.panels])
if tab1.form_submit_button("Rotate 90°") and rid != "--":
    for p in st.session_state.panels:
        if p["id"] == rid:
            p["rotation"] = (p.get("rotation", 0) + 90) % 360

# Delete panel
tab2 = st.sidebar.form("delete_form")
did = tab2.selectbox("Delete panel", ["--"] + [p["id"] for p in st.session_state.panels])
if tab2.form_submit_button("Delete") and did != "--":
    st.session_state.panels = [p for p in st.session_state.panels if p["id"] != did]

# Photo input
type_photo = st.radio("Photo source", ["Upload", "Camera"], horizontal=True)
photo_bytes = None
if type_photo == "Upload":
    f = st.file_uploader("Upload photo", type=["jpg", "jpeg", "png"])
    if f: photo_bytes = f.read()
elif type_photo == "Camera":
    c = st.camera_input("Take photo")
    if c: photo_bytes = c.getvalue()
if not photo_bytes:
    st.info("Upload or take a photo to start.")
    st.stop()

# Prepare image and scale
b64_img = base64.b64encode(photo_bytes).decode()
scale = 800.0 / wall_width

# Sync drag positions via streamlit-js-eval
has_eval = False
try:
    from streamlit_js_eval import streamlit_js_eval
    has_eval = True
except ImportError:
    st.warning("Include streamlit-js-eval>=0.1.2 in requirements.txt for drag persistence.")

if has_eval:
    js = (
        "(function(){"
        "let arr=[];"
        "document.querySelectorAll('.panel').forEach(el=>{"
        " let m=el.style.transform.match(/rotate\(([-0-9.]+)deg\)/);"
        " arr.push({id:el.id, x:parseInt(el.style.left), y:parseInt(el.style.top), rotation:m?parseFloat(m[1]):0});"
        "});"
        "return JSON.stringify(arr);"
        "})()"
    )
    try:
        res = streamlit_js_eval(js_expressions=[js], key="sync")
        raw = res[0] if isinstance(res, list) else res
        positions = json.loads(raw) if isinstance(raw, str) else raw
        for pos in positions:
            for p in st.session_state.panels:
                if p["id"] == pos.get("id"):
                    p.update({
                        "x": pos.get("x", p["x"]),
                        "y": pos.get("y", p["y"]),
                        "rotation": pos.get("rotation", p.get("rotation", 0))
                    })
    except Exception as e:
        st.error(f"Failed to sync panel positions: {e}")

# Add panel form
with st.form("add_form"):
    c1, c2 = st.columns(2)
    size = c1.selectbox("Size", list(sizes.keys()))
    mat = c2.selectbox("Material", materials)
    if st.form_submit_button("Add panel"):
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6], "x": 100, "y": 100,
            "rotation": 0, "size": size, "mat": mat
        })

# Build HTML divs and JS init code
divs, cmds = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p["size"]]
    w_px, h_px = w_cm * scale, h_cm * scale
    rad = "50%" if p["size"] == "MOON" else "0%"
    img_data = textures.get(p["mat"], "")
    off = max(1, int(scale * 2)); blur = off * 2
    sh = f"{off}px {off}px {blur}px rgba(0,0,0,0.25)"
    divs.append(
        f"<div class='panel' id='{p['id']}' data-img='data:image/jpeg;base64,{img_data}'"
        f" style='top:{p['y']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px;"
        f" transform:rotate({p['rotation']}deg); border-radius:{rad}; box-shadow:{sh};"
        f" background-image:url(data:image/jpeg;base64,{img_data}); background-repeat:repeat; background-size:auto;'></div>"
    )
    cmds.append(f"initDrag('{p['id']}');")

# Render canvas and export button
html(
    f"""
<style>
  #wall {{position:relative; width:800px; border:1px solid #ccc; margin-bottom:1rem;}}
  .panel {{position:absolute; cursor:move; z-index:10;}}
</style>
<button id='exportBtn' style='margin-bottom:10px;'>Generate composition</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{b64_img}' style='width:800px;' />
  {''.join(divs)}
</div>
<script>
function initDrag(id) {{
  const el=document.getElementById(id);
  let dx, dy, drag=false;
  el.onmousedown=e=>{{ drag=true; dx=e.clientX-el.offsetLeft; dy=e.clientY-el.offsetTop; }};
  window.onmousemove=e=>{{ if(drag){{ el.style.left=(e.clientX-dx)+'px'; el.style.top=(e.clientY-dy)+'px'; }} }};
  window.onmouseup=()=>{{ drag=false; }};
}}
{''.join(cmds)}
document.getElementById('exportBtn').onclick=()=>{{
  const img=document.querySelector('#wall img');
  const W=img.naturalWidth||img.width;
  const H=img.naturalHeight||img.height;
  const sc_val=W/800;
  const c=document.createElement('canvas'); c.width=W; c.height=H;
  const ctx=c.getContext('2d');
  const base=new Image(); base.src=img.src;
  base.onload=()=>{{
    ctx.drawImage(base,0,0,W,H);
    let cnt=0;
    document.querySelectorAll('.panel').forEach(panel=>{{
      const i=new Image(); i.src=panel.dataset.img;
      i.onload=()=>{{
        const pw=panel.offsetWidth*sc_val;
        const ph=panel.offsetHeight*sc_val;
        const px=parseFloat(panel.style.left)*sc_val;
        const py=parseFloat(panel.style.top)*sc_val;
        let a=0;
        const m=/rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
        if(m) a=parseFloat(m[1])*Math.PI/180;
        ctx.save(); ctx.translate(px+pw/2, py+ph/2); ctx.rotate(a);
        const pat=ctx.createPattern(i,'repeat'); ctx.fillStyle=pat;
        if(panel.style.borderRadius==='50%'){{
          const r=Math.max(pw,ph)/2; ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill();
        }} else {{ ctx.fillRect(-pw/2,-ph/2,pw,ph); }}
        ctx.restore(); cnt++;
        if(cnt===document.querySelectorAll('.panel').length){{
          const url=c.toDataURL('image/png'); const a=document.createElement('a'); a.href=url; a.download='composition.png'; a.click();
        }}
      }};
    }});
  }};
}};
</script>
""",
    height=880
)

# Share session inline
st.write("Share session code:")
st.text_area(
    "Base64:",
    base64.b64encode(json.dumps({"panels": st.session_state.panels}).encode()).decode(),
    height=100
)

