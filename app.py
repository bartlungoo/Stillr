import streamlit as st
# Zorg dat set_page_config als allereerste Streamlit-oproep staat
st.set_page_config(layout="wide")

from PIL import Image, ImageDraw, ImageFilter
import os
import base64
import json
import uuid
from streamlit.components.v1 import html
from io import BytesIO

# Toon logo
try:
    logo = Image.open("logo.png")
    st.image(logo, width=250)
except:
    pass
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# Paneelformaten (breedte x hoogte in cm)
formaten = {
    "M": (47.5, 95),
    "L": (95, 95),
    "XL": (190, 95),
    "MOON": (95, 95)
}

# Laad alle textures uit root en /Textures map
textures = {}
stoffen = []
root_dir = os.path.dirname(__file__)
# Zoek in hoofdmap
for f in os.listdir(root_dir):
    if f.lower().endswith((".jpg", ".jpeg", ".png")):
        name = os.path.splitext(f)[0]
        with open(os.path.join(root_dir, f), "rb") as imgf:
            textures[name] = base64.b64encode(imgf.read()).decode()
        stoffen.append(name)
# Zoek in submap Textures
tx_dir = os.path.join(root_dir, "Textures")
if os.path.isdir(tx_dir):
    for f in os.listdir(tx_dir):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            name = os.path.splitext(f)[0]
            if name not in textures:
                with open(os.path.join(tx_dir, f), "rb") as imgf:
                    textures[name] = base64.b64encode(imgf.read()).decode()
                stoffen.append(name)

# Initialiseer sessiestate
if "panels" not in st.session_state:
    st.session_state.panels = []

# Functie om compositie lokaal te genereren (optie)
def generate_composite(base_bytes, muurbreedte_cm):
    base_img = Image.open(BytesIO(base_bytes)).convert("RGBA")
    img_w, img_h = base_img.size
    scale_ui_to_img = img_w / 800.0
    px_per_cm = img_w / float(muurbreedte_cm)
    for p in st.session_state.panels:
        b64 = textures.get(p['stof'], '')
        if not b64:
            continue
        pane_bytes = base64.b64decode(b64)
        pane = Image.open(BytesIO(pane_bytes)).convert("RGBA")
        w_px = int(formaten[p['formaat']][0] * px_per_cm)
        h_px = int(formaten[p['formaat']][1] * px_per_cm)
        pane = pane.resize((w_px, h_px), Image.LANCZOS)
        if p['formaat'] == 'MOON':
            mask = Image.new('L', (w_px, h_px), 0)
            d = ImageDraw.Draw(mask)
            d.ellipse((0,0,w_px,h_px), fill=255)
            pane.putalpha(mask)
        rot = -p.get('rotation', 0)
        pane = pane.rotate(rot, expand=True)
        pw, ph = pane.size
        x_ui, y_ui = p['x'], p['y']
        cx = (x_ui + (formaten[p['formaat']][0] * (800.0/muurbreedte_cm)) / 2.0) * scale_ui_to_img
        cy = (y_ui + (formaten[p['formaat']][1] * (800.0/muurbreedte_cm)) / 2.0) * scale_ui_to_img
        nx = int(cx - pw/2)
        ny = int(cy - ph/2)
        base_img.paste(pane, (nx, ny), pane)
    return base_img.convert("RGB")

# Sidebar opties
st.sidebar.header("Opties")
muurbreedte = st.sidebar.number_input("Breedte muur (cm)", value=400.0)
sessie_upload = st.sidebar.file_uploader("📂 Laad sessie (.json)", type=["json"])
if sessie_upload:
    try:
        sessiedata = json.load(sessie_upload)
        st.session_state.panels = sessiedata.get('panels', [])
        muurbreedte = sessiedata.get('muurbreedte', muurbreedte)
    except:
        st.error("Kon sessie niet laden. Controleer JSON.")

