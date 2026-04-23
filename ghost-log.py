#!/usr/bin/env python3
# ghost-log — GHOST EYES PROJECT
# Lee logs del sistema y los traduce a lenguaje humano con colores

import sys, os, re, subprocess, argparse, time
from datetime import datetime

class C:
    ORANGE      = "\033[38;5;166m"
    ORANGE_DIM  = "\033[38;5;130m"
    ORANGE_GLOW = "\033[38;5;208m"
    RED         = "\033[38;5;160m"
    RED_BRIGHT  = "\033[38;5;196m"
    YELLOW      = "\033[38;5;136m"
    GREEN       = "\033[38;5;64m"
    GREY        = "\033[38;5;238m"
    WHITE       = "\033[38;5;255m"
    RESET       = "\033[0m"
    BOLD        = "\033[1m"
    BLINK       = "\033[5m"

# ── Diccionario de traducciones ──────────────────────────────
TRANSLATIONS = [
    # Kernel / Hardware
    (r"kernel: \[.*?\] (.*)",                    lambda m: ("KERNEL", m.group(1))),
    (r"Out of memory.*Kill process (\d+) \((\w+)\)", lambda m: ("MEMORIA", f"Sin memoria RAM — proceso '{m.group(2)}' (PID {m.group(1)}) fue forzado a cerrar")),
    (r"EXT4-fs error",                           lambda _: ("DISCO",   "Error en el sistema de archivos — puede haber sectores dañados en el disco")),
    (r"ata\d+.*failed command",                  lambda _: ("DISCO",   "Fallo de comando en disco duro — posible problema físico o cable suelto")),
    (r"ACPI.*error",                             lambda _: ("HARDWARE","Error ACPI — problema con la comunicación con la placa base")),
    (r"nouveau.*failed",                         lambda _: ("GPU",     "Driver nouveau (GPU NVIDIA genérico) falló — instala nvidia-open-dkms")),
    (r"nvidia.*error|NVRM.*error",               lambda _: ("GPU",     "Error en driver NVIDIA — ejecuta: sudo ghost-nvidia")),
    (r"amdgpu.*error|radeon.*error",             lambda _: ("GPU",     "Error en driver AMD GPU — puede necesitar actualización del kernel")),
    (r"i915.*error",                             lambda _: ("GPU",     "Error en driver Intel GPU — actualiza el kernel o ajusta parámetros i915")),
    (r"usb.*disconnect",                         lambda _: ("USB",     "Dispositivo USB desconectado de forma inesperada")),
    (r"usb.*cannot reset",                       lambda _: ("USB",     "USB no responde — desconéctalo y vuélvelo a conectar")),
    # Red
    (r"wlan\d+.*disconnected|wlp.*disconnected", lambda _: ("RED",     "WiFi desconectada de forma inesperada")),
    (r"eth\d+.*link is down|enp.*link is down",  lambda _: ("RED",     "Cable de red desconectado o switch apagado")),
    (r"DHCP.*failed|dhclient.*failed",           lambda _: ("RED",     "No se pudo obtener IP automática del router — comprueba la red")),
    (r"connection refused",                      lambda _: ("RED",     "Conexión rechazada — el servicio de destino no está activo")),
    (r"UFW BLOCK",                               lambda _: ("FIREWALL","Paquete de red bloqueado por el firewall (UFW)")),
    # Servicios
    (r"(\w+\.service).*failed",                  lambda m: ("SERVICIO",f"Servicio '{m.group(1)}' falló al iniciar — usa: systemctl status {m.group(1)}")),
    (r"(\w+\.service).*started",                 lambda m: ("SERVICIO",f"Servicio '{m.group(1)}' iniciado correctamente")),
    (r"(\w+\.service).*stopped",                 lambda m: ("SERVICIO",f"Servicio '{m.group(1)}' detenido")),
    # Seguridad
    (r"authentication failure",                  lambda _: ("SEGURIDAD","Fallo de autenticación — alguien intentó acceder con contraseña incorrecta")),
    (r"Invalid user (\S+) from (\S+)",           lambda m: ("SEGURIDAD",f"Intento de acceso SSH con usuario '{m.group(1)}' desde IP {m.group(2)}")),
    (r"Failed password for (\S+) from (\S+)",    lambda m: ("SEGURIDAD",f"Contraseña incorrecta para '{m.group(1)}' desde {m.group(2)}")),
    (r"sudo.*COMMAND",                           lambda _: ("SUDO",    "Comando ejecutado con privilegios de administrador")),
    # Sistema
    (r"segfault",                                lambda _: ("CRASH",   "Programa se cerró por fallo de memoria (segfault) — posible bug o RAM dañada")),
    (r"call trace|kernel panic",                 lambda _: ("CRÍTICO", "Fallo crítico del kernel — si se repite, puede haber hardware dañado")),
    (r"temperature.*critical|thermal.*shutdown", lambda _: ("TEMPERATURA","¡CPU o GPU sobrecalentada! El sistema puede apagarse para protegerse")),
    (r"Battery.*low|battery.*critical",          lambda _: ("BATERÍA", "Batería casi agotada")),
    (r"filesystem.*full|no space left",          lambda _: ("DISCO",   "Disco duro lleno — libera espacio con: ghost-clean")),
    (r"Bluetooth.*error",                        lambda _: ("BLUETOOTH","Error en Bluetooth — reinicia el servicio: sudo systemctl restart bluetooth")),
]

