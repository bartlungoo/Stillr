import streamlit as st
from streamlit.components.v1 import html
from PIL import Image
import os, base64, json, uuid

# ------ STYLING & LAYOUT ------
st.set_page_config(layout="wide")
st.markdown("""
<link href="https://fonts.googleapis.com/css?family=Lato:400,700|EB+Garamond:700&display=swap" rel="stylesheet">
<style>
body, .block-container {
    font-family: 'Lato', Arial, sans-serif;
    background: #faf7f2 !important;
}
#wall {
    position: relative;
    width: 800px;
    min-height: 420px;
    background: #fffdfa;
    border: 1.5px solid #dedede;
    border-radius: 18px;
    margin-bottom: 1.4rem;
    box-shadow: 0 6px 38px rgba(120,110,90,.09);
}
.panel {
    cursor: move;
    z-index: 2;
    box-shadow: 0 8px 32px rgba(40,40,60,0.17), 0 1.5px 4px rgba(0,0,0,0.05);
    border-radius: 0;
    transition: box-shadow .22s, transform .16s;
    position: absolute;
    outline: none;
    border: 1.5px solid #eee;
}
.panel.moon { border-radius: 50% !important;}
.panel.active, .panel:active, .panel:hover {
    box-shadow: 0 20px 48px rgba(30,50,80,0.24), 0 4px 12px rgba(20,20,40,0.14);
    outline: 2px solid #a9bdfc;
}
.panel-label {
    position: absolute;
    top: 7px; right: 12px;
    background: rgba(255,255,255,0.85);
    color: #3c4250;
    font-family: 'Lato', Arial, sans-serif;
    font-size: 13px;
    padding: 2px 11px 2px 8px;
    border-radius: 6px;
    pointer-events: none;
    box-shadow: 0 1px 4px rgba(80,80,80,0.07);
    font-weight: 700;
    letter-spacing: 0.5px;
    z-index: 5;
}
.stButton>button {
    background: #f3ecd6;
    color: #2b2b2b;
    border-radius: 9px;
    border: none;
    box-shadow: 0 2px 12px rgba(120,100,40,0.08);
    font-family: 'Lato', Arial, sans-serif;
    font-size: 15px;
    font-weight: 700;
    padding: 7px 18px;
    margin-top: 8px;
    margin-bottom: 2px;
    transition: background .13s;
}
.stButton>button:hover {
    background: #efe2b8;
    color: #20203a;
}
.stSelectbox label, .stNumberInput label {
    color: #343049;
    font-family: 'Garamond', 'EB Garamond', serif;
    font-size: 1.07rem;
    font-weight: 600;
    letter-spacing: .01em;
}
#stillr-watermark {
    position: absolute;
    bottom: 20px; right: 24px;
    opacity: 0.13;
    z-index: 20;
    pointer-events: none;
}
</style>
""", unsafe_allow_html=True)

# ------ LOGO ------
if os.path.exists("logo.png"):
    st.image(Image.open("logo.png"), width=250)

# ------ PANEL DATA ------
sizes = {"M": (47.5, 95), "L": (95, 95), "XL": (190, 95), "MOON": (95, 95)}
textures, materials = {}, []
for folder in [os.getcwd(), os.path.join(os.getcwd(), "Textures")]:
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.lower().endswith((".jpg",".jpeg",".png")):
                key = os.path.splitext(fname)[0]
                with open(os.path.join(folder, fname), "rb") as f:
                    textures[key] = base64.b64encode(f.read()).decode()
                materials.append(key)

if "panels" not in st.session_state:
    st.session_state.panels = []

# ------ FOTO KEUZE ------
photo_bytes = None
source = st.radio("Photo source", ["Upload", "Camera"], horizontal=True)
if source == "Upload":
    up = st.file_uploader("Upload photo", type=["jpg","jpeg","png"])
    if up: photo_bytes = up.read()
else:
    cap = st.camera_input("Take photo")
    if cap: photo_bytes = cap.getvalue()
if not photo_bytes:
    st.info("Upload of maak een foto om te beginnen.")
    st.stop()

b64_img = base64.b64encode(photo_bytes).decode()
wall_width = st.sidebar.number_input("Wall width (cm)", 100.0, 2000.0, 400.0)
scale = 800.0 / wall_width

# ------ PANELEN TOEVOEGEN/ROTATIE/VERWIJDEREN ------
st.sidebar.header("Paneelbeheer")
with st.sidebar.expander("Nieuw paneel toevoegen"):
    sz = st.selectbox("Grootte", list(sizes.keys()), key="add_size")
    mat = st.selectbox("Materiaal", materials, key="add_mat")
    if st.button("Voeg paneel toe"):
        st.session_state.panels.append({
            "id": uuid.uuid4().hex[:6],
            "x": 80, "y": 80,
            "rotation": 0,
            "size": sz, "mat": mat
        })

