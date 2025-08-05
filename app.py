import streamlit as st
# Plaats de page config als allereerste Streamlit‑commando
st.set_page_config(layout="wide")

from PIL import Image, ImageDraw, ImageFilter
import os
import base64
import json
import uuid
from streamlit.components.v1 import html
from io import BytesIO

# Documentatie en uitleg over deze applicatie vind je in de README of het
# bijbehorende rapport. We houden de module vrij van tekstuele literalen zodat
# Streamlit deze niet automatisch op de pagina toont.

# -------------------------------------------------------------------------------------
# Configuratie en basisgegevens
# Toon het Stillr‑logo bovenaan de pagina in plaats van een tekstuele titel
try:
    logo = Image.open("logo.png")
    # Stel een maximale breedte in zodat het logo niet te groot wordt
    st.image(logo, width=250)
except Exception:
    # Fallback: geen logo gevonden
    pass

# Verberg de standaard streamlit titel; we tonen enkel het logo
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# Formaten van de panelen in centimeter (breedte, hoogte)
formaten = {
    # Gebruik de correcte afmetingen voor Stillr‑panelen (breedte x hoogte in cm).
    # M: 47,5 cm breed x 95 cm hoog (staand paneel)
    "M": (47.5, 95),
    # L: 95 cm x 95 cm (vierkant)
    "L": (95, 95),
    # XL: 190 cm breed x 95 cm hoog
    "XL": (190, 95),
    # Moon: rond paneel met een diameter van 95 cm (we gebruiken 95 x 95 en
    # tekenen een cirkel als masker)
    "MOON": (95, 95)
}

# Beschikbare stoffen laden. Als er een map 'Textures' bestaat, worden alle
# JPEG/PNG-bestanden daarin automatisch ingelezen. De bestandsnaam (zonder
# extensie) wordt gebruikt als naam van de stof. Wanneer de map ontbreekt,
# worden de standaardstoffen gebruikt (Affection, Kind, Sympathy, Tender).
textures = {}
stoffen = []
textures_dir = os.path.join(os.path.dirname(__file__), "Textures")
if os.path.isdir(textures_dir):
    for fname in os.listdir(textures_dir):
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            name = os.path.splitext(fname)[0]
            try:
                with open(os.path.join(textures_dir, fname), "rb") as f:
                    textures[name] = base64.b64encode(f.read()).decode()
                stoffen.append(name)
            except Exception:
                continue
else:
    # Fallback naar de standaardkleuren als er geen Textures-map is
    default_stoffen = ["Affection", "Kind", "Sympathy", "Tender"]
    for stof in default_stoffen:
        try:
            with open(f"{stof}.jpg", "rb") as f:
                textures[stof] = base64.b64encode(f.read()).decode()
        except Exception:
            textures[stof] = ""
        stoffen.append(stof)

# Initialiseersessie: slaat toegevoegde panelen op
if "panels" not in st.session_state:
    st.session_state.panels = []

