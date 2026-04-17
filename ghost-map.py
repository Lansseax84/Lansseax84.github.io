#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════╗
# ║  ghost-map — GHOST EYES PROJECT                         ║
# ║  Mapeo visual interactivo de red local                  ║
# ║  Uso: ghost-map [--in-f] [--json] [--silent]            ║
# ╚══════════════════════════════════════════════════════════╝

import sys
import os
import json
import time
import argparse
import ipaddress
import subprocess
import threading
import curses
import socket
import struct
import fcntl

# ── Dependencias opcionales (instala con install.sh) ────────
try:
    from scapy.all import ARP, Ether, srp, conf
    SCAPY_OK = True
except ImportError:
    SCAPY_OK = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    from rich.panel import Panel
    from rich.text import Text
    RICH_OK = True
except ImportError:
    RICH_OK = False

# ── Colores ANSI (fallback si rich no está) ─────────────────
class C:
    ORANGE      = "\033[38;5;166m"
    ORANGE_DIM  = "\033[38;5;130m"
    ORANGE_GLOW = "\033[38;5;208m"
    YELLOW_DIM  = "\033[38;5;136m"
    GREEN_DIM   = "\033[38;5;22m"
    WHITE       = "\033[38;5;250m"
    GREY        = "\033[38;5;238m"
    RESET       = "\033[0m"
    BOLD        = "\033[1m"
    BLINK       = "\033[5m"
    CLEAR       = "\033[2J\033[H"

# ── Historial de visitas por sesión ─────────────────────────
VISIT_HISTORY = {}   # { ip: count }
SESSION_FILE  = "/tmp/.ghost-map-session"

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_session(history):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(history, f)
    except Exception:
        pass

