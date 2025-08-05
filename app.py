import streamlit as st
from PIL import Image
import os, base64, json, uuid
from io import BytesIO
from streamlit.components.v1 import html

# Ensure set_page_config is first
st.set_page_config(layout="wide")

# Display logo if exists
try:
    logo = Image.open("logo.png")
    st.image(logo, width=250)
except FileNotFoundError:
    pass

# Hide default padding
st.markdown("<style>.block-container {padding-top:1rem;}</style>", unsafe_allow_html=True)

# Panel sizes in cm
sizes = {"M": (47.5,95), "L": (95,95), "XL": (190,95), "MOON": (95,95)}

# Load textures
textures = {}
materials = []
root = os.getcwd()
for folder in [root, os.path.join(root, "Textures")]:
    if os.path.isdir(folder):
        for file in os.listdir(folder):
            if file.lower().endswith((".jpg",".jpeg",".png")):
                key = os.path.splitext(file)[0]
                with open(os.path.join(folder,file),"rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

# Initialize session state
if 'panels' not in st.session_state:
    st.session_state.panels = []

# Sidebar configuration
st.sidebar.header("Configuration")
wall_width = st.sidebar.number_input("Wall width (cm)", value=400.0)
sf = st.sidebar.file_uploader("Load session (.json)", type=["json"])
if sf:
    data = json.load(sf)
    st.session_state.panels = data.get('panels', [])
st.sidebar.download_button("Save session", json.dumps({'panels': st.session_state.panels}), file_name='session.json')

with st.sidebar.form("rotate_form"):
    rid = st.selectbox("Rotate panel", ['--'] + [p['id'] for p in st.session_state.panels])
    if st.form_submit_button("Rotate 90°") and rid!='--':
        for p in st.session_state.panels:
            if p['id']==rid:
                p['rotation'] = (p.get('rotation',0)+90)%360

with st.sidebar.form("delete_form"):
    did = st.selectbox("Delete panel", ['--'] + [p['id'] for p in st.session_state.panels])
    if st.form_submit_button("Delete") and did!='--':
        st.session_state.panels = [p for p in st.session_state.panels if p['id']!=did]

# Photo input
method = st.radio("Photo source", ['Upload','Camera'], horizontal=True)
photo_bytes = None
if method=='Upload':
    up = st.file_uploader("Upload photo", type=['jpg','jpeg','png'])
    if up: photo_bytes = up.read()
elif method=='Camera':
    cam = st.camera_input("Take photo")
    if cam: photo_bytes = cam.getvalue()

if not photo_bytes:
    st.info("Upload or take a photo to start.")
    st.stop()

# Prepare variables
photo_b64 = base64.b64encode(photo_bytes).decode()
scale_ui = 800.0 / wall_width

# Add panel form
with st.form("add_panel_form"):
    c1, c2 = st.columns(2)
    psize = c1.selectbox("Size", list(sizes.keys()))
    mat = c2.selectbox("Material", materials)
    if st.form_submit_button("Add panel"):
        st.session_state.panels.append({
            'id': uuid.uuid4().hex[:6],
            'x':100, 'y':100,
            'rotation':0,
            'size':psize, 'mat':mat
        })

# Build panel divs and init scripts
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p['size']]
    w, h = scale_ui*w_cm, scale_ui*h_cm
    rad = '50%' if p['size']=='MOON' else '0%'
    img_data = textures.get(p['mat'], '')
    off, blur = max(1,int(scale_ui*2)), int(scale_ui*2)*2
    shadow = f"{off}px {off}px {blur}px rgba(0,0,0,0.25)"
    divs.append(
        f"<div class='panel' id='{p['id']}' data-img='data:image/jpeg;base64,{img_data}' "
        f"style='top:{p['y']}px; left:{p['x']}px; width:{w}px; height:{h}px;"
        f" transform:rotate({p['rotation']}deg); border-radius:{rad};"
        f" box-shadow:{shadow}; background-image:url(data:image/jpeg;base64,{img_data});"
        f" background-repeat:repeat; background-size:auto;'></div>"
    )
    scripts.append(f"initDrag('{p['id']}');")

