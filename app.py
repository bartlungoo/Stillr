import streamlit as st
# set_page_config must be first Streamlit call
st.set_page_config(layout="wide")

from PIL import Image, ImageDraw
import os, base64, json, uuid
from io import BytesIO
from streamlit.components.v1 import html

# Display logo if available
try:
    logo = Image.open("logo.png")
    st.image(logo, width=250)
except FileNotFoundError:
    pass

# Hide default padding
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# Panel sizes (width x height in cm)
sizes = {
    "M": (47.5, 95),
    "L": (95, 95),
    "XL": (190, 95),
    "MOON": (95, 95)
}

# Load textures from root and Textures/ directory
textures = {}
materials = []
root = os.path.dirname(__file__)
# root folder
for fname in os.listdir(root):
    if fname.lower().endswith((".jpg",".jpeg",".png")):
        key = os.path.splitext(fname)[0]
        with open(os.path.join(root,fname),"rb") as f:
            textures[key] = base64.b64encode(f.read()).decode()
        materials.append(key)
# Textures folder
tex_dir = os.path.join(root, "Textures")
if os.path.isdir(tex_dir):
    for fname in os.listdir(tex_dir):
        if fname.lower().endswith((".jpg",".jpeg",".png")):
            key = os.path.splitext(fname)[0]
            if key not in textures:
                with open(os.path.join(tex_dir,fname),"rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Initialize session
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sidebar
st.sidebar.header("Options")
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)
session_file = st.sidebar.file_uploader("Load session (.json)", type=["json"])
if session_file:
    try:
        data = json.load(session_file)
        st.session_state.panels = data.get("panels", [])
        wall_width = data.get("wall_width", wall_width)
    except:
        st.error("Failed to load session. Check JSON file.")

# Photo input
method = st.radio("Photo source", ["Upload","Camera"])
photo_bytes = None
if method == "Upload":
    up = st.file_uploader("Upload photo", type=["jpg","jpeg","png"])
    if up: photo_bytes = up.read()
elif method == "Camera":
    cap = st.camera_input("Take photo")
    if cap: photo_bytes = cap.getvalue()

if not photo_bytes:
    st.info("Upload or take a photo to start.")
