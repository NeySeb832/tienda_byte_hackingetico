"""Genera la presentación de sustentación sobre la plantilla institucional de la Universidad Central.

Uso (desde la raíz del repositorio, con python-pptx y Pillow instalados):
    py docs/presentacion/build_deck.py <plantilla.pptx> docs/presentacion/sustentacion-byte.pptx

La plantilla aporta fondos, logos y diseños. Se conservan su portada (diapositiva 1) y su cierre
«Gracias» (diapositiva 6); el resto se arma con sus diseños de diapositiva.
"""

from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR: Path  # carpeta temporal de trabajo (build)
MEDIA: Path  # imágenes extraídas de la plantilla (build)
FIG = ROOT / "docs" / "tutorial" / "figuras"

# Paleta tomada de la plantilla institucional.
NAVY = RGBColor(0x0B, 0x3A, 0x82)
BLUE = RGBColor(0x32, 0x59, 0xA0)
SKY = RGBColor(0x2F, 0x9B, 0xE0)
TINT = RGBColor(0xEA, 0xF2, 0xFB)
INK = RGBColor(0x1F, 0x2A, 0x3C)
MUTED = RGBColor(0x5A, 0x67, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1E, 0x8E, 0x55)
ORANGE = RGBColor(0xD9, 0x7A, 0x17)
GREY = RGBColor(0x8A, 0x94, 0xA6)

BODY = "Calibri"
APA = "Times New Roman"  # portada igual a la del documento

# Diseños de la plantilla.
L_COVER, L_HEADER, L_SECTION, L_TITLE_BAND, L_THIN, L_BLANK = range(6)