SEVERITY_COLORS = {
    "CRÍTICO":    (C.RED_BRIGHT, "⚠⚠"),
    "SEGURIDAD":  (C.RED,        "⚠ "),
    "CRASH":      (C.RED,        "✗ "),
    "DISCO":      (C.YELLOW,     "⊘ "),
    "TEMPERATURA":(C.YELLOW,     "🌡"),
    "GPU":        (C.ORANGE_GLOW,"◈ "),
    "MEMORIA":    (C.ORANGE,     "▣ "),
    "RED":        (C.ORANGE_DIM, "⌁ "),
    "FIREWALL":   (C.ORANGE_DIM, "⊛ "),
    "SERVICIO":   (C.GREY,       "● "),
    "USB":        (C.GREY,       "⌀ "),
    "HARDWARE":   (C.ORANGE,     "◆ "),
    "KERNEL":     (C.GREY,       "· "),
    "SUDO":       (C.GREEN,      "✓ "),
    "BLUETOOTH":  (C.GREY,       "⌾ "),
    "BATERÍA":    (C.YELLOW,     "⊟ "),
}

def translate_line(raw):
    """Devuelve (categoria, mensaje_humano) o None si no hay match."""
    for pattern, handler in TRANSLATIONS:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            try:
                return handler(m)
            except:
                return None
    return None

def parse_timestamp(line):
    """Extrae timestamp de línea de log."""
    # journalctl format: "Apr 16 10:22:11"
    m = re.match(r'^(\w{3}\s+\d+\s+\d+:\d+:\d+)', line)
    if m: return m.group(1)
    # systemd format: "2025-04-16T10:22:11"
    m = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
    if m: return m.group(1)[:16].replace("T"," ")
    return ""

def render_entry(ts, cat, msg, count=None):
    col, icon = SEVERITY_COLORS.get(cat, (C.GREY, "· "))
    cat_str = f"{col}{cat:<12}{C.RESET}"
    ts_str  = f"{C.GREY}{ts:<17}{C.RESET}" if ts else ""
    cnt_str = f" {C.GREY}(×{count}){C.RESET}" if count and count > 1 else ""
    return f"  {col}{icon}{C.RESET} {cat_str} {ts_str} {msg}{cnt_str}"