# ------------------------------------------------------------------
# Hulpfunctie om een compositie te genereren
def generate_composite(base_bytes: bytes, muurbreedte_cm: float):
    """
    Combineert de geüploade of vastgelegde muurfoto met de toegevoegde panelen.

    Parameters
    ----------
    base_bytes : bytes
        Byte‐representatie van de muurfoto.
    muurbreedte_cm : float
        Werkelijke breedte van de muur in centimeters. Nodig om de panelen
        op de juiste schaal weer te geven.

    Returns
    -------
    PIL.Image.Image
        Een nieuw beeld met de panelen op de muur geplakt.
    """
    # Open de basismuur als RGBA zodat transparantie mogelijk is
    base_img = Image.open(BytesIO(base_bytes)).convert("RGBA")
    img_width, img_height = base_img.size

    # Brede preview in UI is altijd 800px. Bepaal schaal tussen UI‐coördinaten
    # en de werkelijke afbeeldingsbreedte.
    scale_ui_to_img = img_width / 800.0

    # Bepaal pixels per centimeter op basis van de opgegeven muurbreedte
    px_per_cm = img_width / float(muurbreedte_cm)

    # Loop door alle panelen en plak ze op de basismuur
    for p in st.session_state.panels:
        # Sla panelen over waarvoor geen stofafbeelding beschikbaar is
        texture_b64 = textures.get(p["stof"], "")
        if not texture_b64:
            continue
        try:
            panel_bytes = base64.b64decode(texture_b64)
            panel_img = Image.open(BytesIO(panel_bytes)).convert("RGBA")
        except Exception:
            continue

        # Formaat in centimeter
        w_cm, h_cm = formaten[p["formaat"]]
        # Bereken de formaat in pixels op basis van muurbreedte
        w_px = int(w_cm * px_per_cm)
        h_px = int(h_cm * px_per_cm)

        # Schaal de stofafbeelding naar het gewenste formaat
        panel_resized = panel_img.resize((w_px, h_px), Image.LANCZOS)

        # Maak cirkelvorm voor MOON: alpha‐masker
        if p["formaat"] == "MOON":
            mask = Image.new("L", (w_px, h_px), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, w_px, h_px), fill=255)
            panel_resized.putalpha(mask)

        # Draai het paneel om zijn middelpunt. CSS roteert met de klok mee,
        # PIL roteert tegen de klok in. Daarom negatief.
        rotation_deg = -float(p.get("rotation", 0))
        panel_rotated = panel_resized.rotate(rotation_deg, expand=True)
        rotated_w, rotated_h = panel_rotated.size

        # Bereken positie. p['x'] en p['y'] zijn UI‐coördinaten bij 800px breedte.
        # Vertaal naar beeldcoördinaten.
        x_ui = p["x"]
        y_ui = p["y"]
        center_x = (x_ui + (w_cm * (800.0 / muurbreedte_cm)) / 2.0) * scale_ui_to_img
        center_y = (y_ui + (h_cm * (800.0 / muurbreedte_cm)) / 2.0) * scale_ui_to_img
        # Nieuwe hoekpunten zodat het midden gelijk blijft na rotatie
        new_x = int(center_x - rotated_w / 2.0)
        new_y = int(center_y - rotated_h / 2.0)

        # Plak het paneel met alfa op de basismuur
        base_img.paste(panel_rotated, (new_x, new_y), panel_rotated)

    return base_img.convert("RGB")

# Detecteer de grootste rechthoek van randen in de afbeelding die vermoedelijk
# de muur voorstelt. Deze functie gebruikt een eenvoudige randdetectie met de
# ingebouwde ImageFilter.FIND_EDGES en thresholding. Het resultaat is een
# bounding box en een voorbeeldafbeelding met een rode kader om de gevonden
# muur.
def detect_wall(base_bytes: bytes):
    try:
        img_gray = Image.open(BytesIO(base_bytes)).convert("L")
        # Randdetectie uitvoeren
        edges = img_gray.filter(ImageFilter.FIND_EDGES)
        # Binary threshold zodat enkel sterke randen overblijven
        edges = edges.point(lambda x: 255 if x > 40 else 0)
        bbox = edges.getbbox()
        if bbox:
            # Maak RGB-versie en teken een kader rond de gedetecteerde muur
            rgb = Image.open(BytesIO(base_bytes)).convert("RGB").copy()
            draw = ImageDraw.Draw(rgb)
            draw.rectangle(bbox, outline="red", width=3)
            return bbox, rgb
        return None, None
    except Exception:
        return None, None

# ------------------------------------------------------------------
# Sidebar opties
st.sidebar.header("Opties")
muurbreedte = st.sidebar.number_input("Breedte muur (cm)", value=400.0)

sessie_upload = st.sidebar.file_uploader("📂 Laad sessie (.json)", type=["json"])
if sessie_upload:
    try:
        sessie_data = json.load(sessie_upload)
        st.session_state.panels = sessie_data.get("panels", [])
        muurbreedte = sessie_data.get("muurbreedte", muurbreedte)
    except Exception:
        st.error("Kon de sessie niet laden. Controleer het JSON‑bestand.")

