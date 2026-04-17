#!/usr/bin/env python3
# ghost-wallpaper.py — GHOST EYES PROJECT
# Genera y aplica el fondo de escritorio temático
# Uso: python3 ghost-wallpaper.py [--set] [--resolution 1920x1080]

import os, sys, math, argparse, subprocess

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    os.system("pip install Pillow --break-system-packages -q")
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Colores del tema ─────────────────────────────────────────
BG          = (0, 0, 0)
ORANGE      = (200, 90, 0)
ORANGE_DIM  = (120, 53, 0)
ORANGE_GLOW = (255, 122, 26)
ORANGE_DARK = (40, 18, 0)
GRID_LINE   = (18, 8, 0)
ACCENT      = (80, 35, 0)
FACE_COL    = (245, 240, 230)
HAIR_OR     = (212, 136, 15)
GLASSES_OR  = (200, 125, 10)

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

def generate_wallpaper(w=1920, h=1080, output="/tmp/ghost-eyes-wallpaper.png"):
    img  = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    # ── 1. Gradiente radial de fondo (naranja muy oscuro en centro) ──
    cx, cy = w//2, h//2
    max_r = math.sqrt(cx**2 + cy**2)
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            d = math.sqrt((x-cx)**2 + (y-cy)**2)
            t = min(1.0, d / (max_r * 0.7))
            col = lerp_color(ORANGE_DARK, BG, t)
            draw.rectangle([x, y, x+4, y+4], fill=col)

    # ── 2. Grid táctica (líneas sutiles) ────────────────────
    grid_spacing = 60
    for gx in range(0, w, grid_spacing):
        draw.line([(gx, 0), (gx, h)], fill=GRID_LINE, width=1)
    for gy in range(0, h, grid_spacing):
        draw.line([(0, gy), (w, gy)], fill=GRID_LINE, width=1)

    # ── 3. Patrón de fondo (X y gotas como en la imagen) ────
    pat_spacing = 48
    for py in range(0, h, pat_spacing):
        for px in range(0, w, pat_spacing):
            pcx, pcy = px + pat_spacing//2, py + pat_spacing//2
            dist_center = math.sqrt((pcx-cx)**2 + (pcy-cy)**2)
            opacity_factor = min(1.0, dist_center / (max_r * 0.5))
            col_val = int(25 * opacity_factor)
            pcol = (col_val, col_val//3, 0)
            if (px//pat_spacing + py//pat_spacing) % 2 == 0:
                s = 5
                draw.line([(pcx-s,pcy-s),(pcx+s,pcy+s)], fill=pcol, width=1)
                draw.line([(pcx+s,pcy-s),(pcx-s,pcy+s)], fill=pcol, width=1)
            else:
                draw.ellipse([pcx-3, pcy-5, pcx+3, pcy+3], outline=pcol, width=1)

    # ── 4. Chibi Dokkaebi central (grande, semitransparente) ─
    def draw_chibi(draw, dcx, dcy, sc=1.0, alpha=0.18):
        """Dibuja el chibi con opacidad reducida para fondo."""
        def dim(c, factor):
            return tuple(int(v * factor) for v in c)
        f = alpha

        def s(v): return int(v * sc)

        # Cuernos
        for side in [-1, 1]:
            pts = [(dcx+side*s(75),dcy-s(55)),(dcx+side*s(90),dcy-s(100)),(dcx+side*s(58),dcy-s(78))]
            draw.polygon(pts, fill=dim(FACE_COL,f*1.2), outline=dim(ACCENT,f*2))
        # Cara
        draw.ellipse([dcx-s(95),dcy-s(95),dcx+s(95),dcy+s(95)], fill=dim(FACE_COL,f), outline=dim(ACCENT,f*3))
        # Pelo blanco
        hair=[
            (dcx-s(93),dcy-s(25)),(dcx-s(100),dcy-s(55)),(dcx-s(80),dcy-s(90)),
            (dcx-s(45),dcy-s(103)),(dcx,dcy-s(107)),(dcx+s(45),dcy-s(103)),
            (dcx+s(80),dcy-s(90)),(dcx+s(100),dcy-s(55)),(dcx+s(93),dcy-s(25))
        ]
        draw.polygon(hair, fill=dim(FACE_COL,f*1.1), outline=dim(ACCENT,f*2))
        # Rayas naranja pelo
        for ox, sw in [(-48,16),(-18,14),(12,13)]:
            pts=[(dcx+s(ox),dcy-s(107)),(dcx+s(ox+sw),dcy-s(107)),
                 (dcx+s(ox+sw+28),dcy-s(38)),(dcx+s(ox+10),dcy-s(38))]
            draw.polygon(pts, fill=dim(HAIR_OR, f*1.8))
        # Gafas
        for gsx in [-1,1]:
            gox=s(36)*gsx; goy=s(5); gr=s(36)
            draw.ellipse([dcx+gox-gr,dcy+goy-gr,dcx+gox+gr,dcy+goy+gr],
                         fill=dim(GLASSES_OR,f*2.2), outline=dim(GLASSES_OR,f*3), width=s(4))
        # Ojos
        for gsx in [-1,1]:
            ex=dcx+s(36)*gsx; ey=dcy+s(12)
            draw.ellipse([ex-s(13),ey-s(4),ex+s(13),ey+s(16)], fill=dim((20,20,20),f*3))

    # Chibi grande centrado, muy sutil
    draw_chibi(draw, cx, cy - 30, sc=2.8, alpha=0.12)

    # ── 5. Líneas diagonales de "barrido" (esquinas) ────────
    for i in range(0, 300, 40):
        alpha_line = int(15 * (1 - i/300))
        lc = (alpha_line, alpha_line//3, 0)
        draw.line([(0, i), (i, 0)], fill=lc, width=1)
        draw.line([(w, h-i), (w-i, h)], fill=lc, width=1)

    # ── 6. Círculos concéntricos tácticos ───────────────────
    for r in range(80, max_r, 120):
        alpha_c = max(0, int(20 * (1 - r/max_r)))
        draw.ellipse([cx-r,cy-r,cx+r,cy+r], outline=(alpha_c,alpha_c//3,0), width=1)

    # ── 7. Brackets en esquinas ──────────────────────────────
    bracket_size = 60
    bracket_col  = ORANGE_DIM
    bw = 2
    margin = 40
    # TL
    draw.line([(margin,margin),(margin+bracket_size,margin)], fill=bracket_col, width=bw)
    draw.line([(margin,margin),(margin,margin+bracket_size)], fill=bracket_col, width=bw)
    # TR
    draw.line([(w-margin,margin),(w-margin-bracket_size,margin)], fill=bracket_col, width=bw)
    draw.line([(w-margin,margin),(w-margin,margin+bracket_size)], fill=bracket_col, width=bw)
    # BL
    draw.line([(margin,h-margin),(margin+bracket_size,h-margin)], fill=bracket_col, width=bw)
    draw.line([(margin,h-margin),(margin,h-margin-bracket_size)], fill=bracket_col, width=bw)
    # BR
    draw.line([(w-margin,h-margin),(w-margin-bracket_size,h-margin)], fill=bracket_col, width=bw)
    draw.line([(w-margin,h-margin),(w-margin,h-margin-bracket_size)], fill=bracket_col, width=bw)

    # ── 8. Texto GHOST EYES (watermark sutil) ───────────────
    try:
        for fp in ["/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]:
            if os.path.exists(fp):
                font_big  = ImageFont.truetype(fp, 11)
                font_small= ImageFont.truetype(fp, 9)
                break
        else:
            font_big = font_small = ImageFont.load_default()
    except:
        font_big = font_small = ImageFont.load_default()

    draw.text((margin+4, margin+10), "GHOST EYES OS", fill=ACCENT, font=font_big)
    draw.text((margin+4, margin+26), "DOKKAEBI PROTOCOL · ACCESO RESTRINGIDO", fill=(30,13,0), font=font_small)

    # ── 9. Línea inferior naranja sutil ─────────────────────
    draw.line([(0, h-2), (w, h-2)], fill=ORANGE_DIM, width=1)

    # ── 10. Guardar ──────────────────────────────────────────
    img.save(output, "PNG", optimize=True)
    print(f"[ghost-wallpaper] Guardado: {output}")
    return output

def set_wallpaper(path):
    """Aplica el fondo en XFCE, GNOME o KDE."""
    de = os.environ.get("XDG_CURRENT_DESKTOP","").lower()
    tried = False
    if "xfce" in de or not de:
        try:
            r = subprocess.run(
                ["xfconf-query","-c","xfce4-desktop","-p",
                 "/backdrop/screen0/monitorHDMI-1/workspace0/last-image","-s",path],
                capture_output=True)
            # intentar todos los monitores posibles
            for mon in ["HDMI-1","HDMI-2","eDP-1","DP-1","VGA-1"]:
                subprocess.run(["xfconf-query","-c","xfce4-desktop","-p",
                    f"/backdrop/screen0/monitor{mon}/workspace0/last-image","-s",path],
                    capture_output=True)
            tried=True; print("[ghost-wallpaper] Aplicado en XFCE.")
        except: pass
    if "gnome" in de or "ubuntu" in de:
        try:
            subprocess.run(["gsettings","set","org.gnome.desktop.background",
                           "picture-uri",f"file://{path}"])
            subprocess.run(["gsettings","set","org.gnome.desktop.background",
                           "picture-uri-dark",f"file://{path}"])
            tried=True; print("[ghost-wallpaper] Aplicado en GNOME.")
        except: pass
    if "kde" in de or "plasma" in de:
        script=f"""
var allDesktops = desktops();
for(var i=0;i<allDesktops.length;i++){{
    var d=allDesktops[i]; d.wallpaperPlugin="org.kde.image";
    d.currentConfigGroup=["Wallpaper","org.kde.image","General"];
    d.writeConfig("Image","file://{path}");
}}
"""
        try:
            subprocess.run(["qdbus","org.kde.plasmashell","/PlasmaShell",
                           "org.kde.PlasmaShell.evaluateScript",script])
            tried=True; print("[ghost-wallpaper] Aplicado en KDE.")
        except: pass
    if not tried:
        # Fallback: feh o nitrogen
        for cmd in [["feh","--bg-fill",path],["nitrogen","--set-scaled",path]]:
            try: subprocess.run(cmd,check=True); tried=True; break
            except: pass
    if not tried:
        print(f"[ghost-wallpaper] No se pudo aplicar automáticamente.")
        print(f"  Aplica manualmente: feh --bg-fill {path}")

def main():
    p=argparse.ArgumentParser(description="ghost-wallpaper — Fondo de escritorio Ghost Eyes")
    p.add_argument("--set",        action="store_true", help="Aplicar fondo automáticamente")
    p.add_argument("--resolution", default="1920x1080", help="Resolución: 1920x1080, 2560x1440, etc.")
    p.add_argument("--output",     default="/usr/share/ghost-eyes/wallpaper.png")
    args=p.parse_args()

    try:
        w,h=map(int,args.resolution.split("x"))
    except:
        w,h=1920,1080

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    path=generate_wallpaper(w,h,args.output)

    if args.set:
        set_wallpaper(path)
    else:
        print(f"  Usa --set para aplicar automáticamente.")
        print(f"  O aplica manualmente: feh --bg-fill {path}")

if __name__=="__main__":
    main()