# Render HTML & JS for interactive canvas and export
html(
    f"""
<style>
  #wall {{position:relative;width:800px;border:1px solid #ccc;margin-bottom:1rem;}}
  .panel {{position:absolute;cursor:move;z-index:10;}}
</style>
<button id='exportBtn'>Generate composition</button>
<div id='wall'>
  <img src='data:image/jpeg;base64,{photo_b64}' style='width:800px;' />
  {''.join(divs)}
</div>
<script>
function initDrag(id) {{
  const el = document.getElementById(id);
  let dx, dy, drag=false;
  el.onmousedown = e => {{drag=true;dx=e.clientX-el.offsetLeft;dy=e.clientY-el.offsetTop;}};
  window.onmousemove = e => {{if(drag) {{el.style.left=(e.clientX-dx)+'px';el.style.top=(e.clientY-dy)+'px';}}}};
  window.onmouseup = () => {{drag=false;}};
}}
{''.join(scripts)}
document.getElementById('exportBtn').onclick = () => {{
  const wallImg = document.querySelector('#wall img');
  const W = wallImg.naturalWidth || wallImg.width;
  const H = wallImg.naturalHeight || wallImg.height;
  const sc = W/800;
  const c = document.createElement('canvas'); c.width=W; c.height=H;
  const ctx = c.getContext('2d');
  const base = new Image(); base.src = wallImg.src;
  base.onload = () => {{
    ctx.drawImage(base,0,0,W,H);
    let cnt=0;
    document.querySelectorAll('.panel').forEach(panel=>{{
      const img2=new Image(); img2.src=panel.dataset.img;
      img2.onload = () => {{
        const pw=panel.offsetWidth*sc, ph=panel.offsetHeight*sc;
        const px=parseFloat(panel.style.left)*sc, py=parseFloat(panel.style.top)*sc;
        let a=0; const m=/rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
        if(m) a= parseFloat(m[1])*Math.PI/180;
        ctx.save(); ctx.translate(px+pw/2, py+ph/2); ctx.rotate(a);
        const pat=ctx.createPattern(img2,'repeat'); ctx.fillStyle=pat;
        if(panel.style.borderRadius==='50%') {{
          const r=Math.max(pw,ph)/2; ctx.beginPath(); ctx.arc(0,0,r,0,2*Math.PI); ctx.fill();
        }} else {{ ctx.fillRect(-pw/2,-ph/2,pw,ph); }}
        ctx.restore(); cnt++;
        if(cnt === document.querySelectorAll('.panel').length) {{
          const url=c.toDataURL('image/png'); const a=document.createElement('a'); a.href=url; a.download='composition.png'; a.click();
        }}
      }};
    }});
  }};
}};
</script>
""", height=880
)

# After HTML render, sync positions via JS evaluation
try:
    from streamlit_js_eval import streamlit_js_eval
    positions_json = streamlit_js_eval(
        js_expressions=[
            "(function(){"
            "var arr=[];"
            "document.querySelectorAll('.panel').forEach(function(el){"
            "  var m=el.style.transform.match(/rotate\\(([-0-9.]+)deg\\)/);"
            "  arr.push({id:el.id,x:parseInt(el.style.left),y:parseInt(el.style.top),rotation:m?parseFloat(m[1]):0});"
            "});"
            "return JSON.stringify(arr);"
            "})()"
        ],
        key='sync'
    )
    if positions_json:
        arr = json.loads(positions_json)
        for pos in arr:
            for p in st.session_state.panels:
                if p['id'] == pos['id']:
                    p['x'], p['y'], p['rotation'] = pos['x'], pos['y'], pos['rotation']
except ImportError:
    st.warning("Add 'streamlit-js-eval' to requirements.txt for drag persistence.")

# Share session inline
st.write("Share session code:")
st.text_area("Base64:", base64.b64encode(json.dumps({'panels': st.session_state.panels}).encode()).decode(), height=100)
