#!/usr/bin/env python3
# ghost-plymouth-gen.py
# Genera los frames PNG del tema Plymouth con el chibi de Dokkaebi
# Requiere: pip install Pillow --break-system-packages

import os, math, sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ghost] Instalando Pillow...")
    os.system("pip install Pillow --break-system-packages -q")
    from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "/usr/share/plymouth/themes/ghost-eyes"
W, H = 1920, 1080

# ── Paleta de colores (basada en la imagen enviada) ──────────
BG          = (0,   0,   0)        # negro puro
FACE        = (245, 240, 230)      # blanco crema cara
OUTLINE     = (10,  10,  10)       # negro bordes
HAIR_WHITE  = (240, 235, 225)      # blanco pelo
HAIR_ORANGE = (220, 140,  20)      # naranja/dorado rayas pelo
GLASSES_OR  = (210, 130,  15)      # naranja gafas
GLASSES_IN  = (195, 115,   5)      # naranja oscuro interior lentes
HORN        = (230, 225, 215)      # color cuernos
EYE_WHITE   = (40,  40,  40)       # pupilas oscuras (cejas bajas)
MOUTH_LINE  = (60,  60,  60)       # línea boca
PATTERN_COL = (22,  22,  22)       # patrón fondo (x y gotas)
TEXT_COL    = (255, 255, 255)      # texto coreano blanco
ORANGE_GLOW = (200,  90,   0)      # naranja ghost-eyes