# Laat de gebruiker kiezen hoe hij/zij een foto wil toevoegen
methode = st.radio(
    "Foto invoer",
    options=["Upload foto", "Gebruik camera"],
    index=0,
    horizontal=True,
    help="Je kunt een bestaande muurfoto uploaden of direct een foto nemen met je camera."
)

foto_bytes = None
if methode == "Upload foto":
    uploaded_file = st.file_uploader("Upload een muurfoto", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        foto_bytes = uploaded_file.read()
elif methode == "Gebruik camera":
    camera_capture = st.camera_input("Neem een foto van de ruimte")
    if camera_capture is not None:
        # camera_input geeft een UploadedFile terug; getvalue() levert bytes
        foto_bytes = camera_capture.getvalue()

# Als er nog geen foto is geselecteerd
if not foto_bytes:
    st.info("Upload of neem een foto om te starten.")
else:
    # Toon de foto in base64 voor de preview
    foto_b64 = base64.b64encode(foto_bytes).decode()
    schaal_ui = 800.0 / muurbreedte

    # Optionele automatische muurdetectie
    if st.checkbox("🔍 Detecteer muur automatisch", help="Probeert het muurgebied te vinden en toont een rood kader."):
        bbox, preview = detect_wall(foto_bytes)
        if preview is not None:
            st.image(preview, caption="Gedetecteerde muur", use_column_width=True)
        else:
            st.warning("Er werd geen duidelijk muurgebied gevonden.")

    # Formulier voor nieuwe panelen
    with st.form("paneel_form"):
        col1, col2 = st.columns(2)
        formaat = col1.selectbox("📐 Formaat", list(formaten.keys()))
        stof = col2.selectbox("🎨 Stof", stoffen)
        if st.form_submit_button("➕ Voeg paneel toe"):
            st.session_state.panels.append({
                "id": str(uuid.uuid4())[:4],
                "x": 100,
                "y": 100,
                "rotation": 0,
                "formaat": formaat,
                "stof": stof
            })

    # Genereer de HTML voor alle panelen en de bijbehorende scripts
    panel_html = ""
    scripts = ""
    for p in st.session_state.panels:
        w_cm, h_cm = formaten[p["formaat"]]
        # Paneelgrootte in px binnen de UI (800px breed)
        w = schaal_ui * w_cm
        h = schaal_ui * h_cm
        radius = "50%" if p["formaat"] == "MOON" else "0%"
        img_src = textures.get(p["stof"], "")
        # Voeg een subtiele 3D-schaduw toe. We gebruiken een kleinere offset en
        # blur zodat de diepte minder overheersend is. De offset is gebaseerd op
        # 2 cm (in plaats van 5 cm) voor een subtiele uitstraling.
        offset_px = max(1, int(schaal_ui * 2))
        blur_px = int(offset_px * 2)
        shadow = f"{offset_px}px {offset_px}px {blur_px}px rgba(0,0,0,0.25)"
        # Genereer een div in plaats van een img om textuurpatronen te herhalen.
        # De base64-afbeelding wordt opgeslagen in data-img zodat we deze kunnen
        # gebruiken in de export. De achtergrond wordt herhaald voor een natuurlijker
        # textuur.
        panel_html += f'''
            <div class="paneel" id="{p['id']}" data-img="data:image/jpeg;base64,{img_src}"
                 style="top:{p['y']}px; left:{p['x']}px; width:{w}px; height:{h}px;
                        transform:rotate({p['rotation']}deg); border-radius:{radius};
                        box-shadow:{shadow};
                        background-image:url('data:image/jpeg;base64,{img_src}');
                        background-repeat:repeat;
                        background-size:auto;">
            </div>
        '''
        scripts += f"initDrag('{p['id']}');"

    # Plaats de muur en panelen in de app. Met JavaScript kunnen panelen worden versleept.
    html(f'''
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
                let offsetX = 0, offsetY = 0, isDragging = false;
                el.addEventListener("mousedown", function(e) {{
                    isDragging = true;
                    offsetX = e.clientX - el.offsetLeft;
                    offsetY = e.clientY - el.offsetTop;
                }});
                window.addEventListener("mousemove", function(e) {{
                    if (!isDragging) return;
                    el.style.left = (e.clientX - offsetX) + "px";
                    el.style.top = (e.clientY - offsetY) + "px";
                }});
                window.addEventListener("mouseup", function() {{ isDragging = false; }});
            }}
            {scripts}
            // Functie om compositie te exporteren naar een PNG
            const exportBtn = document.getElementById('exportBtn');
            exportBtn.addEventListener('click', function() {{
                const wallImg = document.querySelector('#muur img');
                const wallWidth = wallImg.naturalWidth || wallImg.width;
                const wallHeight = wallImg.naturalHeight || wallImg.height;
                const scale = wallWidth / 800.0;
                const canvas = document.createElement('canvas');
                canvas.width = wallWidth;
                canvas.height = wallHeight;
                const ctx = canvas.getContext('2d');
                const base = new Image();
                base.src = wallImg.src;
                base.onload = function() {{
                    ctx.drawImage(base, 0, 0, wallWidth, wallHeight);
                    const panels = document.querySelectorAll('.paneel');
                    let processed = 0;
                    panels.forEach(function(panel) {{
                        // Gebruik de data-img van het div-paneel voor de textuur
                        const img2 = new Image();
                        img2.src = panel.dataset.img;
                        img2.onload = function() {{
                            const w = panel.offsetWidth * scale;
                            const h = panel.offsetHeight * scale;
                            const x = parseFloat(panel.style.left) * scale;
                            const y = parseFloat(panel.style.top) * scale;
                            let rot = 0;
                            const transform = panel.style.transform;
                            const match = /rotate\(([-0-9.]+)deg\)/.exec(transform);
                            if (match) rot = parseFloat(match[1]) * Math.PI / 180.0;
                            ctx.save();
                            ctx.translate(x + w / 2.0, y + h / 2.0);
                            ctx.rotate(rot);
                            // Schaduwinstellingen voor subtiele diepte in de export
                            // Dikte van het paneel (5 cm) omgerekend naar pixels
                            const thickness = 5 * scale;
                            // Gebruik de data‑image als patroon zodat de textuur wordt herhaald
                            const pattern = ctx.createPattern(img2, 'repeat');
                            // Reset schaduwinstellingen; we tekenen zelf de zijkanten in plaats van een drop shadow
                            ctx.shadowColor = 'transparent';
                            // Translate naar het midden van het paneel en roteer zoals in de UI
                            ctx.save();
                            ctx.translate(x + w / 2.0, y + h / 2.0);
                            ctx.rotate(rot);
                            // Teken het voorvlak met het textuurpatroon
                            ctx.fillStyle = pattern;
                            if (panel.style.borderRadius === '50%') {{
                                // Voor een rond paneel gebruiken we een cirkelvormig pad
                                const radius = Math.max(w, h) / 2.0;
                                ctx.beginPath();
                                ctx.arc(0, 0, radius, 0, 2 * Math.PI);
                                ctx.fill();
                                // Voeg een subtiele highlight toe zodat het materiaal levendiger oogt
                                const radial = ctx.createRadialGradient(0, 0, radius * 0.3, 0, 0, radius);
                                radial.addColorStop(0, 'rgba(255,255,255,0.15)');
                                radial.addColorStop(1, 'rgba(0,0,0,0)');
                                ctx.fillStyle = radial;
                                ctx.beginPath();
                                ctx.arc(0, 0, radius, 0, 2 * Math.PI);
                                ctx.fill();
                            }} else {{
                                // Rechthoekig paneel
                                ctx.fillRect(-w / 2.0, -h / 2.0, w, h);
                                // Teken de zijkanten om diepte te simuleren
                                // Rechter zijkant
                                ctx.beginPath();
                                ctx.moveTo(w / 2.0, -h / 2.0);
                                ctx.lineTo(w / 2.0, h / 2.0);
                                ctx.lineTo(w / 2.0 + thickness, h / 2.0);
                                ctx.lineTo(w / 2.0 + thickness, -h / 2.0);
                                ctx.closePath();
                                const gradRight = ctx.createLinearGradient(w / 2.0, -h / 2.0, w / 2.0 + thickness, -h / 2.0);
                                gradRight.addColorStop(0, 'rgba(0,0,0,0.25)');
                                gradRight.addColorStop(1, 'rgba(0,0,0,0)');
                                ctx.fillStyle = gradRight;
                                ctx.fill();
                                // Onderste zijkant
                                ctx.beginPath();
                                ctx.moveTo(w / 2.0, h / 2.0);
                                ctx.lineTo(-w / 2.0, h / 2.0);
                                ctx.lineTo(-w / 2.0, h / 2.0 + thickness);
                                ctx.lineTo(w / 2.0, h / 2.0 + thickness);
                                ctx.closePath();
                                const gradBottom = ctx.createLinearGradient(-w / 2.0, h / 2.0, -w / 2.0, h / 2.0 + thickness);
                                gradBottom.addColorStop(0, 'rgba(0,0,0,0.25)');
                                gradBottom.addColorStop(1, 'rgba(0,0,0,0)');
                                ctx.fillStyle = gradBottom;
                                ctx.fill();
                                // Voeg een highlight toe aan het voorvlak om een lichtbron te simuleren (van linksboven)
                                const highlight = ctx.createLinearGradient(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0);
                                highlight.addColorStop(0, 'rgba(255,255,255,0.15)');
                                highlight.addColorStop(1, 'rgba(0,0,0,0)');
                                ctx.fillStyle = highlight;
                                ctx.fillRect(-w / 2.0, -h / 2.0, w, h);
                            }}
                            // Herstel de context
                            ctx.restore();
                            processed++;
                            if (processed === panels.length) {{
                                const url = canvas.toDataURL('image/png');
                                const link = document.createElement('a');
                                link.href = url;
                                link.download = 'visualisatie.png';
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                            }}
                        }};
                    }});
                }};
            }});
        </script>
    ''', height=820)

    # Opties om sessie te downloaden of te wijzigen
    st.download_button(
        "💾 Download sessie",
        json.dumps({
            "muurbreedte": muurbreedte,
            "panels": st.session_state.panels
        }),
        file_name="sessie.json",
        help="Bewaar de huidige configuratie zodat je deze later kunt herladen."
    )

    # Deeloptie: genereer een base64‑code van de sessie die je kunt delen
    if st.button("🔗 Deel sessie"):
        session_data = json.dumps({
            "muurbreedte": muurbreedte,
            "panels": st.session_state.panels
        })
        session_b64 = base64.b64encode(session_data.encode()).decode()
        st.text_area(
            "Kopieer deze code en deel hem met je team. Zij kunnen de code plakken in het veld 'Laad sessie' nadat ze deze base64 hebben gedecodeerd.",
            value=session_b64,
            height=150
        )

    # Paneel roteren met bevestiging
    if st.session_state.panels:
        with st.form("rotate_form"):
            col_r1, col_r2 = st.columns([3, 1])
            roteren_select = col_r1.selectbox(
                "🔄 Kies paneel om 90° te roteren",
                options=["--"] + [p["id"] for p in st.session_state.panels],
                index=0
            )
            if col_r2.form_submit_button("Roteer"):
                if roteren_select != "--":
                    for p in st.session_state.panels:
                        if p["id"] == roteren_select:
                            p["rotation"] = (p.get("rotation", 0) + 90) % 360

        # Paneel verwijderen met bevestiging
        with st.form("delete_form"):
            col_d1, col_d2 = st.columns([3, 1])
            verwijder_select = col_d1.selectbox(
                "🗑 Kies paneel om te verwijderen",
                options=["--"] + [p["id"] for p in st.session_state.panels],
                index=0
            )
            if col_d2.form_submit_button("Verwijder"):
                if verwijder_select != "--":
                    st.session_state.panels = [p for p in st.session_state.panels if p["id"] != verwijder_select]
    else:
        st.info("Er zijn nog geen panelen om te roteren of verwijderen.")

