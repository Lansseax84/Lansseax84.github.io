#!/usr/bin/env python3
# ghost-recon — GHOST EYES PROJECT
# Reconocimiento profundo de red: puertos, servicios, OS fingerprint
# Uso: ghost-recon <ip/dominio> [--ports 1-1024] [--json] [--fast]

import sys, os, re, json, time, socket, argparse, subprocess, threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class C:
    O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
    G="\033[38;5;64m";  R="\033[38;5;160m";  Y="\033[38;5;136m"
    W="\033[38;5;255m"; GY="\033[38;5;238m"; RESET="\033[0m"; BOLD="\033[1m"

# ── Base de datos de servicios ────────────────────────────────
SERVICES = {
    21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",
    80:"HTTP",110:"POP3",143:"IMAP",443:"HTTPS",445:"SMB",
    993:"IMAPS",995:"POP3S",1433:"MSSQL",3306:"MySQL",
    3389:"RDP",5432:"PostgreSQL",5900:"VNC",6379:"Redis",
    8080:"HTTP-Alt",8443:"HTTPS-Alt",27017:"MongoDB",
    6667:"IRC",11211:"Memcached",9200:"Elasticsearch",
}

RISK = {
    23:"ALTO — Telnet sin cifrado",
    21:"MEDIO — FTP sin cifrado",
    3389:"ALTO — RDP expuesto",
    5900:"ALTO — VNC expuesto",
    445:"ALTO — SMB (WannaCry)",
    6667:"ALTO — IRC sospechoso",
    11211:"MEDIO — Memcached sin auth",
    9200:"MEDIO — Elasticsearch sin auth",
    27017:"MEDIO — MongoDB sin auth",
}

def grab_banner(ip, port, timeout=2):
    """Intenta obtener el banner del servicio."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        # HTTP
        if port in (80, 8080, 8000):
            s.sendall(b"HEAD / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
        elif port == 21:
            pass  # FTP envía banner solo
        elif port == 22:
            pass  # SSH envía banner solo
        else:
            s.sendall(b"\r\n")
        banner = s.recv(256).decode("utf-8", errors="ignore").strip()
        s.close()
        # Limpiar banner
        banner = re.sub(r'[\x00-\x1f\x7f-\xff]+', ' ', banner)
        return banner[:80] if banner else ""
    except Exception:
        return ""

def scan_port(ip, port, timeout=1):
    """Escanea un puerto. Devuelve (port, open, banner)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        s.close()
        if result == 0:
            banner = grab_banner(ip, port)
            return port, True, banner
        return port, False, ""
    except Exception:
        return port, False, ""

def parse_port_range(port_str):
    """Parsea '1-1024' o '80,443,8080' o 'common'."""
    if port_str == "common":
        return list(SERVICES.keys())
    if port_str == "all":
        return list(range(1, 65536))
    if "," in port_str:
        return [int(p.strip()) for p in port_str.split(",") if p.strip().isdigit()]
    if "-" in port_str:
        parts = port_str.split("-")
        if len(parts) == 2:
            try:
                return list(range(int(parts[0]), int(parts[1])+1))
            except ValueError:
                pass
    try:
        return [int(port_str)]
    except ValueError:
        return list(SERVICES.keys())

def resolve_target(target):
    """Resuelve hostname a IP."""
    try:
        ip = socket.gethostbyname(target)
        return ip
    except socket.gaierror:
        return None

