#!/usr/bin/env python3
# ghost-trace — GHOST EYES PROJECT
# Traceroute visual con mapa ASCII, colores por latencia y detección de saltos
# Uso: ghost-trace <destino> [--hops 20] [--json] [--silent]

import sys, os, re, time, socket, subprocess, argparse, json, struct

class C:
    O  = "\033[38;5;166m";  OD = "\033[38;5;130m"; OG = "\033[38;5;208m"
    G  = "\033[38;5;64m";   Y  = "\033[38;5;136m";  R  = "\033[38;5;160m"
    W  = "\033[38;5;255m";  GR = "\033[38;5;238m";  RESET = "\033[0m"
    BOLD = "\033[1m"

def latency_color(ms_str):
    """Color según latencia: verde<10ms, naranja<50ms, rojo>50ms, gris=timeout."""
    if ms_str in ("*", "?", "timeout"):
        return C.GR, "TIMEOUT"
    try:
        ms = float(ms_str)
        if ms < 10:   return C.G,  "EXCELENTE"
        if ms < 30:   return C.OG, "BUENA"
        if ms < 80:   return C.Y,  "LENTA"
        return C.R, "MUY LENTA"
    except ValueError:
        return C.GR, "?"

def latency_bar(ms_str, width=20):
    """Barra visual de latencia."""
    try:
        ms = float(ms_str)
        filled = min(width, int((ms / 200) * width))
        col, _ = latency_color(ms_str)
        bar = col + "█" * filled + C.GR + "░" * (width - filled) + C.RESET
        return bar
    except ValueError:
        return C.GR + "░" * width + C.RESET

def resolve_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""

def get_geo_hint(ip):
    """Clasifica la IP: local, loopback, pública, etc."""
    if ip in ("*", "?"):
        return "FILTRADO"
    parts = ip.split(".")
    if not parts or len(parts) < 4:
        return ""
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return ""
    if first == 10: return "RED LOCAL"
    if first == 172 and 16 <= second <= 31: return "RED LOCAL"
    if first == 192 and second == 168: return "RED LOCAL"
    if first == 127: return "LOOPBACK"
    if first in (1, 8, 9): return "INTERNET"
    return "INTERNET"

def run_traceroute(target, max_hops=20, timeout=2):
    """Ejecuta traceroute y parsea la salida. Fallback a ping por TTL si falla."""
    hops = []

    # Intentar traceroute estándar
    try:
        cmd = ["traceroute", "-n", f"-m{max_hops}", f"-w{timeout}", "-q1", target]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        for line in proc.stdout:
            line = line.strip()
            if not line or line.startswith("traceroute"):
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                hop_n = int(parts[0])
            except ValueError:
                continue

            if len(parts) == 2 and parts[1] == "*":
                hops.append({"n": hop_n, "ip": "*", "ms": "*", "host": ""})
                continue

            # Formato: N  ip  ms ms  (o N  * * *)
            ip_found = ""
            ms_found = "*"
            for p in parts[1:]:
                if re.match(r"\d+\.\d+\.\d+\.\d+", p):
                    ip_found = p
                elif re.match(r"\d+\.?\d*", p) and ip_found:
                    try:
                        ms_found = str(float(p))
                        break
                    except ValueError:
                        pass

            if ip_found:
                host = resolve_hostname(ip_found)
                hops.append({"n": hop_n, "ip": ip_found,
                             "ms": ms_found, "host": host})
            else:
                hops.append({"n": hop_n, "ip": "*", "ms": "*", "host": ""})

        proc.wait(timeout=60)

    except FileNotFoundError:
        # traceroute no disponible — intentar tracepath
        try:
            cmd2 = ["tracepath", "-n", target]
            result = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
            for line in result.stdout.split("\n"):
                m = re.match(r"\s*(\d+).*?(\d+\.\d+\.\d+\.\d+).*?(\d+\.?\d*)\s*ms", line)
                if m:
                    ip = m.group(2)
                    hops.append({"n": int(m.group(1)), "ip": ip,
                                 "ms": m.group(3), "host": resolve_hostname(ip)})
        except Exception:
            pass

    except Exception as e:
        print(f"  {C.R}[!] Error ejecutando traceroute: {e}{C.RESET}")

    return hops

def print_banner():
    print(f"{C.O}")
    print(r"  ████████╗██████╗  █████╗  ██████╗███████╗")
    print(r"     ██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝")
    print(r"     ██║   ██████╔╝███████║██║     █████╗  ")
    print(r"     ██║   ██╔══██╗██╔══██║██║     ██╔══╝  ")
    print(r"     ██║   ██║  ██║██║  ██║╚██████╗███████╗")
    print(r"     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝")
    print(f"{C.RESET}")
    print(f"  {C.OD}GHOST EYES · Traceroute visual con análisis de latencia{C.RESET}\n")