# ── Detectar IP y subred local ───────────────────────────────
def get_local_network():
    """Devuelve (ip_local, subred_cidr) ej: ('192.168.1.50', '192.168.1.0/24')"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        # Asumir /24 como subred por defecto
        parts = ip.split(".")
        subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        return ip, subnet
    except Exception:
        return "127.0.0.1", "127.0.0.0/24"

# ── Escaneo ARP con Scapy ────────────────────────────────────
def scan_network_scapy(subnet, silent=False):
    """Escanea la subred con ARP. Devuelve lista de dicts."""
    if not SCAPY_OK:
        return scan_network_nmap(subnet, silent)

    conf.verb = 0
    devices = []

    if not silent and RICH_OK:
        console = Console()
        with Progress(
            SpinnerColumn(style="color(166)"),
            TextColumn("[color(166)]Escaneando {task.description}"),
            BarColumn(bar_width=30, style="color(130)", complete_style="color(208)"),
            TextColumn("[color(130)]{task.percentage:.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(subnet, total=100)
            def _scan():
                nonlocal devices
                pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
                answered, _ = srp(pkt, timeout=3, retry=1, verbose=0)
                for _, rcv in answered:
                    devices.append({
                        "ip":       rcv.psrc,
                        "mac":      rcv.hwsrc,
                        "hostname": resolve_hostname(rcv.psrc),
                        "vendor":   get_vendor(rcv.hwsrc),
                        "ports":    [],
                        "visits":   0,
                    })
            t = threading.Thread(target=_scan)
            t.start()
            while t.is_alive():
                progress.update(task, advance=2)
                time.sleep(0.1)
            t.join()
            progress.update(task, completed=100)
    else:
        pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
        answered, _ = srp(pkt, timeout=3, retry=1, verbose=0)
        for _, rcv in answered:
            devices.append({
                "ip":       rcv.psrc,
                "mac":      rcv.hwsrc,
                "hostname": resolve_hostname(rcv.psrc),
                "vendor":   get_vendor(rcv.hwsrc),
                "ports":    [],
                "visits":   0,
            })

    return sorted(devices, key=lambda d: tuple(int(x) for x in d["ip"].split(".")))

# ── Fallback: nmap si scapy no está ─────────────────────────
def scan_network_nmap(subnet, silent=False):
    devices = []
    if not silent:
        print(f"{C.ORANGE}[ghost-map]{C.RESET} Usando nmap como fallback...")
    try:
        result = subprocess.run(
            ["nmap", "-sn", "-T4", subnet],
            capture_output=True, text=True, timeout=60
        )
        lines = result.stdout.split("\n")
        current_ip = None
        for line in lines:
            if "Nmap scan report" in line:
                current_ip = line.split()[-1].strip("()")
            if "MAC Address" in line and current_ip:
                parts = line.split()
                mac = parts[2] if len(parts) > 2 else "??:??:??:??:??:??"
                vendor = " ".join(parts[3:]).strip("()") if len(parts) > 3 else "Desconocido"
                devices.append({
                    "ip":       current_ip,
                    "mac":      mac,
                    "hostname": resolve_hostname(current_ip),
                    "vendor":   vendor,
                    "ports":    [],
                    "visits":   0,
                })
                current_ip = None
    except Exception as e:
        print(f"{C.ORANGE_DIM}[!] Error en nmap: {e}{C.RESET}")
    return devices

# ── Resolución de hostname ───────────────────────────────────
def resolve_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ip

# ── Vendor MAC (primeros 3 octetos) ─────────────────────────
VENDOR_DB = {
    "00:50:56": "VMware",       "00:0c:29": "VMware",
    "b8:27:eb": "Raspberry Pi", "dc:a6:32": "Raspberry Pi",
    "00:1a:11": "Google",       "f0:9f:c2": "Ubiquiti",
    "18:fd:74": "Apple",        "ac:bc:32": "Apple",
    "00:16:3e": "Xen",          "52:54:00": "QEMU/KVM",
    "08:00:27": "VirtualBox",
}

def get_vendor(mac):
    prefix = mac[:8].lower().replace("-", ":")
    for k, v in VENDOR_DB.items():
        if prefix.startswith(k.lower()):
            return v
    return "Desconocido"

# ── Escaneo rápido de puertos comunes ───────────────────────
COMMON_PORTS = [22, 80, 443, 8080, 8443, 3389, 21, 25, 53]

def scan_ports(ip, timeout=0.5):
    open_ports = []
    for port in COMMON_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
            s.close()
        except Exception:
            pass
    return open_ports

# ── Render del mapa ASCII ────────────────────────────────────
def render_map(devices, local_ip, selected_idx, visit_history):
    lines = []
    lines.append(f"{C.ORANGE}╔{'═'*58}╗{C.RESET}")
    lines.append(f"{C.ORANGE}║{C.RESET}  {C.BOLD}{C.ORANGE_GLOW}GHOST-MAP · RED LOCAL{C.RESET}"
                 + " " * 37 + f"{C.ORANGE}║{C.RESET}")
    lines.append(f"{C.ORANGE}╚{'═'*58}╝{C.RESET}")
    lines.append("")

    # Router (primer dispositivo o .1)
    router_ip = devices[0]["ip"] if devices else "192.168.1.1"
    lines.append(f"  {C.ORANGE_GLOW}◆ {router_ip}{C.RESET}  {C.GREY}[GATEWAY / ROUTER]{C.RESET}")
    lines.append(f"  {C.ORANGE_DIM}│{C.RESET}")

    for i, dev in enumerate(devices):
        is_selected = (i == selected_idx)
        is_local    = (dev["ip"] == local_ip)
        visits      = visit_history.get(dev["ip"], 0)

        # Conector
        is_last = (i == len(devices) - 1)
        connector = "└──" if is_last else "├──"

        # Indicador de posición
        if is_local:
            marker = f"{C.YELLOW_DIM}{C.BLINK}●{C.RESET}"
            label  = f"{C.YELLOW_DIM}← TÚ{C.RESET}"
        else:
            marker = f"{C.ORANGE_DIM}○{C.RESET}"
            label  = ""

        # Indicador de visitas
        visit_mark = ""
        if visits >= 2:
            visit_mark = f" {C.GREEN_DIM}[✓✓ visitado]{C.RESET}"
        elif visits == 1:
            visit_mark = f" {C.GREEN_DIM}[✓ visitado]{C.RESET}"

        # Fila seleccionada
        if is_selected:
            row_color = C.ORANGE_GLOW
            cursor    = f"{C.ORANGE_GLOW}▶{C.RESET} "
        else:
            row_color = C.ORANGE_DIM
            cursor    = "  "

        hostname_short = dev["hostname"][:20] if dev["hostname"] else dev["ip"]
        vendor_short   = dev["vendor"][:12]

        line = (
            f"  {C.ORANGE_DIM}{connector}{C.RESET} "
            f"{cursor}{marker} "
            f"{row_color}{dev['ip']:<16}{C.RESET}"
            f"{C.GREY}{vendor_short:<14}{C.RESET}"
            f"{C.ORANGE_DIM}{hostname_short:<22}{C.RESET}"
            f"{label}{visit_mark}"
        )
        lines.append(line)

        if not is_last:
            lines.append(f"  {C.ORANGE_DIM}│{C.RESET}")

    lines.append("")
    lines.append(
        f"  {C.GREY}[↑↓] Navegar  "
        f"[ENTER] Ver detalles  "
        f"[R] Re-escanear  "
        f"[Q] Salir{C.RESET}"
    )
    lines.append(
        f"  {C.ORANGE_DIM}Dispositivos: {len(devices)}  "
        f"│  Tu IP: {local_ip}  "
        f"│  Flag --in-f para forzar info{C.RESET}"
    )
    return lines

# ── Panel de detalles del dispositivo ───────────────────────
def show_device_panel(dev, visit_history, force=False):
    ip      = dev["ip"]
    visits  = visit_history.get(ip, 0)

    if visits >= 2 and not force:
        print(f"\n{C.ORANGE_DIM}[ghost-map]{C.RESET} Ya visitaste {C.ORANGE}{ip}{C.RESET} "
              f"{C.GREY}({visits}x). Usa --in-f para forzar.{C.RESET}\n")
        return

    # Escanear puertos si no están ya
    if not dev.get("ports"):
        print(f"{C.ORANGE_DIM}  → Escaneando puertos...{C.RESET}", end="\r")
        dev["ports"] = scan_ports(ip)

    ports_str = ", ".join(str(p) for p in dev["ports"]) if dev["ports"] else "Ninguno detectado"

    print(f"\n{C.ORANGE}╔{'═'*46}╗{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.BOLD}{C.ORANGE_GLOW}DISPOSITIVO · DETALLES{C.RESET}"
          + " " * 24 + f"{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}╠{'═'*46}╣{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}IP        {C.RESET}{C.ORANGE}{ip:<36}{C.RESET}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}MAC       {C.RESET}{dev['mac']:<36}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}VENDOR    {C.RESET}{dev['vendor']:<36}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}HOSTNAME  {C.RESET}{dev['hostname'][:36]:<36}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}PUERTOS   {C.RESET}{ports_str[:36]:<36}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}║{C.RESET}  {C.ORANGE_DIM}VISITAS   {C.RESET}{str(visits+1):<36}{C.ORANGE}║{C.RESET}")
    print(f"{C.ORANGE}╚{'═'*46}╝{C.RESET}\n")

    # Actualizar historial
    visit_history[ip] = visits + 1
    save_session(visit_history)

# ── Bucle interactivo principal ──────────────────────────────
def interactive_map(devices, local_ip, visit_history, force_info=False):
    selected = 0
    # Posición inicial: el propio dispositivo
    for i, d in enumerate(devices):
        if d["ip"] == local_ip:
            selected = i
            break

    while True:
        # Limpiar pantalla y redibujar
        os.system("clear")
        lines = render_map(devices, local_ip, selected, visit_history)
        for line in lines:
            print(line)

        # Capturar tecla (sin curses para simplicidad y compatibilidad)
        try:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            ch = input("\n> ").strip().lower()
            if ch == "q":
                break
            if ch == "r":
                return "rescan"
            continue

        # Tecla especial (escape sequence)
        if ch == "\x1b":
            try:
                import tty, termios
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                tty.setraw(fd)
                seq = sys.stdin.read(2)
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                if seq == "[A":   # flecha arriba
                    selected = max(0, selected - 1)
                elif seq == "[B": # flecha abajo
                    selected = min(len(devices) - 1, selected + 1)
            except Exception:
                pass

        elif ch in ("q", "Q"):
            break

        elif ch in ("r", "R"):
            return "rescan"

        elif ch in ("\r", "\n", " "):
            # Mostrar detalles del dispositivo seleccionado
            os.system("clear")
            show_device_panel(devices[selected], visit_history, force=force_info)
            input(f"  {C.GREY}[ENTER para volver al mapa]{C.RESET}")

    return "exit"

# ── Exportar JSON ────────────────────────────────────────────
def export_json(devices, local_ip):
    data = {
        "local_ip":  local_ip,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "devices":   devices,
    }
    filename = f"ghost-map-{time.strftime('%Y%m%d-%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"{C.ORANGE}[ghost-map]{C.RESET} Exportado → {C.ORANGE_GLOW}{filename}{C.RESET}")
    return filename

# ── Banner de inicio ─────────────────────────────────────────
def print_banner():
    print(f"{C.ORANGE}")
    print(r"   _____ _    _  ____   _____ _______   __  __          _____  ")
    print(r"  / ____| |  | |/ __ \ / ____|__   __| |  \/  |   /\  |  __ \ ")
    print(r" | |  __| |__| | |  | | (___    | |    | \  / |  /  \ | |__) |")
    print(r" | | |_ |  __  | |  | |\___ \   | |    | |\/| | / /\ \|  ___/ ")
    print(r" | |__| | |  | | |__| |____) |  | |    | |  | |/ ____ \ |     ")
    print(r"  \_____|_|  |_|\____/|_____/   |_|    |_|  |_/_/    \_\_|     ")
    print(f"{C.RESET}")
    print(f"  {C.ORANGE_DIM}GHOST EYES PROJECT · Mapeo visual de red local{C.RESET}")
    print(f"  {C.GREY}Uso: ghost-map [--in-f] [--json] [--silent]{C.RESET}\n")

# ── Entry point ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="ghost-map — Mapa visual interactivo de red",
        add_help=True
    )
    parser.add_argument("--in-f",   action="store_true",
                        help="Forzar ventana de info aunque ya hayas visitado 2+ veces")
    parser.add_argument("--json",   action="store_true",
                        help="Exportar resultados a JSON")
    parser.add_argument("--silent", action="store_true",
                        help="No mostrar barra de progreso durante el escaneo")
    args = parser.parse_args()

    # Verificar root para ARP scan
    if os.geteuid() != 0:
        print(f"{C.ORANGE_DIM}[!] ghost-map necesita privilegios root para ARP scan.{C.RESET}")
        print(f"    Ejecuta: {C.ORANGE}sudo ghost-map{C.RESET}\n")
        sys.exit(1)

    print_banner()

    # Cargar sesión
    visit_history = load_session()

    # Detectar red local
    local_ip, subnet = get_local_network()
    print(f"  {C.ORANGE}[+]{C.RESET} IP local detectada : {C.ORANGE_GLOW}{local_ip}{C.RESET}")
    print(f"  {C.ORANGE}[+]{C.RESET} Subred objetivo    : {C.ORANGE_GLOW}{subnet}{C.RESET}\n")

    action = "rescan"
    devices = []

    while action == "rescan":
        # Escanear
        print(f"  {C.ORANGE_DIM}Iniciando escaneo ARP...{C.RESET}\n")
        devices = scan_network_scapy(subnet, silent=args.silent)

        if not devices:
            print(f"\n{C.ORANGE_DIM}[!] No se encontraron dispositivos. "
                  f"Verifica que estás en una red local.{C.RESET}\n")
            sys.exit(1)

        print(f"\n  {C.ORANGE}[+]{C.RESET} {len(devices)} dispositivos encontrados.\n")
        time.sleep(0.8)

        # Exportar si se pidió
        if args.json:
            export_json(devices, local_ip)
            sys.exit(0)

        # Mapa interactivo
        action = interactive_map(
            devices, local_ip, visit_history,
            force_info=args.in_f
        )

    print(f"\n  {C.ORANGE_DIM}[ghost-map] Sesión cerrada. Datos guardados en {SESSION_FILE}{C.RESET}\n")

if __name__ == "__main__":
    main()