def read_journalctl(lines=200, unit=None, priority=None, since=None):
    """Lee logs del sistema vía journalctl. Fallback a /var/log/syslog."""
    cmd = ["journalctl", "--no-pager", f"-n{lines}", "--output=short"]
    if unit:     cmd += ["-u", unit]
    if priority: cmd += [f"-p{priority}"]
    if since:    cmd += [f"--since={since}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split("\n")
        # journalctl devolvió error — intentar fallback
    except FileNotFoundError:
        print(f"  {C.OD}[!] journalctl no disponible — leyendo /var/log/syslog{C.RESET}")
    except subprocess.TimeoutExpired:
        print(f"  {C.Y}[!] journalctl tardó demasiado — intentando syslog{C.RESET}")
    except Exception as e:
        print(f"  {C.Y}[!] journalctl error: {e}{C.RESET}")

    # Fallbacks: syslog, kern.log, auth.log
    for logfile in ["/var/log/syslog", "/var/log/kern.log", "/var/log/auth.log"]:
        if os.path.exists(logfile):
            try:
                with open(logfile, "r", errors="replace") as f:
                    content = f.readlines()
                    return content[-lines:]
            except PermissionError:
                print(f"  {C.Y}[!] Sin permiso para leer {logfile} — prueba con sudo{C.RESET}")
            except Exception:
                continue

    print(f"  {C.R}[!] No se encontraron logs accesibles.{C.RESET}")
    return []

def read_file(path):
    try:
        if not os.path.exists(path):
            print(f"  {C.R}[!] Archivo no encontrado: {path}{C.RESET}")
            return []
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
            return lines[-500:]
    except PermissionError:
        print(f"  {C.R}[!] Sin permiso para leer: {path}{C.RESET}")
        return []
    except Exception as e:
        print(f"  {C.R}[!] Error leyendo {path}: {e}{C.RESET}")
        return []

def process_logs(raw_lines, limit=50):
    """Procesa líneas crudas y devuelve entradas traducidas."""
    results = []
    seen    = {}  # deduplicar mensajes repetidos

    for line in raw_lines:
        if not line.strip(): continue
        result = translate_line(line)
        if not result: continue
        cat, msg = result
        ts = parse_timestamp(line)
        key = f"{cat}:{msg[:40]}"
        if key in seen:
            seen[key]["count"] += 1
        else:
            entry = {"ts": ts, "cat": cat, "msg": msg, "count": 1}
            seen[key] = entry
            results.append(entry)
        if len(results) >= limit: break

    return results

def print_banner():
    print(f"{C.ORANGE}")
    print(r"   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗    ██╗      ██████╗  ██████╗")
    print(r"  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝    ██║     ██╔═══██╗██╔════╝")
    print(r"  ██║  ███╗███████║██║   ██║███████╗   ██║       ██║     ██║   ██║██║  ███╗")
    print(r"  ██║   ██║██╔══██║██║   ██║╚════██║   ██║       ██║     ██║   ██║██║   ██║")
    print(r"  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║       ███████╗╚██████╔╝╚██████╔╝")
    print(r"   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝       ╚══════╝ ╚═════╝  ╚═════╝")
    print(f"{C.RESET}")
    print(f"  {C.ORANGE_DIM}GHOST EYES · Logs del sistema en lenguaje humano{C.RESET}\n")

def print_summary(results):
    cats = {}
    for e in results:
        cats[e["cat"]] = cats.get(e["cat"], 0) + e.get("count", 1)

    criticals = sum(v for k,v in cats.items() if k in ("CRÍTICO","CRASH","SEGURIDAD"))
    warnings  = sum(v for k,v in cats.items() if k in ("DISCO","TEMPERATURA","MEMORIA","GPU"))

    print(f"\n  {C.ORANGE}╔{'═'*50}╗{C.RESET}")
    print(f"  {C.ORANGE}║{C.RESET}  {C.BOLD}RESUMEN{C.RESET}" + " "*43 + f"{C.ORANGE}║{C.RESET}")
    print(f"  {C.ORANGE}╠{'═'*50}╣{C.RESET}")
    print(f"  {C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}Entradas procesadas : {C.RESET}{len(results):<28}{C.ORANGE}║{C.RESET}")
    if criticals:
        print(f"  {C.ORANGE}║{C.RESET}  {C.RED}Críticos/Seguridad  : {criticals:<28}{C.RESET}{C.ORANGE}║{C.RESET}")
    if warnings:
        print(f"  {C.ORANGE}║{C.RESET}  {C.YELLOW}Advertencias        : {warnings:<28}{C.RESET}{C.ORANGE}║{C.RESET}")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1])[:5]:
        col = SEVERITY_COLORS.get(cat, (C.GREY,""))[0]
        print(f"  {C.ORANGE}║{C.RESET}  {col}{cat:<20}{C.RESET} {count:<29}{C.ORANGE}║{C.RESET}")
    print(f"  {C.ORANGE}╚{'═'*50}╝{C.RESET}\n")