# Foto-invoer
methode = st.radio("Foto invoer", ["Upload foto","Gebruik camera"], horizontal=True)
foto_bytes = None
if methode == "Upload foto":
    up = st.file_uploader("Upload muurfoto", type=["jpg","jpeg","png"])
    if up:
        foto_bytes = up.read()
elif methode == "Gebruik camera":
    cam = st.camera_input("Neem een foto van de ruimte")
    if cam:
        foto_bytes = cam.getvalue()

if not foto_bytes:
    st.info("Upload of neem een foto om te starten.")
else:
    foto_b64 = base64.b64encode(foto_bytes).decode()
    schaal_ui = 800.0 / muurbreedte

    # Optionele muurdetectie
    if st.checkbox("🔍 Detecteer muur automatisch"):
        bbox, prev = detect_wall(foto_bytes)
        if prev:
            st.image(prev, caption="Gedetecteerde muur", use_column_width=True)
        else:
            st.warning("Geen duidelijke muur gevonden.")

    # Paneel toevoegen
    with st.form("paneel_form"):
        c1, c2 = st.columns(2)
        fmt = c1.selectbox("📐 Formaat", list(formaten.keys()))
        stof = c2.selectbox("🎨 Stof", stoffen)
        if st.form_submit_button("➕ Voeg paneel toe"):
            st.session_state.panels.append({
                'id': str(uuid.uuid4())[:4], 'x': 100, 'y': 100,
                'rotation': 0, 'formaat': fmt, 'stof': stof
            })

    # Bouw panelen HTML & JS
    panel_html = ''
    scripts = ''
    for p in st.session_state.panels:
        w_cm, h_cm = formaten[p['formaat']]
        w = schaal_ui * w_cm
        h = schaal_ui * h_cm
        rad = '50%' if p['formaat']=='MOON' else '0%'
        src = textures.get(p['stof'], '')
        # Schaduw
        off = max(1, int(schaal_ui*2))
        blur = int(off*2)
        shadow = f"{off}px {off}px {blur}px rgba(0,0,0,0.25)"
        panel_html += f'''<div class="paneel" id="{p['id']}" data-img="data:image/jpeg;base64,{src}" style="top:{p['y']}px; left:{p['x']}px; width:{w}px; height:{h}px; transform:rotate({p['rotation']}deg); border-radius:{rad}; box-shadow:{shadow}; background-image:url('data:image/jpeg;base64,{src}'); background-repeat:repeat; background-size:auto;"></div>'''
        scripts += f"initDrag('{p['id']}');"

    # Render HTML + JS
    html(f"""
    <style>
      #muur {{ position: relative; width: 800px; border: 1px solid #ccc; margin-bottom: 1rem; }}
      .paneel {{ position: absolute; cursor: move; z-index: 10; }}
    </style>
    <button id="exportBtn" style="margin-bottom:10px;">🎬 Genereer compositie</button>
    <div id="muur">
      <img src="data:image/jpeg;base64,{foto_b64}" style="width: 800px;" />
      {panel_html}
    </div>
    <script>
      function initDrag(id) {{
        const el = document.getElementById(id);
        let ox, oy, drag=false;
        el.addEventListener('mousedown', e=>{{ drag=true; ox=e.clientX-el.offsetLeft; oy=e.clientY-el.offsetTop; }});
        window.addEventListener('mousemove', e=>{{ if(drag){{ el.style.left=(e.clientX-ox)+'px'; el.style.top=(e.clientY-oy)+'px'; }} }});
        window.addEventListener('mouseup', ()=>{{ drag=false; }});
      }}
      {scripts}
      document.getElementById('exportBtn').onclick = function() {{
        const wall = document.querySelector('#muur img');
        const w0 = wall.naturalWidth || wall.width;
        const h0 = wall.naturalHeight || wall.height;
        const sc = w0/800;
        const canvas = document.createElement('canvas');
        canvas.width = w0; canvas.height = h0;
        const ctx = canvas.getContext('2d');
        const base = new Image(); base.src=wall.src;
        base.onload = ()=>{{
          ctx.drawImage(base,0,0,w0,h0);
          let cnt=0;
          document.querySelectorAll('.paneel').forEach(panel=>{{
            const img2 = new Image(); img2.src=panel.dataset.img;
            img2.onload = ()=>{{
              const pw = panel.offsetWidth*sc;
              const ph = panel.offsetHeight*sc;
              const px = parseFloat(panel.style.left)*sc;
              const py = parseFloat(panel.style.top)*sc;
              let r=0;
              const m=/rotate\(([-0-9.]+)deg\)/.exec(panel.style.transform);
              if(m) r=parseFloat(m[1])*Math.PI/180;
              ctx.save();
              ctx.translate(px+pw/2,py+ph/2);
              ctx.rotate(r);
              // Voorvlak
              const pattern = ctx.createPattern(img2,'repeat');
              ctx.fillStyle = pattern;
              if(panel.style.borderRadius==='50%'){{
                const rad = Math.max(pw,ph)/2;
                ctx.beginPath(); ctx.arc(0,0,rad,0,2*Math.PI); ctx.fill();
                // Radiaal highlight
                const radial = ctx.createRadialGradient(0,0,rad*0.3,0,0,rad);
                radial.addColorStop(0,'rgba(255,255,255,0.15)');
                radial.addColorStop(1,'rgba(0,0,0,0)');
                ctx.fillStyle=radial;
                ctx.beginPath(); ctx.arc(0,0,rad,0,2*Math.PI); ctx.fill();
              }} else {{
                ctx.fillRect(-pw/2,-ph/2,pw,ph);
                // Extrusie rechthoekige zijkanten
                const thickness = 5*sc;
                // rechterzijde
                ctx.beginPath();
                ctx.moveTo(pw/2,-ph/2);
                ctx.lineTo(pw/2,ph/2);
                ctx.lineTo(pw/2+thickness,ph/2);
                ctx.lineTo(pw/2+thickness,-ph/2);
                ctx.closePath();
                const gradR = ctx.createLinearGradient(pw/2,-ph/2,pw/2+thickness,-ph/2);
                gradR.addColorStop(0,'rgba(0,0,0,0.25)');
                gradR.addColorStop(1,'rgba(0,0,0,0)');
                ctx.fillStyle=gradR; ctx.fill();
                // onderzijde
                ctx.beginPath();
                ctx.moveTo(pw/2,ph/2);
                ctx.lineTo(-pw/2,ph/2);
                ctx.lineTo(-pw/2,ph/2+thickness);
                ctx.lineTo(pw/2,ph/2+thickness);
                ctx.closePath();
                const gradB = ctx.createLinearGradient(-pw/2,ph/2,-pw/2,ph/2+thickness);
                gradB.addColorStop(0,'rgba(0,0,0,0.25)');
                gradB.addColorStop(1,'rgba(0,0,0,0)');
                ctx.fillStyle=gradB; ctx.fill();
                // highlight frontvlak
                const hl = ctx.createLinearGradient(-pw/2,-ph/2,pw/2,ph/2);
                hl.addColorStop(0,'rgba(255,255,255,0.15)');
                hl.addColorStop(1,'rgba(0,0,0,0)');
                ctx.fillStyle=hl;
                ctx.fillRect(-pw/2,-ph/2,pw,ph);
              }}
              ctx.restore();
              cnt++;
              if(cnt===document.querySelectorAll('.paneel').length){
                const url=canvas.toDataURL('image/png');
                const a=document.createElement('a'); a.href=url; a.download='visualisatie.png'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
              }
            }};
          }});
        }};
      }}
    </script>
    """, height=820)

    # Sessies opslaan en delen
    st.download_button(
        "💾 Download sessie",
        json.dumps({"muurbreedte": muurbreedte, "panels": st.session_state.panels}),
        file_name="sessie.json"
    )
    if st.button("🔗 Deel sessie"):
        data = json.dumps({"muurbreedte":muurbreedte, "panels":st.session_state.panels})
        st.text_area("Copy iemand deze code:", value=base64.b64encode(data.encode()).decode(), height=150)