else:
    # Prepare preview
    b64 = base64.b64encode(photo_bytes).decode()
    scale_ui = 800 / wall_width

    # Add panel form
    with st.form("add_panel"):
        c1, c2 = st.columns(2)
        psize = c1.selectbox("Size", list(sizes.keys()))
        mat = c2.selectbox("Material", materials)
        if st.form_submit_button("Add panel"):
            st.session_state.panels.append({
                "id": uuid.uuid4().hex[:6],
                "x": 100, "y": 100,
                "rotation": 0,
                "size": psize,
                "mat": mat
            })

    # Build HTML & JS for panels
    panel_divs = []
    script_calls = []
    for p in st.session_state.panels:
        w_cm, h_cm = sizes[p["size"]]
        w = scale_ui * w_cm
        h = scale_ui * h_cm
        radius = "50%" if p["size"] == "MOON" else "0%"
        img_data = textures.get(p["mat"], "")
        # subtle shadow
        off = max(1, int(scale_ui * 2)); blur = off * 2
        shadow = f"{off}px {off}px {blur}px rgba(0,0,0,0.25)"
        div = f"""
<div class='panel' id='{p['id']}' data-img='data:image/jpeg;base64,{img_data}'
     style='top:{p['y']}px; left:{p['x']}px;
            width:{w}px; height:{h}px;
            transform:rotate({p['rotation']}deg);
            border-radius:{radius};
            box-shadow:{shadow};
            background-image:url(data:image/jpeg;base64,{img_data});
            background-repeat:repeat;
            background-size:auto;'>
</div>
"""
        panel_divs.append(div)
        script_calls.append(f"initDrag('{p['id']}');")

    # Render UI
    html(f"""
<style>
  #wall {{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem;}}
  .panel {{position:absolute;cursor:move;z-index:10;}}
</style>
<button id='exportBtn' style='margin-bottom:10px;'>Generate composition</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{b64}' style='width:800px;' />
  {''.join(panel_divs)}
</div>
<script>
function initDrag(id) {{
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  el.onmousedown = e=>{{ dragging=true; dx=e.clientX-el.offsetLeft; dy=e.clientY-el.offsetTop; }};
  window.onmousemove = e=>{{ if(dragging) {{ el.style.left=(e.clientX-dx)+'px'; el.style.top=(e.clientY-dy)+'px'; }} }};
  window.onmouseup = ()=>{{ dragging=false; }};
}}
{''.join(script_calls)}

document.getElementById('exportBtn').onclick = () => {{
  const wallImg = document.querySelector('#wall img');
  const W = wallImg.naturalWidth || wallImg.width;
  const H = wallImg.naturalHeight || wallImg.height;
  const sc = W/800;
  const c = document.createElement('canvas'); c.width=W; c.height=H;
  const ctx = c.getContext('2d');
  const base = new Image(); base.src = wallImg.src;
  base.onload = () => {{
    ctx.drawImage(base, 0, 0, W, H);
    let count = 0;
    const panels = document.querySelectorAll('.panel');
    panels.forEach(panel => {{
      const img2 = new Image(); img2.src = panel.dataset.img;
      img2.onload = () => {{
        const pw = panel.offsetWidth*sc;
        const ph = panel.offsetHeight*sc;
        const px = parseFloat(panel.style.left)*sc;
        const py = parseFloat(panel.style.top)*sc;
        let a = 0;
        const m = /rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
        if(m) a = parseFloat(m[1])*Math.PI/180;
        ctx.save();
        ctx.translate(px+pw/2, py+ph/2);
        ctx.rotate(a);
        // Fill front with tiled pattern
        const pat = ctx.createPattern(img2, 'repeat');
        ctx.fillStyle = pat;
        if(panel.style.borderRadius==='50%') {{
          const r = Math.max(pw,ph)/2;
          ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill();
          // radial highlight
          const radial = ctx.createRadialGradient(0,0,r*0.3,0,0,r);
          radial.addColorStop(0,'rgba(255,255,255,0.15)');
          radial.addColorStop(1,'rgba(0,0,0,0)');
          ctx.fillStyle = radial;
          ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill();
        }} else {{
          ctx.fillRect(-pw/2,-ph/2,pw,ph);
          const thickness = 5*sc;
          // Right side
          ctx.beginPath();
          ctx.moveTo(pw/2,-ph/2);
          ctx.lineTo(pw/2,ph/2);
          ctx.lineTo(pw/2+thickness,ph/2);
          ctx.lineTo(pw/2+thickness,-ph/2);
          ctx.closePath();
          const gradR = ctx.createLinearGradient(pw/2,-ph/2,pw/2+thickness,-ph/2);
          gradR.addColorStop(0,'rgba(0,0,0,0.25)');
          gradR.addColorStop(1,'rgba(0,0,0,0)');
          ctx.fillStyle = gradR; ctx.fill();
          // Bottom side
          ctx.beginPath();
          ctx.moveTo(pw/2,ph/2);
          ctx.lineTo(-pw/2,ph/2);
          ctx.lineTo(-pw/2,ph/2+thickness);
          ctx.lineTo(pw/2,ph/2+thickness);
          ctx.closePath();
          const gradB = ctx.createLinearGradient(-pw/2,ph/2,-pw/2,ph/2+thickness);
          gradB.addColorStop(0,'rgba(0,0,0,0.25)');
          gradB.addColorStop(1,'rgba(0,0,0,0)');
          ctx.fillStyle = gradB; ctx.fill();
          // highlight front
          const hl = ctx.createLinearGradient(-pw/2,-ph/2,pw/2,ph/2);
          hl.addColorStop(0,'rgba(255,255,255,0.15)');
          hl.addColorStop(1,'rgba(0,0,0,0)');
          ctx.fillStyle = hl;
          ctx.fillRect(-pw/2,-ph/2,pw,ph);
        }}
        ctx.restore();
        count++;
        if(count === panels.length) {{ const url = c.toDataURL('image/png'); const a=document.createElement('a'); a.href=url; a.download='composition.png'; a.click(); }}
      }};
    }});
  }};
}};
</script>
