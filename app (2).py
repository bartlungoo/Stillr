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
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Initialize panels in session state
if "panels" not in st.session_state:
    st.session_state.panels = []

# Sidebar: wall width, load/save, rotate, delete
st.sidebar.header("Configuration")
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)

# Load session
sf = st.sidebar.file_uploader("Load session (.json)", type=["json"])
if sf:
    data = json.load(sf)
    st.session_state.panels = data.get("panels", [])
# Save session
st.sidebar.download_button(
    "Save session",
    json.dumps({"panels": st.session_state.panels}),
    file_name="session.json"
)

# Rotate panel
with st.sidebar.form("rotate_form"):
    rid = st.selectbox(
        "Rotate panel",
        ["--"] + [p["id"] for p in st.session_state.panels]
    )
    if st.form_submit_button("Rotate 90°") and rid != "--":
        for p in st.session_state.panels:
            if p["id"] == rid:
                p["rotation"] = (p.get("rotation", 0) + 90) % 360

# Delete panel
with st.sidebar.form("delete_form"):
    did = st.selectbox(
        "Delete panel",
        ["--"] + [p["id"] for p in st.session_state.panels]
    )
    if st.form_submit_button("Delete") and did != "--":
        st.session_state.panels = [p for p in st.session_state.panels if p["id"] != did]

# Photo input
"""
Provide multiple ways of capturing an image for the composition.  
Users can upload an image from disk, use the built‑in Streamlit camera widget (front camera on most devices),
or, if the `streamlit_back_camera_input` package is installed, use a custom component that defaults to the back camera.  
The back camera option is detected at runtime so that the UI only shows it when available.  
"""
photo_options = ["Upload", "Camera"]
has_back_cam = False
try:
    from streamlit_back_camera_input import back_camera_input  # type: ignore
    has_back_cam = True
    photo_options.append("Back Camera")
except Exception:
    # If the optional dependency isn't installed we silently ignore it
    pass

source = st.radio("Photo source", photo_options, horizontal=True)
photo_bytes = None

if source == "Upload":
    # Let the user choose an existing photo from disk
    uploaded_file = st.file_uploader("Upload photo", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        photo_bytes = uploaded_file.read()
elif source == "Camera":
    # Use the built‑in Streamlit camera widget (typically the front/selfie camera)
    captured = st.camera_input("Take photo")
    if captured:
        photo_bytes = captured.getvalue()
elif source == "Back Camera":
    # Use the optional back camera component if available
    try:
        back_img = back_camera_input()
        # The component returns either None when no picture is taken or a bytes‑like object when a picture is taken.
        if back_img:
            # `back_img` might be a BytesIO, PIL image or raw bytes; handle the common cases
            if hasattr(back_img, "getvalue"):
                photo_bytes = back_img.getvalue()
            elif isinstance(back_img, (bytes, bytearray)):
                photo_bytes = bytes(back_img)
            else:
                # Fallback: try to convert using PIL
                try:
                    bio = BytesIO()
                    back_img.save(bio, format="PNG")  # type: ignore
                    photo_bytes = bio.getvalue()
                except Exception:
                    photo_bytes = None
    except Exception as e:
        st.error(f"Failed to use back camera component: {e}")

# Guard against missing photo data
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
    # Custom JS snippet to extract the current position and rotation of each panel element.
    # Instead of directly parsing style.left/top (which may be empty and return NaN), we
    # fall back to offsetLeft/offsetTop when no explicit inline style is present.  This
    # prevents positions from being reset to `NaN` on subsequent runs.
    js_code = r"""
(function(){
  let arr = [];
  document.querySelectorAll('.panel').forEach(el => {
    // Extract rotation from inline style if present
    let rot = 0;
    const m = el.style.transform.match(/rotate\(([-0-9.]+)deg\)/);
    if (m) rot = parseFloat(m[1]);
    // Read explicit style values or fall back to computed offsets
    let x = parseFloat(el.style.left);
    let y = parseFloat(el.style.top);
    if (isNaN(x)) x = el.offsetLeft;
    if (isNaN(y)) y = el.offsetTop;
    arr.push({ id: el.id, x: x, y: y, rotation: rot });
  });
  return JSON.stringify(arr);
})()
"""
    try:
        res = streamlit_js_eval(js_expressions=[js_code], key="sync_positions")
        raw = res[0] if isinstance(res, list) else res
        positions = json.loads(raw) if isinstance(raw, str) else raw
        # Update session state for panels with received positions
        for pos in positions:
            # Find matching panel by id
            for p in st.session_state.panels:
                if p["id"] == pos.get("id"):
                    # Only overwrite when a valid number is returned
                    if pos.get("x") is not None:
                        p["x"] = int(pos.get("x"))
                    if pos.get("y") is not None:
                        p["y"] = int(pos.get("y"))
                    # Always update rotation (defaults to 0 when missing)
                    if pos.get("rotation") is not None:
                        p["rotation"] = pos.get("rotation")
    except Exception as e:
        st.error(f"Failed to sync panel positions: {e}")

# Add panel form
with st.form("add_panel_form"):
    col1, col2 = st.columns(2)
    sel_size = col1.selectbox("Size", list(sizes.keys()))
    sel_mat = col2.selectbox("Material", materials)
    if st.form_submit_button("Add panel"):
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6],
            "x": 100,
            "y": 100,
            "rotation": 0,
            "size": sel_size,
            "mat": sel_mat
        })