def watch_mode():
    """Modo live: muestra nuevas entradas en tiempo real."""
    print(f"  {C.ORANGE_DIM}Modo watch activo — Ctrl+C para salir{C.RESET}\n")
    cmd = ["journalctl", "-f", "--output=short", "--no-pager"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in proc.stdout:
            result = translate_line(line)
            if result:
                cat, msg = result
                ts = parse_timestamp(line)
                print(render_entry(ts, cat, msg))
    except KeyboardInterrupt:
        print(f"\n  {C.ORANGE_DIM}Watch detenido.{C.RESET}\n")

def main():
    p = argparse.ArgumentParser(description="ghost-log — Logs en lenguaje humano")
    p.add_argument("--lines",   type=int, default=500,  help="Líneas a leer (default: 500)")
    p.add_argument("--limit",   type=int, default=40,   help="Resultados a mostrar (default: 40)")
    p.add_argument("--watch",   action="store_true",    help="Modo live en tiempo real")
    p.add_argument("--unit",    type=str, default=None, help="Filtrar por servicio systemd")
    p.add_argument("--errors",  action="store_true",    help="Solo errores críticos")
    p.add_argument("--since",   type=str, default=None, help="Desde cuándo: '1 hour ago', 'today'")
    p.add_argument("--file",    type=str, default=None, help="Leer archivo de log directamente")
    p.add_argument("--json",    action="store_true",    help="Exportar en JSON")
    args = p.parse_args()

    print_banner()

    if args.watch:
        watch_mode()
        return

    # Leer logs
    if args.file:
        print(f"  {C.ORANGE_DIM}Leyendo: {args.file}{C.RESET}\n")
        raw = read_file(args.file)
    else:
        priority = "3" if args.errors else None
        print(f"  {C.ORANGE_DIM}Leyendo {args.lines} líneas del journal...{C.RESET}\n")
        raw = read_journalctl(args.lines, args.unit, priority, args.since)

    results = process_logs(raw, args.limit)

    if not results:
        print(f"  {C.GREEN}✓ Sin eventos relevantes detectados.{C.RESET}\n")
        return

    # Cabecera tabla
    print(f"  {C.ORANGE}{'─'*72}{C.RESET}")
    print(f"  {C.ORANGE_DIM}  TIPO         HORA              DESCRIPCIÓN{C.RESET}")
    print(f"  {C.ORANGE}{'─'*72}{C.RESET}\n")

    for entry in results:
        print(render_entry(entry["ts"], entry["cat"], entry["msg"], entry.get("count")))

    print_summary(results)

    if args.json:
        import json
        fname = f"ghost-log-{time.strftime('%Y%m%d-%H%M%S')}.json"
        with open(fname,"w") as f: json.dump(results, f, indent=2)
        print(f"  {C.ORANGE}→ Exportado: {fname}{C.RESET}\n")

if __name__ == "__main__":
    main()