def render_trace(hops, target, target_ip):
    """Dibuja el mapa ASCII del recorrido."""
    print(f"  {C.O}╔{'═'*64}╗{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.BOLD}{C.OG}GHOST-TRACE · RUTA HACIA {target[:30]}{C.RESET}"
          + " "*(38-len(target[:30])) + f"  {C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*64}╣{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.OD}{'HOP':<4} {'IP':<18} {'MS':>7}  {'BARRA':<22} {'TIPO':<12}{C.RESET}  {C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*64}╣{C.RESET}")

    local_ip = get_local_ip()
    prev_ms = None

    for hop in hops:
        n    = hop["n"]
        ip   = hop["ip"]
        ms   = hop["ms"]
        host = hop.get("host", "")
        geo  = get_geo_hint(ip)

        col, quality = latency_color(ms)
        bar = latency_bar(ms)

        # Diferencia con salto anterior
        diff_str = ""
        if ms not in ("*", "?") and prev_ms not in (None, "*", "?"):
            try:
                diff = float(ms) - float(prev_ms)
                if diff > 20:
                    diff_str = f" {C.R}+{diff:.0f}ms{C.RESET}"
                elif diff < -10:
                    diff_str = f" {C.G}{diff:.0f}ms{C.RESET}"
            except ValueError:
                pass
        if ms not in ("*", "?"):
            prev_ms = ms

        # Indicador visual de salto
        if ip == "*":
            hop_icon = f"{C.GR}···{C.RESET}"
            ip_str   = f"{C.GR}{'filtrado':<18}{C.RESET}"
            ms_str   = f"{C.GR}{'*':>7}{C.RESET}"
        elif ip == local_ip:
            hop_icon = f"{C.OG}◉  {C.RESET}"
            ip_str   = f"{C.OG}{ip:<18}{C.RESET}"
            ms_str   = f"{col}{ms:>7}{C.RESET}"
        else:
            hop_icon = f"{C.OD}○  {C.RESET}"
            ip_str   = f"{col}{ip:<18}{C.RESET}"
            ms_str   = f"{col}{ms:>7}{C.RESET}"

        geo_col = C.GR if geo == "INTERNET" else C.OD
        print(f"  {C.O}║{C.RESET}  {C.GR}{n:>2}.{C.RESET} {hop_icon}{ip_str} "
              f"{ms_str}  {bar} {geo_col}{geo:<12}{C.RESET}  {C.O}║{C.RESET}")

        if host and host != ip:
            print(f"  {C.O}║{C.RESET}       {C.GR}└─ {host[:52]}{C.RESET}"
                  + " "*(52-len(host[:52])) + f"  {C.O}║{C.RESET}")

    # Línea conector
    print(f"  {C.O}╠{'═'*64}╣{C.RESET}")

    # Destino final
    reached = any(h["ip"] == target_ip for h in hops) if target_ip else False
    if reached or (hops and hops[-1]["ip"] not in ("*","?")):
        print(f"  {C.O}║{C.RESET}  {C.G}✓ DESTINO ALCANZADO{C.RESET} → "
              f"{C.OG}{target_ip or target}{C.RESET}"
              + " "*22 + f"  {C.O}║{C.RESET}")
    else:
        print(f"  {C.O}║{C.RESET}  {C.R}✗ DESTINO NO ALCANZADO{C.RESET} → "
              f"{C.OD}{target}{C.RESET}"
              + " "*20 + f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╠{'═'*64}╣{C.RESET}")

    # Resumen estadístico
    valid = [h for h in hops if h["ms"] not in ("*","?")]
    timeouts = len(hops) - len(valid)
    if valid:
        ms_vals = []
        for h in valid:
            try: ms_vals.append(float(h["ms"]))
            except ValueError: pass
        if ms_vals:
            avg = sum(ms_vals)/len(ms_vals)
            mx  = max(ms_vals)
            mn  = min(ms_vals)
            print(f"  {C.O}║{C.RESET}  {C.OD}Saltos: {len(hops):<4}{C.RESET}  "
                  f"{C.OD}Min: {mn:.1f}ms{C.RESET}  "
                  f"{C.OD}Avg: {avg:.1f}ms{C.RESET}  "
                  f"{C.OD}Max: {mx:.1f}ms{C.RESET}  "
                  f"{C.R if timeouts else C.G}Timeouts: {timeouts}{C.RESET}"
                  + " "*8 + f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╚{'═'*64}╝{C.RESET}\n")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    p = argparse.ArgumentParser(description="ghost-trace — Traceroute visual")
    p.add_argument("target", help="IP o dominio destino")
    p.add_argument("--hops",   type=int, default=20, help="Máximo de saltos (default: 20)")
    p.add_argument("--json",   action="store_true",  help="Exportar resultado en JSON")
    p.add_argument("--silent", action="store_true",  help="Sin banner")
    p.add_argument("--timeout",type=int, default=2,  help="Timeout por salto en segundos")
    args = p.parse_args()

    if not args.silent:
        print_banner()

    target = args.target

    # Resolver IP del destino
    target_ip = ""
    try:
        target_ip = socket.gethostbyname(target)
        print(f"  {C.O}[+]{C.RESET} Destino  : {C.OG}{target}{C.RESET}"
              + (f" → {C.OD}{target_ip}{C.RESET}" if target_ip != target else ""))
    except socket.gaierror:
        print(f"  {C.R}[!] No se pudo resolver: {target}{C.RESET}\n")
        sys.exit(1)

    print(f"  {C.O}[+]{C.RESET} Tu IP    : {C.OG}{get_local_ip()}{C.RESET}")
    print(f"  {C.O}[+]{C.RESET} Máx saltos: {args.hops}\n")
    print(f"  {C.OD}Trazando ruta...{C.RESET}\n")

    hops = run_traceroute(target, args.hops, args.timeout)

    if not hops:
        print(f"  {C.R}[!] No se obtuvieron saltos.{C.RESET}")
        print(f"  {C.OD}  Verifica que traceroute está instalado: sudo apt install traceroute{C.RESET}\n")
        sys.exit(1)

    render_trace(hops, target, target_ip)

    if args.json:
        data = {"target": target, "target_ip": target_ip,
                "hops": hops, "total": len(hops)}
        fname = f"ghost-trace-{target.replace('.','_')}.json"
        with open(fname, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  {C.O}→ Exportado: {fname}{C.RESET}\n")

if __name__ == "__main__":
    main()