def draw_background(draw, frame_n, total):
    """Fondo negro con patrón de X y gotas como en la imagen original."""
    draw.rectangle([0, 0, W, H], fill=BG)
    # Patrón de fondo: X y gotas en cuadrícula
    spacing = 48
    for y in range(0, H, spacing):
        for x in range(0, W, spacing):
            cx, cy = x + spacing//2, y + spacing//2
            # Alternar X y gota
            if (x//spacing + y//spacing) % 2 == 0:
                # Cruz / X
                s = 6
                draw.line([(cx-s, cy-s),(cx+s, cy+s)], fill=PATTERN_COL, width=1)
                draw.line([(cx+s, cy-s),(cx-s, cy+s)], fill=PATTERN_COL, width=1)
            else:
                # Gota (óvalo pequeño)
                draw.ellipse([cx-4, cy-6, cx+4, cy+4], outline=PATTERN_COL, width=1)

def draw_dokkaebi_chibi(draw, cx, cy, scale=1.0, alpha_frame=1.0):
    """Dibuja el chibi de Dokkaebi exactamente como la imagen."""
    s = scale

    def sp(x): return int(x * s)  # scale point

    # ── CUERNOS (detrás de la cara) ──────────────────────────
    # Cuerno izquierdo
    horn_pts_l = [
        (cx + sp(-82), cy + sp(-60)),
        (cx + sp(-95), cy + sp(-110)),
        (cx + sp(-70), cy + sp(-85)),
    ]
    draw.polygon(horn_pts_l, fill=HORN, outline=OUTLINE)
    # Cuerno derecho
    horn_pts_r = [
        (cx + sp(82),  cy + sp(-60)),
        (cx + sp(95),  cy + sp(-110)),
        (cx + sp(70),  cy + sp(-85)),
    ]
    draw.polygon(horn_pts_r, fill=HORN, outline=OUTLINE)

    # ── CARA BASE (círculo grande) ────────────────────────────
    face_r = sp(100)
    draw.ellipse(
        [cx - face_r, cy - face_r, cx + face_r, cy + face_r],
        fill=FACE, outline=OUTLINE, width=sp(4)
    )

    # ── PELO BLANCO (parte superior, sobre la cara) ──────────
    # Franja blanca de pelo — forma redondeada arriba
    hair_pts = [
        (cx - sp(98), cy - sp(30)),
        (cx - sp(105), cy - sp(60)),
        (cx - sp(85), cy - sp(95)),
        (cx - sp(50), cy - sp(108)),
        (cx,           cy - sp(112)),
        (cx + sp(50), cy - sp(108)),
        (cx + sp(85), cy - sp(95)),
        (cx + sp(105), cy - sp(60)),
        (cx + sp(98), cy - sp(30)),
    ]
    draw.polygon(hair_pts, fill=HAIR_WHITE, outline=OUTLINE, width=sp(3))

    # ── RAYAS NARANJAS DEL PELO ───────────────────────────────
    # 3 rayas diagonales naranjas sobre el pelo
    stripe_data = [
        # (x_start_offset, ancho_raya)
        (-50, 18),
        (-18, 16),
        ( 14, 14),
    ]
    for ox, sw in stripe_data:
        pts = [
            (cx + sp(ox),        cy - sp(108)),
            (cx + sp(ox + sw),   cy - sp(108)),
            (cx + sp(ox + sw + 30), cy - sp(40)),
            (cx + sp(ox + 12),   cy - sp(40)),
        ]
        draw.polygon(pts, fill=HAIR_ORANGE)

    # ── OREJAS PEQUEÑAS (laterales) ──────────────────────────
    # Oreja izquierda
    draw.ellipse([cx - sp(108), cy - sp(20), cx - sp(88), cy + sp(8)],
                 fill=FACE, outline=OUTLINE, width=sp(2))
    # Oreja derecha
    draw.ellipse([cx + sp(88), cy - sp(20), cx + sp(108), cy + sp(8)],
                 fill=FACE, outline=OUTLINE, width=sp(2))

    # ── GAFAS ─────────────────────────────────────────────────
    # Marco izquierdo — lente grande naranja
    gl = sp(38)  # radio lente
    gox = sp(38) # distancia del centro
    goy = sp(5)  # altura

    # Lente izquierda
    draw.ellipse([cx - gox - gl, cy + goy - gl, cx - gox + gl, cy + goy + gl],
                 fill=GLASSES_IN, outline=GLASSES_OR, width=sp(5))
    # Lente derecha
    draw.ellipse([cx + gox - gl, cy + goy - gl, cx + gox + gl, cy + goy + gl],
                 fill=GLASSES_IN, outline=GLASSES_OR, width=sp(5))
    # Puente entre lentes
    draw.line([(cx - gox + gl, cy + goy), (cx + gox - gl, cy + goy)],
              fill=GLASSES_OR, width=sp(4))
    # Patillas
    draw.line([(cx - gox - gl, cy + goy), (cx - sp(98), cy + goy - sp(5))],
              fill=GLASSES_OR, width=sp(3))
    draw.line([(cx + gox + gl, cy + goy), (cx + sp(98), cy + goy - sp(5))],
              fill=GLASSES_OR, width=sp(3))

    # Ojos (pupilas bajas dentro de las gafas — expresión seria)
    eye_r = sp(18)
    # Ojo izquierdo
    draw.ellipse([cx - gox - eye_r//2, cy + goy - sp(4),
                  cx - gox + eye_r//2, cy + goy + sp(16)],
                 fill=EYE_WHITE)
    # Ojo derecho
    draw.ellipse([cx + gox - eye_r//2, cy + goy - sp(4),
                  cx + gox + eye_r//2, cy + goy + sp(16)],
                 fill=EYE_WHITE)

    # Cejas bajas (expresión seria/aburrida)
    brow_y = cy + goy - sp(24)
    draw.line([(cx - gox - sp(28), brow_y), (cx - gox + sp(28), brow_y + sp(6))],
              fill=OUTLINE, width=sp(4))
    draw.line([(cx + gox - sp(28), brow_y + sp(6)), (cx + gox + sp(28), brow_y)],
              fill=OUTLINE, width=sp(4))

    # ── NARIZ (pequeño punto) ─────────────────────────────────
    draw.ellipse([cx - sp(4), cy + sp(38), cx + sp(4), cy + sp(46)],
                 fill=OUTLINE)

    # ── BOCA (línea recta — expresión seria) ─────────────────
    draw.line([(cx - sp(22), cy + sp(62)), (cx + sp(22), cy + sp(62))],
              fill=MOUTH_LINE, width=sp(3))

def draw_korean_text(draw, cx, cy, face_r, scale, font_path=None):
    """Dibuja el texto coreano '까불지 마' debajo de la cara."""
    text = "까불지 마"
    font_size = int(42 * scale)
    font = None
    # Lista ampliada de rutas de fuentes — cubre Kali, Debian, Ubuntu, VMs
    FONT_PATHS = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    # Calcular posición centrada
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        # Pillow < 9.2 usa textsize en vez de textbbox
        try:
            tw, _ = draw.textsize(text, font=font)
        except Exception:
            tw = font_size * len(text)

    text_x = cx - tw // 2
    text_y = cy + int(face_r * scale) + int(20 * scale)
    draw.text((text_x, text_y), text, fill=TEXT_COL, font=font)

def draw_progress_bar(draw, frame_n, total):
    """Barra de carga naranja en la parte inferior."""
    bar_h = 3
    bar_y = H - 60
    bar_w = W - 200
    bar_x = 100
    progress = frame_n / max(total - 1, 1)

    # Fondo barra
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                   fill=(25, 10, 0))
    # Progreso
    filled = int(bar_w * progress)
    if filled > 0:
        draw.rectangle([bar_x, bar_y, bar_x + filled, bar_y + bar_h],
                       fill=ORANGE_GLOW)
    # Texto GHOST EYES debajo
    try:
        fnt = ImageFont.load_default()
    except:
        fnt = None
    draw.text((bar_x, bar_y + 10), "GHOST EYES", fill=(80, 35, 0), font=fnt)

def generate_frames(n_frames=24, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    print(f"[ghost-plymouth] Generando {n_frames} frames en {output_dir}/")

    center_x = W // 2
    center_y = H // 2 - 60  # un poco arriba del centro

    for i in range(n_frames):
        img  = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # Fondo con patrón
        draw_background(draw, i, n_frames)

        # Animación de aparición (fade-in en primeros frames, estático después)
        progress = i / max(n_frames - 1, 1)
        if progress < 0.3:
            # Fase 1: aparece desde abajo
            offset_y = int((1 - progress / 0.3) * 40)
            scale = 0.85 + 0.15 * (progress / 0.3)
        elif progress > 0.85:
            # Fase 3: ligero pulso de salida
            pulse = math.sin((progress - 0.85) / 0.15 * math.pi) * 0.02
            offset_y = 0
            scale = 1.0 + pulse
        else:
            # Fase 2: estático
            offset_y = 0
            scale = 1.0

        # Dibujar chibi
        draw_dokkaebi_chibi(draw, center_x, center_y + offset_y, scale=scale)

        # Texto coreano
        draw_korean_text(draw, center_x, center_y + offset_y, 100, scale)

        # Barra de progreso
        draw_progress_bar(draw, i, n_frames)

        # Guardar frame
        path = os.path.join(output_dir, f"frame_{i:04d}.png")
        img.save(path, "PNG")
        print(f"  [{i+1:2d}/{n_frames}] {path}")

    print(f"\n[ghost-plymouth] Frames generados correctamente.")
    return output_dir

def install_theme():
    """Instala el tema Plymouth y lo activa."""
    if os.geteuid() != 0:
        print("[!] Necesita root para instalar el tema Plymouth.")
        return

    theme_dir = OUTPUT_DIR
    generate_frames(output_dir=theme_dir)

    # Crear archivo .plymouth
    plymouth_conf = f"""[Plymouth Theme]
Name=ghost-eyes
Description=GHOST EYES - Dokkaebi Boot Theme
ModuleName=script

[script]
ImageDir={theme_dir}
ScriptFile={theme_dir}/ghost-eyes.script
"""
    with open(f"{theme_dir}/ghost-eyes.plymouth", "w") as f:
        f.write(plymouth_conf)

    # Script Plymouth para reproducir los frames
    script = """
Window.SetBackgroundTopColor(0.0, 0.0, 0.0);
Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);

frames = [];
for (i = 0; i < 24; i++) {
    frames[i] = Image(String.Format("frame_%04d.png", i));
}

current_frame = 0;
logo = SpriteNew();
logo.SetX(Window.GetWidth() / 2 - frames[0].GetWidth() / 2);
logo.SetY(Window.GetHeight() / 2 - frames[0].GetHeight() / 2);

fun refresh_callback() {
    logo.SetImage(frames[current_frame]);
    current_frame = (current_frame + 1) % 24;
}

Plymouth.SetRefreshFunction(refresh_callback);
"""
    with open(f"{theme_dir}/ghost-eyes.script", "w") as f:
        f.write(script)

    # Activar tema
    os.system(f"plymouth-set-default-theme ghost-eyes")
    os.system("update-initramfs -u -k all")
    print(f"\n[ghost-plymouth] Tema instalado y activado.")
    print(f"[ghost-plymouth] Reinicia para ver el resultado.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ghost-plymouth-gen — Genera tema Plymouth Ghost Eyes")
    parser.add_argument("--install",  action="store_true", help="Instalar en el sistema (requiere root)")
    parser.add_argument("--output",   default="./ghost-eyes-frames", help="Directorio de salida")
    parser.add_argument("--frames",   type=int, default=24, help="Número de frames (default: 24)")
    parser.add_argument("--width",    type=int, default=1920)
    parser.add_argument("--height",   type=int, default=1080)
    args = parser.parse_args()

    if args.install:
        install_theme()
    else:
        # Usar directorio local por defecto — no necesita root
        out_dir = args.output
        os.makedirs(out_dir, exist_ok=True)
        generate_frames(n_frames=args.frames, output_dir=out_dir)
        print(f"\nFrames guardados en: {out_dir}/")
        print("Usa --install para instalar en el sistema (requiere root)")