def os_fingerprint(ip):
    """Intenta detectar el OS via TTL."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", ip],
            capture_output=True, text=True, timeout=5
        )
        ttl_m = re.search(r"ttl=(\d+)", result.stdout, re.IGNORECASE)
        if ttl_m:
            ttl = int(ttl_m.group(1))
            if ttl <= 64:   return f"Linux/Unix (TTL={ttl})"
            if ttl <= 128:  return f"Windows (TTL={ttl})"
            if ttl <= 255:  return f"Cisco/Network (TTL={ttl})"
    except Exception:
        pass

    # Intentar nmap OS detection si disponible
    try:
        r = subprocess.run(
            ["nmap", "-O", "--osscan-guess", "-T4", ip],
            capture_output=True, text=True, timeout=15
        )
        os_m = re.search(r"OS details: (.+)", r.stdout)
        if os_m: return os_m.group(1)[:50]
    except Exception:
        pass
    return "Desconocido"

def print_banner_cmd():
    print(f"{C.O}")
    print(r"  ██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗")
    print(r"  ██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║")
    print(r"  ██████╔╝█████╗  ██║     ██║   ██║██╔██╗ ██║")
    print(r"  ██╔══██╗██╔══╝  ██║     ██║   ██║██║╚██╗██║")
    print(r"  ██║  ██║███████╗╚██████╗╚██████╔╝██║ ╚████║")
    print(r"  ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝")
    print(f"{C.RESET}")
    print(f"  {C.OD}GHOST EYES · Reconocimiento profundo de red{C.RESET}\n")

def render_map(target, ip, open_ports):
    """Dibuja mapa ASCII del objetivo."""
    print(f"\n  {C.O}╔{'═'*58}╗{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.OG}{C.BOLD}MAPA DE SERVICIOS — {target}{C.RESET}"
          +" "*(36-len(target))+f"  {C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*58}╣{C.RESET}")

    print(f"  {C.O}║{C.RESET}  {C.OG}◆ {ip}{C.RESET}" + " "*44 + f"  {C.O}║{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.OD}│{C.RESET}" + " "*56 + f"  {C.O}║{C.RESET}")

    for port, banner in open_ports[:12]:
        svc  = SERVICES.get(port, "?")
        risk = RISK.get(port, "")
        risk_col = C.R if "ALTO" in risk else (C.Y if "MEDIO" in risk else C.G)
        risk_str = risk_col + risk[:20] + C.RESET if risk else ""
        banner_str = f" · {banner[:20]}" if banner else ""
        print(f"  {C.O}║{C.RESET}  {C.OD}├──{C.RESET} {C.OG}:{port:<6}{C.RESET}"
              f"{C.W}{svc:<12}{C.RESET}{risk_str}{C.GY}{banner_str}{C.RESET}")

    if len(open_ports) > 12:
        print(f"  {C.O}║{C.RESET}  {C.GY}    ... y {len(open_ports)-12} puertos más{C.RESET}"
              +" "*28+f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╚{'═'*58}╝{C.RESET}")

def main():
    p = argparse.ArgumentParser(description="ghost-recon — Reconocimiento de red")
    p.add_argument("target",   help="IP o dominio objetivo")
    p.add_argument("--ports",  default="common",
                   help="Rango: 'common', '1-1024', '80,443', 'all'")
    p.add_argument("--json",   action="store_true")
    p.add_argument("--fast",   action="store_true", help="Timeout 0.5s")
    p.add_argument("--banner", action="store_true", help="Capturar banners")
    p.add_argument("--silent", action="store_true")
    args = p.parse_args()

    if not args.silent:
        print_banner_cmd()

    target = args.target
    timeout = 0.5 if args.fast else 1.0

    # Resolver
    print(f"  {C.O}[+]{C.RESET} Objetivo  : {C.OG}{target}{C.RESET}")
    ip = resolve_target(target)
    if not ip:
        print(f"  {C.R}[!] No se pudo resolver: {target}{C.RESET}"); sys.exit(1)
    if ip != target:
        print(f"  {C.O}[+]{C.RESET} IP        : {C.OG}{ip}{C.RESET}")

    # OS fingerprint
    print(f"  {C.O}[+]{C.RESET} Detectando OS...")
    os_info = os_fingerprint(ip)
    print(f"  {C.O}[+]{C.RESET} OS estimado: {C.OG}{os_info}{C.RESET}")

    # Puertos a escanear
    ports = parse_port_range(args.ports)
    print(f"  {C.O}[+]{C.RESET} Puertos   : {len(ports)} a escanear")
    print(f"  {C.OD}Escaneando...{C.RESET}\n")

    open_ports = []
    total     = len(ports)
    scanned   = 0
    lock      = threading.Lock()

    workers = 150 if args.fast else 80

    def on_done(port, is_open, banner):
        nonlocal scanned
        with lock:
            scanned += 1
            pct = int(scanned/total*100)
            filled = int(pct/5)
            bar = C.O+"█"*filled+C.GY+"░"*(20-filled)+C.RESET
            print(f"\r  {bar} {C.OD}{pct:3d}%{C.RESET}  {C.GY}{scanned}/{total}{C.RESET}",
                  end="", flush=True)
            if is_open:
                open_ports.append((port, banner))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(scan_port, ip, port, timeout): port for port in ports}
        for future in as_completed(futures):
            port, is_open, banner = future.result()
            on_done(port, is_open, banner)

    print()

    # Ordenar resultados
    open_ports.sort(key=lambda x: x[0])

    print(f"\n  {C.O}[+]{C.RESET} {C.G}{len(open_ports)} puertos abiertos{C.RESET} "
          f"de {total} escaneados\n")

    if not open_ports:
        print(f"  {C.GY}· Sin puertos abiertos detectados.{C.RESET}")
    else:
        render_map(target, ip, open_ports)

        # Tabla detallada
        print(f"\n  {C.OD}{'PUERTO':<10}{'SERVICIO':<14}{'BANNER':<36}{'RIESGO'}{C.RESET}")
        print(f"  {C.O}{'─'*70}{C.RESET}")
        for port, banner in open_ports:
            svc  = SERVICES.get(port, "Desconocido")
            risk = RISK.get(port, "")
            risk_col = C.R if "ALTO" in risk else (C.Y if "MEDIO" in risk else C.G)
            print(f"  {C.OG}{port:<10}{C.RESET}"
                  f"{C.W}{svc:<14}{C.RESET}"
                  f"{C.GY}{banner[:35]:<36}{C.RESET}"
                  f"{risk_col}{risk}{C.RESET}")

    # Resumen de riesgos
    risks = [(p, RISK[p]) for p, _ in open_ports if p in RISK]
    if risks:
        print(f"\n  {C.R}⚠  PUERTOS DE RIESGO DETECTADOS:{C.RESET}")
        for port, risk in risks:
            print(f"  {C.R}   :{port} — {risk}{C.RESET}")

    # JSON export
    if args.json:
        data = {
            "target": target, "ip": ip, "os": os_info,
            "timestamp": datetime.now().isoformat(),
            "open_ports": [
                {"port": p, "service": SERVICES.get(p,"?"),
                 "banner": b, "risk": RISK.get(p,"")}
                for p, b in open_ports
            ]
        }
        fname = f"ghost-recon-{target.replace('.','_')}.json"
        with open(fname, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n  {C.O}→ Exportado: {fname}{C.RESET}")

    print()

if __name__ == "__main__":
    main()
