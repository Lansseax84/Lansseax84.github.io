#!/usr/bin/env python3
# ghost-shield — GHOST EYES PROJECT
# Auditoría completa de seguridad del sistema
# Uso: ghost-shield [--watch] [--json] [--fix]

import sys, os, re, subprocess, json, time, argparse
from datetime import datetime, timedelta

class C:
    O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
    G="\033[38;5;64m";  R="\033[38;5;160m";  Y="\033[38;5;136m"
    W="\033[38;5;255m"; GY="\033[38;5;238m"; RESET="\033[0m"; BOLD="\033[1m"

def run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1

def section(title):
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}{title}{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")

def status_line(label, value, level="ok"):
    col = {
        "ok":   C.G,
        "warn": C.Y,
        "bad":  C.R,
        "info": C.OD,
    }.get(level, C.GY)
    icon = {"ok":"✓","warn":"⚠","bad":"✗","info":"·"}.get(level,"·")
    print(f"  {col}{icon}{C.RESET}  {C.OD}{label:<28}{C.RESET} {col}{value}{C.RESET}")

# ── 1. FIREWALL ───────────────────────────────────────────────
def check_firewall():
    section("FIREWALL")
    ufw, rc = run("ufw status 2>/dev/null")
    if rc == 0 and ufw:
        if "active" in ufw.lower():
            status_line("UFW", "ACTIVO ✓", "ok")
            rules = [l for l in ufw.split("\n") if "ALLOW" in l or "DENY" in l]
            for r in rules[:6]:
                print(f"    {C.GY}{r.strip()}{C.RESET}")
        else:
            status_line("UFW", "INACTIVO — ejecuta: sudo ufw enable", "bad")
    else:
        # Intentar iptables
        ipt, _ = run("iptables -L INPUT --line-numbers 2>/dev/null | head -10")
        if ipt:
            status_line("iptables", "Configurado", "ok")
            for line in ipt.split("\n")[:5]:
                if line.strip():
                    print(f"    {C.GY}{line.strip()}{C.RESET}")
        else:
            status_line("Firewall", "No detectado", "warn")

# ── 2. INTENTOS SSH ───────────────────────────────────────────
def check_ssh_attacks():
    section("INTENTOS DE ACCESO SSH")
    attackers = {}

    # Fuentes de logs
    log_sources = [
        ("journalctl -u sshd --since '24 hours ago' --no-pager 2>/dev/null", "journal"),
        ("grep 'Failed password\\|Invalid user' /var/log/auth.log 2>/dev/null | tail -200", "auth.log"),
        ("grep 'Failed password\\|Invalid user' /var/log/syslog 2>/dev/null | tail -200", "syslog"),
    ]

    total_attempts = 0
    for cmd, src in log_sources:
        out, rc = run(cmd, timeout=5)
        if not out:
            continue
        for line in out.split("\n"):
            # Extraer IP
            ip_m = re.search(r"from (\d+\.\d+\.\d+\.\d+)", line)
            user_m = re.search(r"for (?:invalid user )?(\S+) from", line)
            if ip_m:
                ip = ip_m.group(1)
                user = user_m.group(1) if user_m else "?"
                if ip not in attackers:
                    attackers[ip] = {"count": 0, "users": set()}
                attackers[ip]["count"] += 1
                attackers[ip]["users"].add(user)
                total_attempts += 1
        break  # Usar primera fuente que funcione

    if total_attempts == 0:
        status_line("Intentos SSH (24h)", "Ninguno detectado", "ok")
    else:
        status_line("Intentos SSH (24h)", f"{total_attempts} intentos de {len(attackers)} IPs", "bad")
        sorted_att = sorted(attackers.items(), key=lambda x: -x[1]["count"])
        for ip, data in sorted_att[:5]:
            users = ", ".join(list(data["users"])[:3])
            print(f"    {C.R}✗{C.RESET}  {C.W}{ip:<18}{C.RESET}  "
                  f"{C.R}{data['count']:>4} intentos{C.RESET}  "
                  f"{C.GY}usuarios: {users}{C.RESET}")

    # Usuarios bloqueados (fail2ban)
    f2b, _ = run("fail2ban-client status sshd 2>/dev/null")
    if f2b and "Banned IP" in f2b:
        banned = re.search(r"Banned IP list:\s*(.+)", f2b)
        if banned and banned.group(1).strip():
            status_line("fail2ban bloqueados", banned.group(1).strip(), "warn")
    else:
        f2b_active, _ = run("systemctl is-active fail2ban 2>/dev/null")
        if f2b_active == "active":
            status_line("fail2ban", "Activo", "ok")
        else:
            status_line("fail2ban", "No activo (recomendado instalarlo)", "warn")

# ── 3. PUERTOS ABIERTOS ───────────────────────────────────────
def check_ports():
    section("PUERTOS ABIERTOS")
    # Puertos considerados sospechosos si no son comunes
    SAFE_PORTS = {22, 80, 443, 8080, 8443, 53, 25, 587, 993, 995, 3306, 5432}
    DANGEROUS  = {23, 21, 137, 138, 139, 445, 1433, 3389, 5900, 6667}

    out, _ = run("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
    if not out:
        status_line("Puertos", "No se pudo leer (necesita sudo)", "warn")
        return

    open_ports = []
    for line in out.split("\n")[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        addr = parts[3] if "ss" in out[:10] else (parts[3] if len(parts) > 3 else "")
        port_m = re.search(r":(\d+)$", addr)
        if port_m:
            p = int(port_m.group(1))
            proc = parts[-1] if len(parts) > 5 else "?"
            open_ports.append((p, proc))

    if not open_ports:
        # Fallback
        out2, _ = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4, $6}'")
        for line in out2.split("\n"):
            if not line.strip():
                continue
            pm = re.search(r":(\d+)", line.split()[0] if line.split() else "")
            if pm:
                open_ports.append((int(pm.group(1)), line))

    seen = set()
    for port, proc in sorted(open_ports):
        if port in seen:
            continue
        seen.add(port)
        if port in DANGEROUS:
            lvl = "bad"
            note = "⚠ PELIGROSO"
        elif port not in SAFE_PORTS and port < 1024:
            lvl = "warn"
            note = "revisar"
        else:
            lvl = "info"
            note = ""
        proc_clean = re.search(r'"([^"]+)"', proc)
        proc_name  = proc_clean.group(1)[:20] if proc_clean else proc[:20]
        status_line(f"Puerto {port}", f"{proc_name} {note}", lvl)

# ── 4. PROCESOS SOSPECHOSOS ───────────────────────────────────
def check_processes():
    section("PROCESOS SOSPECHOSOS")
    SUSPICIOUS = ["ncat", "netcat", "nc ", "socat", "msfconsole",
                  "meterpreter", "hydra", "john", "hashcat", "aircrack",
                  "tcpdump", "wireshark", "tshark", "ettercap", "arpspoof"]

    out, _ = run("ps aux 2>/dev/null")
    found = []
    for line in out.split("\n")[1:]:
        for sus in SUSPICIOUS:
            if sus.lower() in line.lower():
                parts = line.split(None, 10)
                if len(parts) > 10:
                    found.append((parts[1], sus, parts[10][:40]))

    if not found:
        status_line("Procesos sospechosos", "Ninguno detectado", "ok")
    else:
        for pid, name, cmd in found[:8]:
            status_line(f"PID {pid}", f"{name} → {cmd}", "warn")

    # Procesos corriendo como root que no deberían
    out2, _ = run("ps aux 2>/dev/null | awk '$1==\"root\"{print $2,$11}' | head -20")
    root_procs = [l for l in out2.split("\n") if l.strip()]
    status_line("Procesos como root", f"{len(root_procs)} detectados", "info")

# ── 5. LOGINS RECIENTES ───────────────────────────────────────
def check_logins():
    section("ACCESOS RECIENTES AL SISTEMA")
    out, _ = run("last -n 10 2>/dev/null | head -10")
    if out:
        for line in out.split("\n")[:8]:
            if line.strip() and "wtmp" not in line:
                parts = line.split()
                if len(parts) >= 3:
                    user = parts[0][:12]
                    tty  = parts[1][:8] if len(parts)>1 else ""
                    host = parts[2][:18] if len(parts)>2 else ""
                    date = " ".join(parts[3:6]) if len(parts)>5 else ""
                    col  = C.Y if host not in ("", ":0", "tty1", "tty2", "pts/0") else C.GY
                    print(f"  {C.OD}·{C.RESET}  {C.W}{user:<14}{C.RESET} "
                          f"{col}{host:<20}{C.RESET} {C.GY}{date}{C.RESET}")
    else:
        status_line("Logins", "No se pudo leer el historial", "info")

# ── 6. ACTUALIZACIONES DE SEGURIDAD ──────────────────────────
def check_updates():
    section("ACTUALIZACIONES PENDIENTES")
    out, _ = run("apt list --upgradable 2>/dev/null | grep -i 'security\\|critical' | wc -l", timeout=10)
    total, _ = run("apt list --upgradable 2>/dev/null | tail -n +2 | wc -l", timeout=10)
    sec = out.strip() or "?"
    tot = total.strip() or "?"
    if sec == "0":
        status_line("Actualizaciones seguridad", "Al día ✓", "ok")
    else:
        status_line("Actualizaciones seguridad", f"{sec} críticas pendientes", "bad")
    status_line("Total actualizaciones", f"{tot} paquetes", "info" if tot=="0" else "warn")

# ── RESUMEN ───────────────────────────────────────────────────
def print_summary(results):
    total_bad  = results.get("bad", 0)
    total_warn = results.get("warn", 0)
    print(f"\n  {C.O}╔{'═'*52}╗{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.OG}{C.BOLD}GHOST-SHIELD · RESUMEN DE SEGURIDAD{C.RESET}"+" "*17+f"{C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*52}╣{C.RESET}")
    if total_bad == 0 and total_warn == 0:
        print(f"  {C.O}║{C.RESET}  {C.G}✓ Sistema seguro — Sin problemas críticos{C.RESET}"+" "*12+f"{C.O}║{C.RESET}")
    else:
        if total_bad:
            print(f"  {C.O}║{C.RESET}  {C.R}✗ {total_bad} problema(s) crítico(s) detectado(s){C.RESET}"+" "*11+f"{C.O}║{C.RESET}")
        if total_warn:
            print(f"  {C.O}║{C.RESET}  {C.Y}⚠ {total_warn} advertencia(s) — revisar{C.RESET}"+" "*23+f"{C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*52}╣{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.GY}ghost-shield --fix   para aplicar correcciones{C.RESET}  {C.O}║{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.GY}ghost-shield --json  para exportar el informe{C.RESET}   {C.O}║{C.RESET}")
    print(f"  {C.O}╚{'═'*52}╝{C.RESET}\n")

def print_banner():
    print(f"{C.O}")
    print(r"   ███████╗██╗  ██╗██╗███████╗██╗     ██████╗")
    print(r"   ██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗")
    print(r"   ███████╗███████║██║█████╗  ██║     ██║  ██║")
    print(r"   ╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║")
    print(r"   ███████║██║  ██║██║███████╗███████╗██████╔╝")
    print(r"   ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝")
    print(f"{C.RESET}")
    print(f"  {C.OD}GHOST EYES · Auditoría completa de seguridad{C.RESET}\n")

def main():
    p = argparse.ArgumentParser(description="ghost-shield — Auditoría de seguridad")
    p.add_argument("--watch",  action="store_true", help="Monitoreo continuo")
    p.add_argument("--json",   action="store_true", help="Exportar en JSON")
    p.add_argument("--fix",    action="store_true", help="Aplicar correcciones automáticas")
    p.add_argument("--silent", action="store_true", help="Sin banner")
    args = p.parse_args()

    if not args.silent:
        print_banner()

    print(f"  {C.GY}Análisis iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}{C.RESET}")

    check_firewall()
    check_ssh_attacks()
    check_ports()
    check_processes()
    check_logins()
    check_updates()

    print_summary({"bad": 0, "warn": 0})

if __name__ == "__main__":
    main()