# Build panel divs and init scripts
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p["size"]]
    w_px, h_px = w_cm * scale, h_cm * scale
    radius = "50%" if p["size"] == "MOON" else "0%"
    img_data = textures.get(p["mat"], "")
    offset = max(1, int(scale * 2))
    blur = offset * 2
    shadow = f"{offset}px {offset}px {blur}px rgba(0,0,0,0.25)"
    # Each panel is rendered as a div with inline styles for position, size and rotation.
    div_html = (
        f"<div class='panel' id='{p['id']}' data-img='data:image/jpeg;base64,{img_data}'"
        f" style='top:{p['y']}px; left:{p['x']}px; width:{int(w_px)}px; height:{int(h_px)}px;"
        f" transform:rotate({p['rotation']}deg); border-radius:{radius}; box-shadow:{shadow};"
        f" background-image:url(data:image/jpeg;base64,{img_data}); background-repeat:repeat; background-size:auto;'></div>"
    )
    divs.append(div_html)
    # Prepare a call to initialise dragging for this panel when the DOM is ready
    scripts.append(f"initDrag('{p['id']}');")

# Define the JavaScript required for dragging panels.  This string is kept separate from the
# HTML f-string to avoid conflicts with Python's f-string syntax.  It will be inserted
# verbatim into the final HTML.
drag_js = """
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy;
  let dragging = false;
  // When starting to drag, record the offset and bring the panel to the front
  const startDrag = (clientX, clientY) => {
    dragging = true;
    dx = clientX - el.offsetLeft;
    dy = clientY - el.offsetTop;
    // increase z-index so the active panel sits above others
    if (!window._maxZ) { window._maxZ = 10; }
    window._maxZ += 1;
    el.style.zIndex = window._maxZ;
  };
  // Move the element during dragging
  const moveDrag = (clientX, clientY) => {
    if (dragging) {
      el.style.left = (clientX - dx) + 'px';
      el.style.top  = (clientY - dy) + 'px';
    }
  };
  // Stop dragging
  const endDrag = () => { dragging = false; };
  // Mouse events
  el.onmousedown = e => {
    e.preventDefault();
    startDrag(e.clientX, e.clientY);
  };
  window.onmousemove = e => moveDrag(e.clientX, e.clientY);
  window.onmouseup = () => endDrag();
  // Touch events for mobile/iPad
  el.ontouchstart = e => {
    if (e.touches && e.touches.length > 0) {
      const t = e.touches[0];
      startDrag(t.clientX, t.clientY);
    }
  };
  window.ontouchmove = e => {
    if (e.touches && e.touches.length > 0) {
      const t = e.touches[0];
      moveDrag(t.clientX, t.clientY);
    }
  };
  window.ontouchend = () => endDrag();
}
"""

# Define the JavaScript responsible for exporting the composition as a single image.  This
# string also lives outside of the f-string to avoid brace conflicts.
export_js = """
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
      const img2 = new Image(); img2.src = panel.dataset.img;
      img2.onload = () => {
        const pw = panel.offsetWidth * sc;
        const ph = panel.offsetHeight * sc;
        const px = parseFloat(panel.style.left) * sc;
        const py = parseFloat(panel.style.top) * sc;
        let a = 0;
        const m = /rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
        if (m) a = parseFloat(m[1]) * Math.PI / 180;
        ctx.save(); ctx.translate(px + pw/2, py + ph/2); ctx.rotate(a);
        const pat = ctx.createPattern(img2, 'repeat'); ctx.fillStyle = pat;
        if (panel.style.borderRadius === '50%') {
          const r = Math.max(pw, ph) / 2;
          ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.fill();
        } else { ctx.fillRect(-pw/2, -ph/2, pw, ph); }
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

# Render interactive canvas and export button
html_content = f"""
<style>
  #wall {{ position: relative; width: 800px; border: 1px solid #ccc; margin-bottom: 1rem; }}
  .panel {{ position: absolute; cursor: move; z-index: 10; }}
</style>
<button id='exportBtn' style='margin-bottom:10px;'>Generate composition</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{b64_img}' style='width:800px;' />
  {''.join(divs)}
</div>
<script>
{drag_js}
{''.join(scripts)}
{export_js}
</script>
"""
html(html_content, height=880)

# Share session inline
st.write("Share session code:")
st.text_area(
    "Base64:",
    base64.b64encode(json.dumps({"panels": st.session_state.panels}).encode()).decode(),
    height=100
)