with st.sidebar.expander("Paneel roteren/verwijderen"):
    if st.session_state.panels:
        ids = [p['id'] for p in st.session_state.panels]
        sel = st.selectbox("Selecteer paneel", ids, key="sel_panel")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Roteer 90°"):
                for p in st.session_state.panels:
                    if p['id'] == sel:
                        p['rotation'] = (p.get('rotation',0)+90)%360
        with col2:
            if st.button("Verwijder paneel"):
                st.session_state.panels = [p for p in st.session_state.panels if p['id'] != sel]

# ------ PANEL DIVS & LABELS ------
divs, scripts = [], []
for p in st.session_state.panels:
    w_cm, h_cm = sizes[p['size']]
    w_px, h_px = w_cm*scale, h_cm*scale
    extra_class = ' moon' if p['size']=='MOON' else ''
    img_data = textures.get(p['mat'], '')
    label_html = f"<span class='panel-label'>{p['size']} – {p['mat']}</span>"
    divs.append(
        f"<div class='panel{extra_class}' id='{p['id']}'"
        f" style='position:absolute;top:{p['y']}px;left:{p['x']}px;"
        f"width:{int(w_px)}px;height:{int(h_px)}px;"
        f"transform:rotate({p['rotation']}deg);"
        f"background-image:url(data:image/jpeg;base64,{img_data});background-size:cover;'>"
        f"{label_html}</div>"
    )
    scripts.append(f"initDrag('{p['id']}');")

# ------ WATERMARK (optioneel) ------
watermark_html = ""
if os.path.exists("watermark.png"):
    with open("watermark.png", "rb") as f:
        wm_b64 = base64.b64encode(f.read()).decode()
        watermark_html = f"<img id='stillr-watermark' src='data:image/png;base64,{wm_b64}' width='110'/>"

# ------ DRAG & EXPORT SCRIPTS ------
drag_js = r"""
function initDrag(id) {
  const el = document.getElementById(id);
  let dx, dy, dragging=false;
  const start=(x,y)=>{dragging=true;dx=x-el.offsetLeft;dy=y-el.offsetTop;el.classList.add('active');};
  const move=(x,y)=>{if(dragging){el.style.left=(x-dx)+'px';el.style.top=(y-dy)+'px';}};
  const end=()=>{dragging=false;el.classList.remove('active');};
  el.onmousedown=e=>{e.preventDefault();start(e.clientX,e.clientY);};
  window.onmousemove=e=>move(e.clientX,e.clientY);
  window.onmouseup=end;
  el.ontouchstart=e=>{let t=e.touches[0];start(t.clientX,t.clientY);};
  window.ontouchmove=e=>{let t=e.touches[0];move(t.clientX,t.clientY);};
  window.onouchend=end;
}
"""

export_js = r"""
document.getElementById('exportBtn').onclick=()=>{
  const img=document.querySelector('#wall img');const W=img.naturalWidth||img.width;const H=img.naturalHeight||img.height;
  const sc=W/800;const c=document.createElement('canvas');c.width=W;c.height=H;const ctx=c.getContext('2d');
  const base=new Image();base.src=img.src;base.onload=()=>{ctx.drawImage(base,0,0,W,H);let cnt=0;document.querySelectorAll('.panel').forEach(el=>{const nm=new Image();nm.src=el.style.backgroundImage.slice(5,-2);nm.onload=()=>{const pw=el.offsetWidth*sc,ph=el.offsetHeight*sc;const px=parseFloat(el.style.left)*sc,py=parseFloat(el.style.top)*sc;let a=0;const m=/rotate\(([-0-9.]+)deg\)/.exec(el.style.transform);if(m)a=parseFloat(m[1])*Math.PI/180;ctx.save();ctx.translate(px+pw/2,py+ph/2);ctx.rotate(a);const pat=ctx.createPattern(nm,'repeat');ctx.fillStyle=pat;if(el.classList.contains('moon')){let r=Math.max(pw,ph)/2;ctx.beginPath();ctx.arc(0,0,r,0,2*Math.PI);ctx.fill();}else ctx.fillRect(-pw/2,-ph/2,pw,ph);ctx.restore();if(++cnt===document.querySelectorAll('.panel').length){const url=c.toDataURL();const a=document.createElement('a');a.href=url;a.download='composition.png';a.click();}}});};};
"""

# ------ RENDER WALL ------
html(f"""
<button id='exportBtn'>Genereer compositie</button>
<div id='wall'><img src='data:image/jpeg;base64,{b64_img}' style='width:800px'/>{''.join(divs)}{watermark_html}</div>
<script>{drag_js}{''.join(scripts)}{export_js}</script>
""", height=900)

# ------ OPTIONEEL: SESSION EXPORT ------
st.write("Share session code:")
st.text_area("Base64", base64.b64encode(json.dumps({"panels":st.session_state.panels}).encode()).decode(), height=100)