# --------------------------------------------------------------------------- helpers
def text(
    slide,
    x,
    y,
    w,
    h,
    runs,
    *,
    size=16,
    color=INK,
    bold=False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    font=BODY,
    name=None,
    spacing=None,
):
    """Caja de texto. `runs` es un str (un párrafo), o una lista de párrafos; cada párrafo es un
    str o una lista de (texto, {opciones}) para combinar estilos."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = anchor
    paras = [runs] if isinstance(runs, str) else runs
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.space_after = Pt(spacing)
        parts = [(para, {})] if isinstance(para, str) else para
        for chunk, opts in parts:
            r = p.add_run()
            r.text = chunk
            f = r.font
            f.name = opts.get("font", font)
            f.size = Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold)
            f.italic = opts.get("italic", False)
            f.color.rgb = opts.get("color", color)
    return box


def box(slide, x, y, w, h, fill=TINT, *, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=None):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        shp.name = name
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = 0.08
    return shp


def badge(slide, x, y, d, label, fill=BLUE, size=16):
    c = box(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), True, WHITE, BODY
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return c


def picture(slide, path, x, y, w, h, *, border=True, crop_h=None):
    """Imagen ajustada dentro de la caja (sin deformar), centrada."""
    src = Path(path)
    if crop_h:
        im = Image.open(src).convert("RGB")
        im = im.crop((0, 0, im.width, min(crop_h, im.height)))
        src = OUT_DIR / f"_crop_{src.stem}.png"
        im.save(src)
    iw, ih = Image.open(src).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    pic = slide.shapes.add_picture(
        str(src), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph)
    )
    if border:
        pic.line.color.rgb = RGBColor(0xC9, 0xD3, 0xE3)
        pic.line.width = Pt(0.75)
    return pic


def header_slide(prs, title, section_logo=False):
    s = prs.slides.add_slide(prs.slide_layouts[L_HEADER])
    s.shapes.title.text = title
    tf = s.shapes.title.text_frame
    for p in tf.paragraphs:
        for r in p.runs:
            r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(30), True, BODY, WHITE
    # Quitar el marcador de contenido vacío (el contenido se compone a mano).
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx == 1:
            ph._element.getparent().remove(ph._element)
    return s


def section_slide(prs, kicker, title, minutes):
    s = prs.slides.add_slide(prs.slide_layouts[L_SECTION])
    s.shapes.title.text = title
    for p in s.shapes.title.text_frame.paragraphs:
        for r in p.runs:
            r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(44), True, NAVY, BODY
    body = next(ph for ph in s.placeholders if ph.placeholder_format.idx == 1)
    body.text = f"{kicker} · {minutes}"
    for p in body.text_frame.paragraphs:
        for r in p.runs:
            r.font.size, r.font.color.rgb, r.font.name = Pt(22), BLUE, BODY
    s.shapes.add_picture(
        str(MEDIA / "image6.png"), Inches(10.2), Inches(6.13), Inches(2.67), Inches(1.06)
    )
    return s


def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt


# --------------------------------------------------------------------------- build
def build(template: Path, out: Path) -> None:
    global OUT_DIR, MEDIA
    OUT_DIR = Path(tempfile.mkdtemp(prefix="deck-"))  # recortes e imágenes de la plantilla
    MEDIA = OUT_DIR
    with zipfile.ZipFile(template) as z:
        for n in ("image6.png",):
            (MEDIA / n).write_bytes(z.read(f"ppt/media/{n}"))

    prs = Presentation(str(template))
    ids = prs.slides._sldIdLst
    # Conservar portada (1) y cierre (6); borrar las de muestra 2-5.
    for sld in list(ids)[1:5]:
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    closing = list(ids)[1]

    # 1 · Portada APA 7 -----------------------------------------------------------------
    cover = prs.slides[0]
    t = cover.shapes.title
    t.left, t.top, t.width, t.height = Inches(7.45), Inches(0.75), Inches(5.15), Inches(2.6)
    t.text_frame.vertical_anchor = MSO_ANCHOR.BOTTOM
    t.text = (
        "Construcción y prueba de penetración de una tienda en línea con vibe coding: "
        "tutorial del caso Byte"
    )
    for p in t.text_frame.paragraphs:
        p.alignment = PP_ALIGN.CENTER
        for r in p.runs:
            r.font.name, r.font.size, r.font.bold, r.font.color.rgb = APA, Pt(26), True, WHITE
    # "vibe coding" en cursiva, como en el documento.
    p = t.text_frame.paragraphs[0]
    full = p.runs[0].text
    a, b = full.split("vibe coding")
    p.runs[0].text = a
    for chunk, ital in (("vibe coding", True), (b, False)):
        r = copy.deepcopy(p.runs[0]._r)
        p._p.append(r)
        p.runs[-1].text = chunk
        p.runs[-1].font.italic = ital
    sub = next(ph for ph in cover.placeholders if ph.placeholder_format.idx == 1)
    sub.left, sub.top, sub.width, sub.height = (
        Inches(7.45),
        Inches(3.65),
        Inches(5.15),
        Inches(2.05),
    )
    lines = [
        "Neyder Sebastian Orozco Villamil",
        "Ingeniería de Sistemas, Facultad de Ingeniería y Ciencias Básicas, Universidad Central",
        "43391427: Hacking Ético",
        "Mg. Carlos Ivan Pinzon Romero",
        "13 de noviembre de 2026",
    ]
    tf = sub.text_frame
    tf.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line
    for p in tf.paragraphs:
        p.alignment = PP_ALIGN.CENTER
        p.space_after = Pt(2)
        for r in p.runs:
            r.font.name, r.font.size, r.font.color.rgb = APA, Pt(15), WHITE
    notes(
        cover,
        "0:20 — Presentación. Buenos días. Soy Neyder Orozco y presento la construcción de "
        "Byte, una tienda en línea completa hecha con vibe coding, la prueba de penetración que le "
        "hice desde Kali y la corrección de lo que encontré.",
    )

    # 2 · Agenda ------------------------------------------------------------------------
    s = prs.slides.add_slide(prs.slide_layouts[L_TITLE_BAND])
    s.shapes.title.text = "Lo que vamos a ver"
    for r in s.shapes.title.text_frame.paragraphs[0].runs:
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(36), True, NAVY, BODY
    items = [
        ("1", "La construcción", "Vibe coding guiado por un prompt maestro", "5 min"),
        ("2", "Pruebas de penetración", "Desde Kali contra la instancia en Render", "4 min"),
        ("3", "Demostración", "La tienda y el panel funcionando en vivo", "3 min"),
        ("4", "Lecciones", "Qué funcionó y qué no", "1 min"),
    ]
    for i, (n, head, sub_, mins) in enumerate(items):
        x = 0.92 + i * 2.95
        box(s, x, 2.25, 2.7, 3.6, TINT, name=f"Agenda {n}")
        badge(s, x + 0.25, 2.5, 0.75, n, NAVY, 24)
        text(s, x + 0.25, 3.45, 2.3, 0.9, head, size=20, bold=True, color=NAVY)
        text(s, x + 0.25, 4.35, 2.3, 1.0, sub_, size=14, color=MUTED)
        text(s, x + 0.25, 5.3, 2.3, 0.4, mins, size=14, bold=True, color=SKY)
    notes(
        s,
        "0:20 — Tres partes y un cierre: cómo se construyó, cómo se atacó y se corrigió, y la "
        "demostración en vivo. En total, menos de 15 minutos.",
    )

    # 3 · Sección 1 ------------------------------------------------------------------------
    s = section_slide(prs, "Parte 1", "La construcción", "5 minutos")
    notes(s, "0:05 — Empezamos por la construcción.")

    # 4 · El reto -----------------------------------------------------------------------
    s = header_slide(prs, "Byte: una tienda en línea real, construida por una IA")
    text(
        s,
        0.6,
        1.75,
        6.1,
        1.3,
        "Tienda en línea y punto de venta de videojuegos para Colombia: precios en COP con IVA, "
        "envíos por departamento y obligaciones de la Ley 1480 y la Ley 1581 (Congreso de Colombia, 2011, 2012).",
        size=16,
        color=INK,
    )
    stats = [
        ("21", "apps de Django"),
        ("10", "roles con permisos"),
        ("66", "productos reales"),
        ("OWASP", "Top 10:2025 desde el día 1"),
    ]
    for i, (value, label) in enumerate(stats):
        x = 0.6 + (i % 2) * 3.05
        y = 3.15 + (i // 2) * 1.75
        box(s, x, y, 2.85, 1.55, TINT, name=f"Dato {label}")
        text(
            s,
            x + 0.2,
            y + 0.12,
            2.5,
            0.75,
            value,
            size=34 if len(value) < 4 else 28,
            bold=True,
            color=NAVY,
        )
        text(s, x + 0.2, y + 0.9, 2.5, 0.5, label, size=14, color=MUTED)
    picture(s, FIG / "f01-inicio.jpg", 6.95, 1.75, 5.8, 4.95)
    notes(
        s,
        "1:00 — El reto: no un prototipo, sino una tienda con catálogo, carrito, pagos, panel "
        "con inventario multisede, punto de venta y analítica. Y como es para Hacking ético, la "
        "seguridad OWASP 2025 fue requisito desde el primer día, no un añadido final.",
    )

    # 5 · Método ------------------------------------------------------------------------
    s = header_slide(prs, "El método: un prompt maestro y puertas de revisión")
    text(
        s,
        0.6,
        1.75,
        5.6,
        0.5,
        "Un solo prompt de 28 000 caracteres fijó:",
        size=16,
        bold=True,
        color=NAVY,
    )
    parts = [
        ("Rol y reglas", "Arquitecto con AppSec; probar, documentar y detenerse en cada fase"),
        ("Alcance verificable", "Stack, arquitectura, roles y controles OWASP comprobables"),
        ("Plan de 10 fases", "Cada fase cierra con pruebas, análisis y commit"),
        ("Criterios de aceptación", "La definición de terminado, punto por punto"),
    ]
    for i, (h, d) in enumerate(parts):
        y = 2.35 + i * 1.08
        badge(s, 0.6, y + 0.08, 0.6, str(i + 1), BLUE, 18)
        text(s, 1.35, y, 4.9, 0.4, h, size=16, bold=True, color=INK)
        text(s, 1.35, y + 0.38, 4.9, 0.6, d, size=14, color=MUTED)
    # Ciclo de cada fase
    box(s, 6.75, 1.75, 6.0, 4.95, TINT, name="Ciclo de cada fase")
    text(s, 7.0, 1.9, 5.5, 0.4, "Ciclo de cada fase", size=16, bold=True, color=NAVY)
    steps = [
        "Prompt de la fase",
        "La IA implementa",
        "15 verificaciones",
        "Bitácora y capturas",
        "Commit en su rama",
        "Revisión humana",
    ]
    for i, st in enumerate(steps):
        col, row = i % 2, i // 2
        x = 7.05 + col * 2.85
        y = 2.4 + row * 1.2
        b = box(s, x, y, 2.55, 0.95, WHITE, line=SKY, name=f"Paso {i + 1}")
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = f"{i + 1}. {st}"
        r.font.size, r.font.color.rgb, r.font.name, r.font.bold = Pt(14), INK, BODY, True
    text(
        s,
        7.0,
        6.1,
        5.5,
        0.45,
        "Si algo falla, se corrige y se repite antes del commit",
        size=13,
        color=MUTED,
        align=PP_ALIGN.CENTER,
    )
    notes(
        s,
        "1:15 — El corazón del método. No fui pidiendo cosas sueltas: escribí un prompt maestro "
        "con el rol de la IA, reglas de trabajo, el alcance escrito para poder verificarlo, un plan "
        "de diez fases y criterios de aceptación. La regla clave: al final de cada fase la IA corre "
        "las pruebas y el análisis de seguridad, documenta, hace commit y se detiene hasta que yo "
        "reviso. Eso convierte el vibe coding en un proceso controlado.",
    )

    # 6 · Arquitectura ------------------------------------------------------------------
    s = header_slide(prs, "Arquitectura desplegada en Render")
    layers = [
        ("Visitante", "Navegador · HTMX · Alpine CSP · Tailwind", WHITE, NAVY),
        ("Cloudflare", "TLS 1.2/1.3 · WAF · escribe CF-Connecting-IP", TINT, NAVY),
        ("Servicio web", "Django 5.2 LTS + gunicorn · CSP con nonce · MFA · axes", BLUE, WHITE),
    ]
    for i, (h, d, fill, fg) in enumerate(layers):
        y = 1.8 + i * 1.12
        box(s, 0.6, y, 7.2, 0.92, fill, line=SKY, name=h)
        text(
            s, 0.85, y + 0.08, 2.0, 0.75, h, size=17, bold=True, color=fg, anchor=MSO_ANCHOR.MIDDLE
        )
        text(s, 2.85, y + 0.08, 4.8, 0.75, d, size=14, color=fg, anchor=MSO_ANCHOR.MIDDLE)
    backs = [
        ("PostgreSQL 17", "Fuente de verdad: CHECK, triggers"),
        ("Valkey + Celery", "Tareas solo JSON, Beat"),
        ("DuckDB + Parquet", "BI medallón, sin PII"),
    ]
    for i, (h, d) in enumerate(backs):
        x = 0.6 + i * 2.45
        box(s, x, 5.2, 2.25, 1.45, NAVY, name=h)
        text(s, x + 0.15, 5.3, 1.95, 0.45, h, size=15, bold=True, color=WHITE)
        text(s, x + 0.15, 5.78, 1.95, 0.8, d, size=13, color=WHITE)
    box(s, 8.25, 1.8, 4.5, 4.85, TINT, name="Principios")
    text(s, 8.5, 1.95, 4.0, 0.4, "Decisiones clave (17 ADR)", size=16, bold=True, color=NAVY)
    text(
        s,
        8.5,
        2.5,
        4.0,
        4.0,
        [
            "Monolito modular con capa de servicios",
            "UUID públicos, nunca la PK interna",
            "Dinero en Decimal con IVA incluido",
            "Stock con bloqueo de filas: sin sobreventa",
            "Libros append-only: auditoría, kardex, precios",
            "Secretos solo por variables de entorno",
        ],
        size=14,
        color=INK,
        spacing=8,
    )
    notes(
        s,
        "1:00 — Así quedó en producción. Cloudflare delante, Django detrás, PostgreSQL como "
        "fuente de verdad con restricciones y triggers, Celery para tareas y DuckDB para la "
        "analítica. Cada decisión con alternativas quedó documentada en un ADR; hay 17.",
    )

    # 7 · 10 fases ----------------------------------------------------------------------
    s = header_slide(prs, "Diez fases, cada una cerrada con pruebas")
    cd = CategoryChartData()
    cd.categories = [f"F{i}" for i in range(1, 10)]
    cd.add_series("Pruebas que pasan", (323, 448, 530, 582, 679, 699, 713, 724, 727))
    gf = s.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75), Inches(7.4), Inches(4.95), cd
    )
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = "Pruebas automáticas al cerrar cada fase"
    tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
    tr.font.size, tr.font.bold, tr.font.color.rgb, tr.font.name = Pt(16), True, NAVY, BODY
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb, dl.font.name = Pt(12), INK, BODY
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = BLUE
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE1, 0xE6, 0xEF)
    va.tick_labels.font.size, va.tick_labels.font.color.rgb = Pt(11), MUTED
    va.format.line.fill.background()
    ca = ch.category_axis
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(12), MUTED
    phases = [
        "Fundaciones",
        "Usuarios y seguridad",
        "Catálogo y precios",
        "Carrito y pagos",
        "Panel administrativo",
        "Valor agregado",
        "Big data / BI",
        "Endurecimiento",
        "Despliegue",
        "Documentación",
    ]
    text(s, 8.35, 1.75, 4.4, 0.4, "Las fases", size=16, bold=True, color=NAVY)
    text(
        s,
        8.35,
        2.2,
        4.4,
        4.5,
        [[(f"F{i + 1}  ", {"bold": True, "color": BLUE}), (ph, {})] for i, ph in enumerate(phases)],
        size=14,
        color=INK,
        spacing=4,
    )
    notes(
        s,
        "1:00 — Diez fases, de las fundaciones a la documentación. Cada barra son las pruebas "
        "que pasaban al cerrar la fase: de 323 a 727, con cobertura siempre por encima del 93 %. "
        "Nada avanzaba si algo fallaba.",
    )

    # 8 · Verificación ------------------------------------------------------------------
    s = header_slide(prs, "Seguridad verificada en cada fase, no al final")
    big = [
        ("727", "pruebas · 93 % de cobertura"),
        ("0", "hallazgos de semgrep"),
        ("0", "fallos en OWASP ZAP baseline"),
    ]
    for i, (n, label) in enumerate(big):
        x = 0.6 + i * 4.1
        box(s, x, 1.8, 3.85, 1.9, NAVY, name=f"Cifra {label}")
        text(s, x + 0.25, 1.9, 3.4, 1.0, n, size=54, bold=True, color=WHITE)
        text(s, x + 0.25, 2.95, 3.4, 0.6, label, size=15, color=WHITE)
    text(
        s,
        0.6,
        3.95,
        7.4,
        0.4,
        "Lo que verifica cada cierre de fase (15 chequeos)",
        size=16,
        bold=True,
        color=NAVY,
    )
    checks = [
        "pytest con PostgreSQL real",
        "ruff · black · mypy",
        "bandit y semgrep (SAST)",
        "pip-audit y Trivy",
        "check --deploy de Django",
        "Cabeceras: CSP, HSTS, XFO",
        "Integridad de las librerías JS",
        "Matriz de permisos y auditoría",
        "SBOM y ZAP baseline",
    ]
    for i, c in enumerate(checks):
        col, row = i % 3, i // 3
        text(
            s,
            0.6 + col * 2.5,
            4.45 + row * 0.62,
            2.4,
            0.55,
            [[("✓ ", {"bold": True, "color": GREEN}), (c, {})]],
            size=13,
            color=INK,
        )
    box(s, 8.25, 3.95, 4.5, 2.3, TINT, name="La IA también falla")
    text(s, 8.5, 4.1, 4.0, 0.4, "La IA también se equivoca", size=16, bold=True, color=ORANGE)
    text(
        s,
        8.5,
        4.55,
        4.0,
        2.0,
        "En la Fase 2 el commit dijo «semgrep sin hallazgos», pero hubo 3. La salida guardada "
        "lo delató y se corrigió. Lección: verificar la evidencia, no el resumen.",
        size=14,
        color=INK,
    )
    notes(
        s,
        "1:00 — La seguridad se verificó en cada fase con las mismas 15 comprobaciones que corre "
        "el CI. Y algo honesto: la IA se equivocó. En la fase 2 resumió mal un resultado de "
        "semgrep. Lo detecté porque guardamos la salida completa. Por eso el método exige evidencia.",
    )

    # 9 · Sección 2 ---------------------------------------------------------------------------
    s = section_slide(prs, "Parte 2", "Pruebas de penetración", "4 minutos")
    notes(s, "0:05 — Ahora, el atacante.")

    # 10 · Alcance y metodología --------------------------------------------------------
    s = header_slide(prs, "Alcance y metodología desde Kali Linux")
    flow = ["Reconocimiento", "Escaneo", "Análisis", "Explotación", "Post-explotación"]
    for i, f in enumerate(flow):
        x = 0.6 + i * 2.42
        b = box(
            s,
            x,
            1.85,
            2.5,
            1.0,
            BLUE if i % 2 == 0 else NAVY,
            shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON,
            name=f"Fase pentest {i + 1}",
        )
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        for j, line in enumerate(f.split("\n")):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = line
            r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(14), True, WHITE, BODY
        tf.margin_left = tf.margin_right = Inches(0.02)
        tf.word_wrap = False
    cols = [
        (
            "Alcance",
            [
                "Solo byte-web-v9h4.onrender.com",
                "13 nov. 2026 · 11:13 a 12:25 UTC",
                "Sin denegación de servicio",
                "Solo usuarios de demostración",
            ],
        ),
        (
            "Enfoque",
            [
                "Caja negra contra producción",
                "Pruebas autenticadas por rol",
                "Revisión del código (caja gris)",
                "OWASP Top 10 2021 y 2025 (OWASP Foundation, 2021, 2025)",
            ],
        ),
        (
            "Herramientas",
            [
                "whois, dig y openssl",
                "numasec: rastreo, fuzzing, sondas",
                "curl y scripts propios",
                "pip-audit · 45 evidencias con SHA-256",
            ],
        ),
    ]
    for i, (h, items_) in enumerate(cols):
        x = 0.6 + i * 4.1
        box(s, x, 3.2, 3.85, 3.0, TINT, name=h)
        text(s, x + 0.25, 3.35, 3.4, 0.4, h, size=16, bold=True, color=NAVY)
        text(s, x + 0.25, 3.85, 3.4, 2.3, items_, size=15, color=INK, spacing=6)
    notes(
        s,
        "1:00 — La prueba se hizo desde Kali contra la instancia real en Render, con las cinco "
        "fases clásicas. El alcance fue solo nuestro host, sin denegación de servicio y con los "
        "usuarios demo. Combinamos caja negra, pruebas autenticadas y revisión del código para "
        "explicar las causas. Cada evidencia quedó con su hash.",
    )

    # 11 · Lo que resistió --------------------------------------------------------------
    s = header_slide(prs, "Lo que resistió: control de acceso e inyección")
    tests = [
        ("IDOR", "Dirección de otro cliente por UUID", "404"),
        ("Escalada vertical", "Cliente pide /panel/", "403"),
        ("MFA del personal", "Vendedor solo con contraseña", "Pide TOTP"),
        ("Inyección SQL", "' OR 1=1-- en la búsqueda", "WAF + ORM"),
        ("XSS reflejado", "<script> en la búsqueda", "Escapado"),
        ("CSRF", "POST al carrito sin token", "403"),
    ]
    for i, (h, d, res) in enumerate(tests):
        col, row = i % 2, i // 2
        x = 0.6 + col * 3.75
        y = 1.8 + row * 1.62
        box(s, x, y, 3.55, 1.45, TINT, name=h)
        text(s, x + 0.2, y + 0.12, 2.0, 0.4, h, size=15, bold=True, color=NAVY)
        text(s, x + 0.2, y + 0.55, 2.0, 0.8, d, size=13, color=MUTED)
        pill = box(s, x + 2.35, y + 0.42, 1.05, 0.6, GREEN, name=f"Resultado {h}")
        tf = pill.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_right = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = res
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(12), True, WHITE, BODY
    picture(s, FIG / "p07-xss-escapado.jpg", 8.25, 1.8, 4.5, 2.31)
    text(
        s,
        8.25,
        4.25,
        4.5,
        1.3,
        "La búsqueda con un script se muestra como texto: el autoescapado "
        "de Django neutraliza el XSS.",
        size=13,
        color=MUTED,
    )
    notes(
        s,
        "1:00 — Lo importante primero: lo que debía resistir, resistió. No se pudo ver el pedido "
        "de otro cliente, un cliente no entra al panel, el personal no entra sin segundo factor, la "
        "inyección SQL la bloquean el WAF y el ORM, y el XSS sale escapado.",
    )

    # 12 · Hallazgos ---------------------------------------------------------------------
    s = header_slide(prs, "Hallazgos: el problema estaba en el despliegue")
    rows = [
        ("ID", "Hallazgo", "OWASP 2025", "Severidad", "Estado"),
        (
            "PT-01",
            "Protección contra fuerza bruta inefectiva en el login",
            "A07",
            "Media · 5,3",
            "Corregido",
        ),
        (
            "PT-04",
            "Secreto TOTP público en las cuentas demo del personal",
            "A07",
            "Media · 4,8",
            "Corregido",
        ),
        ("PT-02", "Panel del personal descubrible en /panel/", "A02", "Informativa", "Aceptado"),
        ("PT-03", "|safe sobre help_text en dos plantillas", "A05", "Informativa", "Abierto"),
    ]
    widths = [1.0, 6.0, 1.7, 1.8, 1.6]
    tbl = s.shapes.add_table(
        len(rows),
        len(widths),
        Inches(0.6),
        Inches(1.85),
        Inches(sum(widths)),
        Inches(0.62 * len(rows)),
    ).table
    for j, w in enumerate(widths):
        tbl.columns[j].width = Inches(w)
    for i, cells in enumerate(rows):
        tbl.rows[i].height = Inches(0.62)
        for j, val in enumerate(cells):
            cell = tbl.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if i == 0 else (WHITE if i % 2 else TINT)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.text = val
            r = tf.paragraphs[0].runs[0]
            r.font.size, r.font.name = Pt(15 if i == 0 else 14), BODY
            r.font.bold = i == 0 or j == 0
            r.font.color.rgb = WHITE if i == 0 else INK
            if i and j == 3:
                r.font.color.rgb = ORANGE if "Media" in val else GREY
                r.font.bold = True
            if i and j == 4:
                r.font.color.rgb = GREEN if val == "Corregido" else MUTED
                r.font.bold = True
    box(s, 0.6, 5.2, 12.1, 1.45, TINT, name="Mensaje hallazgos")
    text(
        s,
        0.85,
        5.3,
        11.6,
        1.25,
        [
            [
                (
                    "Severidad con CVSS 3.1 (FIRST, 2019). Por qué no lo vieron 727 pruebas: ",
                    {"bold": True, "color": NAVY},
                ),
                (
                    "ambos hallazgos medios dependían de cómo se desplegó la app (un proxy delante y un "
                    "comando de demostración en producción), no del código que las pruebas ejercían.",
                    {},
                ),
            ]
        ],
        size=16,
        color=INK,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "1:00 — Cuatro hallazgos, ninguno crítico. Dos medios en autenticación: el login no "
        "bloqueaba la fuerza bruta y las cuentas demo del personal tenían un secreto TOTP publicado "
        "en el repositorio. Lo interesante: ninguno estaba en el código que probamos, sino en el "
        "despliegue.",
    )

    # 13 · PT-01: causa, corrección y re-prueba ---------------------------------------------
    s = header_slide(prs, "PT-01: causa raíz, corrección y re-prueba")
    steps13 = [
        (
            "Causa raíz",
            "django-ipware nunca se instaló. Todos los controles por IP veían el "
            "balanceador de Render (REMOTE_ADDR), no al cliente.",
        ),
        (
            "Corrección",
            "Una sola función de IP para axes, ratelimit, allauth y auditoría; en Render "
            "lee CF-Connecting-IP. CAPTCHA en cada login. ADR-0018.",
        ),
    ]
    for i, (h, d) in enumerate(steps13):
        y = 1.8 + i * 1.55
        badge(s, 0.6, y, 0.55, str(i + 1), NAVY, 16)
        text(s, 1.3, y - 0.03, 4.6, 0.4, h, size=16, bold=True, color=NAVY)
        text(s, 1.3, y + 0.38, 4.6, 1.1, d, size=14, color=INK)
    box(s, 0.6, 4.95, 2.6, 1.7, TINT, name="Antes")
    text(s, 0.8, 5.05, 2.3, 0.4, "Antes", size=14, bold=True, color=MUTED)
    text(s, 0.8, 5.45, 2.3, 1.1, "30 intentos sin bloqueo", size=18, bold=True, color=ORANGE)
    box(s, 3.4, 4.95, 2.6, 1.7, NAVY, name="Después")
    text(s, 3.6, 5.05, 2.3, 0.4, "Después", size=14, bold=True, color=WHITE)
    text(
        s,
        3.6,
        5.45,
        2.3,
        1.1,
        "429 al quinto intento, aun con IP falsa",
        size=18,
        bold=True,
        color=WHITE,
    )
    picture(s, FIG / "p09-retest-pt01.png", 6.3, 1.8, 6.45, 4.85, border=False)
    notes(
        s,
        "1:00 — La causa real fue más profunda que la del informe: la librería que leía la IP "
        "detrás del proxy nunca se instaló, así que el bloqueo contaba la IP del balanceador. Lo "
        "corregí con una sola función de IP para todos los controles y CAPTCHA en cada login. La "
        "re-prueba desde Kali: antes, 30 intentos sin bloqueo; ahora, bloqueo al quinto, incluso "
        "falsificando la IP. PT-04 también se corrigió: el secreto TOTP ya no llega a producción.",
    )

    # 14 · Sección 3 ----------------------------------------------------------------------------
    s = section_slide(prs, "Parte 3", "Demostración en vivo", "3 minutos")
    notes(s, "0:05 — Vamos a la tienda en vivo.")

    # 15 · Guion de la demo ------------------------------------------------------------
    s = header_slide(prs, "Demostración: byte-web-v9h4.onrender.com")
    demo = [
        ("Buscar «plaistation»", "La búsqueda tolera errores de digitación"),
        ("Configurar PS5 Slim", "Cambia edición y condición: el precio cambia en vivo"),
        ("Comprar como cliente demo", "Carrito → login con CAPTCHA → checkout → pago simulado"),
        ("Pedido y factura PDF", "Estado pagado, línea de tiempo y factura de prueba"),
        ("Intentar entrar al panel", "El cliente recibe 403; el personal exige MFA"),
    ]
    for i, (h, d) in enumerate(demo):
        y = 1.8 + i * 0.98
        badge(s, 0.6, y + 0.05, 0.55, str(i + 1), BLUE, 16)
        text(s, 1.3, y, 5.1, 0.4, h, size=16, bold=True, color=INK)
        text(s, 1.3, y + 0.4, 5.1, 0.5, d, size=14, color=MUTED)
    shots = [
        (FIG / "f03-ficha.jpg", "Ficha con configurador"),
        (FIG / "f04-checkout.jpg", "Checkout"),
        (FIG / "f09-e2e-pago.jpg", "Pago aprobado"),
        (FIG / "f07-bi.jpg", "Tablero de BI"),
    ]
    for i, (img, cap) in enumerate(shots):
        col, row = i % 2, i // 2
        x = 6.75 + col * 3.05
        y = 1.8 + row * 2.45
        picture(s, img, x, y, 2.9, 1.95)
        text(s, x, y + 1.98, 2.9, 0.35, cap, size=12, color=MUTED, align=PP_ALIGN.CENTER)
    notes(
        s,
        "2:45 — DEMO EN VIVO (respaldo: las capturas de la derecha si falla la red). "
        "1) Buscar «plaistation» en el inicio. 2) Abrir PS5 Slim y cambiar la configuración: el "
        "precio y el SKU cambian. 3) Agregar al carrito, iniciar sesión con cliente@byte.test "
        "(contraseña: variable BYTE_DEMO_PASSWORD en Render; el widget de CAPTCHA aún dice «solo "
        "para pruebas»), recoger en tienda y pagar en la pasarela de pruebas. 4) Abrir el pedido "
        "pagado y descargar la factura PDF. 5) Con el cliente, ir a /panel/: 403. Si se muestra el "
        "panel con el gerente, activar antes su TOTP en el celular (desde PT-04 cada cuenta del "
        "personal configura su propio autenticador en el primer ingreso).",
    )

    # 16 · Lecciones ----------------------------------------------------------------------
    s = header_slide(prs, "Lecciones para construir con vibe coding")
    lessons = [
        (
            "Especificar para verificar",
            "Un prompt maestro con requisitos comprobables rinde más que mil pedidos sueltos",
        ),
        ("Puertas humanas", "Detenerse en cada fase permitió corregir el rumbo a tiempo"),
        ("Evidencia, no resúmenes", "La IA se equivocó; la salida guardada lo delató"),
        ("Probar lo desplegado", "Los hallazgos estaban en el despliegue, no en el código"),
    ]
    for i, (h, d) in enumerate(lessons):
        col, row = i % 2, i // 2
        x = 0.6 + col * 6.15
        y = 1.8 + row * 1.85
        box(s, x, y, 5.95, 1.6, TINT, name=h)
        badge(s, x + 0.25, y + 0.3, 0.7, str(i + 1), NAVY, 20)
        text(s, x + 1.2, y + 0.25, 4.5, 0.45, h, size=18, bold=True, color=NAVY)
        text(s, x + 1.2, y + 0.75, 4.5, 0.9, d, size=14, color=INK)
    text(
        s,
        0.6,
        5.65,
        12.1,
        0.9,
        [
            [
                ("Conclusión: ", {"bold": True, "color": NAVY}),
                (
                    "el vibe coding (Karpathy, 2025) sirve para software serio cuando se trata como un método, y "
                    "la prueba de penetración es su última puerta de revisión.",
                    {"italic": True},
                ),
            ]
        ],
        size=17,
        color=INK,
    )
    notes(
        s,
        "1:00 — Cuatro lecciones. Especificar para poder verificar. Detenerse en cada fase. "
        "Confiar en la evidencia, no en el resumen de la IA. Y probar el sistema desplegado. El "
        "vibe coding funciona para algo serio cuando es un método, y el pentest cierra el ciclo.",
    )

    # 17 · Referencias APA ---------------------------------------------------------------
    s = prs.slides.add_slide(prs.slide_layouts[L_THIN])
    text(
        s,
        0.92,
        0.4,
        11.5,
        0.8,
        "Referencias",
        size=32,
        bold=True,
        color=NAVY,
        align=PP_ALIGN.CENTER,
    )
    refs = [
        [
            ("American Psychological Association. (2020). ", {}),
            ("Publication manual of the American Psychological Association", {"italic": True}),
            (" (7.ª ed.). https://doi.org/10.1037/0000165-000", {}),
        ],
        [
            ("Anthropic. (s. f.). ", {}),
            ("Claude Code overview", {"italic": True}),
            (". Claude Docs. https://docs.claude.com/en/docs/claude-code/overview", {}),
        ],
        [
            ("Congreso de Colombia. (2011). ", {}),
            (
                "Ley 1480 de 2011 por medio de la cual se expide el Estatuto del Consumidor",
                {"italic": True},
            ),
            (".", {}),
        ],
        [
            ("Congreso de Colombia. (2012). ", {}),
            (
                "Ley Estatutaria 1581 de 2012 por la cual se dictan disposiciones generales para la protección de datos personales",
                {"italic": True},
            ),
            (".", {}),
        ],
        [
            ("FIRST. (2019). ", {}),
            ("Common Vulnerability Scoring System v3.1: Specification document", {"italic": True}),
            (". https://www.first.org/cvss/v3.1/specification-document", {}),
        ],
        [
            ("Karpathy, A. (2025, 2 de febrero). ", {}),
            (
                "There’s a new kind of coding I call “vibe coding”",  # noqa: RUF001 - título original
                {"italic": True},
            ),
            (" [Publicación]. X. https://x.com/karpathy/status/1886192184808149383", {}),
        ],
        [
            ("OffSec. (s. f.). ", {}),
            ("Kali Linux", {"italic": True}),
            (" (Ver. Rolling). https://www.kali.org/", {}),
        ],
        [
            ("OWASP Foundation. (2021). ", {}),
            ("OWASP Top 10:2021", {"italic": True}),
            (". https://owasp.org/Top10/", {}),
        ],
        [
            ("OWASP Foundation. (2025). ", {}),
            ("OWASP Top 10:2025", {"italic": True}),
            (". https://owasp.org/Top10/2025/", {}),
        ],
    ]
    rb = text(s, 0.92, 1.35, 11.5, 5.7, refs, size=13, color=INK, font=APA, spacing=5)
    for p in rb.text_frame.paragraphs:  # sangría francesa (APA 7)
        ppr = p._p.get_or_add_pPr()
        ppr.set("marL", str(Emu(Inches(0.5))))
        ppr.set("indent", str(-Emu(Inches(0.5))))
    notes(s, "Referencias en APA 7 (no se expone).")

    # 18 · Cierre: mover «Gracias» al final y agregar texto ------------------------------
    ids.remove(closing)
    ids.append(closing)
    thanks = prs.slides[len(prs.slides) - 1]
    text(
        thanks,
        2.0,
        5.45,
        9.33,
        1.5,
        [
            [("¿Preguntas?", {"size": 24, "bold": True})],
            "byte-web-v9h4.onrender.com",
            "github.com/NeySeb832/tienda_byte_hackingetico",
        ],
        size=16,
        color=WHITE,
        align=PP_ALIGN.CENTER,
    )
    notes(thanks, "Gracias. Quedo atento a sus preguntas.")

    # Las diapositivas conservadas de la plantilla chocan de nombre con las nuevas (slide6.xml):
    # renumerar todas en el orden final antes de guardar.
    prs.part.rename_slide_parts([sld.rId for sld in ids])
    prs.save(str(out))
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    print(f"ok: {out} ({len(prs.slides)} diapositivas)")  # noqa: T201 - CLI script


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
