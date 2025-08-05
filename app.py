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

# Logo display
if os.path.exists("logo.png"):
    try:
        logo = Image.open("logo.png")
        st.image(logo, width=250)
    except:
        pass

# Panel size definitions (cm)
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}

# Load textures into memory
textures = {}
materials = []
for folder in [os.getcwd(), os.path.join(os.getcwd(), "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Initialize panels in session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Photo input
source_opts = ["Upload"]
if HAS_BACK_CAM:
    source_opts.append("Back Camera")
source_opts.append("Camera")
source = st.radio("Photo source", source_opts, horizontal=True)

photo_bytes = None
if source == "Upload":
    up = st.file_uploader("Upload photo", type=["jpg", "jpeg", "png"])
    if up:
        photo_bytes = up.read()
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

# Encode and scale image
b64_img = base64.b64encode(photo_bytes).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", min_value=100.0, max_value=2000.0, value=400.0)
scale = 800.0 / wall_width

# Sync existing drag positions before controls (requires streamlit-js-eval)
has_eval = False
sync_code = r"""
(function(){
  const arr=[];
  document.querySelectorAll('.panel').forEach(el=>{
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
    from streamlit_js_eval import streamlit_js_eval
    has_eval = True
    res = streamlit_js_eval(js_expressions=[sync_code], key="sync_before")
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

# Sidebar controls (no manual rerun)
st.sidebar.header("Configuratie")
# Add panel
sz = st.sidebar.selectbox("Grootte", list(sizes.keys()))
mt = st.sidebar.selectbox("Materiaal", materials)
if st.sidebar.button("Voeg paneel toe"):
    st.session_state.panels.append({
        "id": uuid.uuid4().hex[:6],
        "x": 100, "y": 100,
        "rotation": 0,
        "size": sz, "mat": mt
    })
# Rotate panel
sel_rot = st.sidebar.selectbox("Roteer paneel", ["--"] + [p['id'] for p in st.session_state.panels])
if st.sidebar.button("Rotate 90°") and sel_rot != "--":
    for p in st.session_state.panels:
        if p['id'] == sel_rot:
            p['rotation'] = (p.get('rotation', 0) + 90) % 360
            break
# Delete panel
sel_del = st.sidebar.selectbox("Verwijder paneel", ["--"] + [p['id'] for p in st.session_state.panels])
if st.sidebar.button("Verwijder") and sel_del != "--":
    st.session_state.panels = [p for p in st.session_state.panels if p['id'] != sel_del]

# Build panel divs & init scripts
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p['size']]
    w_px, h_px = w_cm * scale, h_cm * scale
    radius = "50%" if p['size'] == 'MOON' else '0%'
    img_data = textures.get(p['mat'], '')
    # Correct top and left usage
    style = (
        f"top:{p['y']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px;"
        f"transform:rotate({p['rotation']}deg); border-radius:{radius};"
        f"background-image:url(data:image/jpeg;base64,{img_data}); background-repeat:repeat; background-size:auto;"
    )
    divs.append(f"<div class='panel' id='{p['id']}' style='{style}'></div>")
    scripts.append(f"initDrag('{p['id']}');")

# JS code for dragging
drag_js = r"""
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  const startDrag=(x,y)=>{dragging=true; dx=x-el.offsetLeft; dy=y-el.offsetTop; if(!window._z)window._z=10; el.style.zIndex=++window._z;};
  const moveDrag=(x,y)=>{if(dragging){el.style.left=(x-dx)+'px'; el.style.top=(y-dy)+'px';}};
  const endDrag=()=>{dragging=false;};
  el.onmousedown=e=>{e.preventDefault(); startDrag(e.clientX,e.clientY);};
  window.onmousemove=e=>moveDrag(e.clientX,e.clientY);
  window.onmouseup=endDrag;
  el.ontouchstart=e=>{let t=e.touches[0]; startDrag(t.clientX,t.clientY);};
  window.ontouchmove=e=>{let t=e.touches[0]; moveDrag(t.clientX,t.clientY);};
  window.ontouchend=endDrag;
}
"""

# JS code for exporting composition
export_js = r"""
document.getElementById('exportBtn').onclick = () => {
  const wallImg = document.querySelector('#wall img');
  const W = wallImg.naturalWidth || wallImg.width;
  const H = wallImg.naturalHeight || wallImg.height;
  const sc = W / 800;
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const base = new Image(); base.src = wallImg.src;
  base.onload = () => {
    ctx.drawImage(base, 0, 0, W, H);
    let count = 0;
    document.querySelectorAll('.panel').forEach(panel => {
      const img2 = new Image(); img2.src = panel.dataset.img || panel.style.backgroundImage.slice(5,-2);
      img2.onload = () => {
        const pw = panel.offsetWidth * sc;
        const ph = panel.offsetHeight * sc;
        const px = parseFloat(panel.style.left) * sc;
        const py = parseFloat(panel.style.top) * sc;
        let a = 0;
        const m = /rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
        if (m) a = parseFloat(m[1]) * Math.PI/180;
        ctx.save(); ctx.translate(px + pw/2, py + ph/2); ctx.rotate(a);
        const pat = ctx.createPattern(img2, 'repeat'); ctx.fillStyle = pat;
        if (panel.style.borderRadius === '50%') {
          const r = Math.max(pw, ph) / 2;
          ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.fill();
        } else {
          ctx.fillRect(-pw/2, -ph/2, pw, ph);
        }
        ctx.restore(); count++;
        if (count === document.querySelectorAll('.panel').length) {
          const url = canvas.toDataURL('image/png');
          const a = document.createElement('a'); a.href = url; a.download = 'composition.png'; a.click();
        }
      };
    });
  };
};
"""

# Render canvas and panels
html(f"""
<style>
  #wall {{ position:relative; width:800px; border:1px solid #ccc; margin-bottom:1rem; }}
  .panel {{ position:absolute; cursor:move; }}
</style>
<button id='exportBtn' style='margin-bottom:1rem;'>Generate composition</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{b64_img}' style='width:800px;' />
  {''.join(divs)}
</div>
<script>
{drag_js}
{''.join(scripts)}
{export_js}
</script>
""", height=880)

# Share session inline
st.write("Share session code:")
st.text_area(
    "Base64",
    base64.b64encode(json.dumps({"panels": st.session_state.panels}).encode()).decode(),
    height=100
)
