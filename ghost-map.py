#!/usr/bin/env python3
# ghost-map v2 — GHOST EYES PROJECT
# Mapeo visual + detección de intrusos en rojo + monitor en segundo plano

import sys, os, json, time, argparse, threading, socket, subprocess

try:
    from scapy.all import ARP, Ether, srp, conf
    SCAPY_OK = True
except ImportError:
    SCAPY_OK = False

class C:
    ORANGE      = "\033[38;5;166m"
    ORANGE_DIM  = "\033[38;5;130m"
    ORANGE_GLOW = "\033[38;5;208m"
    YELLOW_DIM  = "\033[38;5;136m"
    GREEN_DIM   = "\033[38;5;64m"
    RED         = "\033[38;5;160m"
    RED_BRIGHT  = "\033[38;5;196m"
    WHITE       = "\033[38;5;255m"
    GREY        = "\033[38;5;238m"
    RESET       = "\033[0m"
    BOLD        = "\033[1m"
    BLINK       = "\033[5m"

SESSION_FILE   = "/tmp/.ghost-map-session"
WHITELIST_FILE = os.path.expanduser("~/.ghost-map-whitelist.json")

def load_session():
    try:
        with open(SESSION_FILE) as f: return json.load(f)
    except: return {}

def save_session(h):
    try:
        with open(SESSION_FILE,"w") as f: json.dump(h,f)
    except: pass

def load_whitelist():
    try:
        with open(WHITELIST_FILE) as f: return set(json.load(f))
    except: return set()

def save_whitelist(wl):
    try:
        with open(WHITELIST_FILE,"w") as f: json.dump(list(wl),f)
    except: pass

def is_known(mac, wl):
    return mac.lower() in {m.lower() for m in wl}

def get_local_network():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]; s.close()
        p = ip.split(".")
        return ip, f"{p[0]}.{p[1]}.{p[2]}.0/24"
    except: return "127.0.0.1","127.0.0.0/24"

def scan_network(subnet, silent=False):
    if not SCAPY_OK: return scan_nmap(subnet)
    conf.verb = 0
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
    answered, _ = srp(pkt, timeout=3, retry=1, verbose=0)
    devs = []
    for _, rcv in answered:
        devs.append({"ip":rcv.psrc,"mac":rcv.hwsrc,
                     "hostname":resolve(rcv.psrc),"vendor":vendor(rcv.hwsrc),
                     "ports":[],"visits":0,"unknown":False})
    return sorted(devs, key=lambda d:[int(x) for x in d["ip"].split(".")])

def scan_nmap(subnet):
    devs=[]; ip=None
    try:
        r=subprocess.run(["nmap","-sn","-T4",subnet],capture_output=True,text=True,timeout=60)
        for ln in r.stdout.split("\n"):
            if "Nmap scan report" in ln: ip=ln.split()[-1].strip("()")
            if "MAC Address" in ln and ip:
                p=ln.split()
                devs.append({"ip":ip,"mac":p[2] if len(p)>2 else "??",
                             "hostname":resolve(ip),"vendor":" ".join(p[3:]).strip("()") if len(p)>3 else "?",
                             "ports":[],"visits":0,"unknown":False})
                ip=None
    except: pass
    return devs

def resolve(ip):
    try: return socket.gethostbyaddr(ip)[0]
    except: return ip

VENDOR_DB={"00:50:56":"VMware","b8:27:eb":"Raspberry Pi","dc:a6:32":"Raspberry Pi",
            "18:fd:74":"Apple","ac:bc:32":"Apple","08:00:27":"VirtualBox"}
def vendor(mac):
    pre=mac[:8].lower().replace("-",":")
    for k,v in VENDOR_DB.items():
        if pre.startswith(k.lower()): return v
    return "Desconocido"

def scan_ports(ip, t=0.5):
    open_p=[]
    for p in [22,80,443,8080,3389,21,25,53]:
        try:
            s=socket.socket(); s.settimeout(t)
            if s.connect_ex((ip,p))==0: open_p.append(p)
            s.close()
        except: pass
    return open_p

PARCA_ASCII = """
     ░░░░░░░░░░░░░░░░░
    ░░  ██████████  ░░
   ░░  ██  ██  ██  ░░
  ░░  ████████████  ░░
  ░░  ██ ○    ○ ██  ░░
  ░░  ██  ----  ██  ░░
  ░░  ████████████  ░░
   ░░  ██      ██  ░░
    ░░  ████████  ░░
     ░░░░░░░░░░░░░░"""

def show_intruder_alert(dev):
    os.system("clear")
    print(f"\n{C.RED}{'!'*58}{C.RESET}")
    print(f"{C.RED}{C.BOLD}")
    for ln in PARCA_ASCII.split("\n"): print(f"  {ln}")
    print(f"{C.RESET}")
    print(f"  {C.WHITE}{C.BOLD}⚠  POSIBLE INTRUSO DETECTADO  ⚠{C.RESET}\n")
    print(f"  {C.RED}Dispositivo DESCONOCIDO en la red:{C.RESET}")
    print(f"\n  {C.ORANGE_DIM}IP       {C.RESET}{C.RED}{C.BOLD}{dev['ip']}{C.RESET}")
    print(f"  {C.ORANGE_DIM}MAC      {C.RESET}{dev['mac']}")
    print(f"  {C.ORANGE_DIM}VENDOR   {C.RESET}{dev['vendor']}")
    print(f"  {C.ORANGE_DIM}HOST     {C.RESET}{dev['hostname']}")
    print(f"\n  {C.ORANGE}[W] Añadir a whitelist (dispositivo de confianza)")
    print(f"  {C.RED}[I] Marcar como intruso y seguir monitoreando{C.RESET}")
    print(f"  {C.GREY}[ENTER] Cerrar alerta{C.RESET}\n")
    print(f"{C.RED}{'!'*58}{C.RESET}\n")

class NetworkMonitor(threading.Thread):
    def __init__(self, subnet, known_devs, wl, cb):
        super().__init__(daemon=True)
        self.subnet   = subnet
        self.known    = {d["mac"].lower() for d in known_devs}
        self.wl       = {m.lower() for m in wl}
        self.cb       = cb
        self.running  = True

    def run(self):
        while self.running:
            time.sleep(30)
            if not self.running: break
            try:
                for dev in scan_network(self.subnet, silent=True):
                    mac=dev["mac"].lower()
                    if mac not in self.known and mac not in self.wl:
                        self.known.add(mac); self.cb(dev)
            except: pass

    def stop(self): self.running=False

def render_map(devices, local_ip, sel, visits, wl, intruders):
    intruder_ips={d["ip"] for d in intruders}
    lines=[]
    lines.append(f"{C.ORANGE}╔{'═'*60}╗{C.RESET}")
    lines.append(f"{C.ORANGE}║{C.RESET}  {C.BOLD}{C.ORANGE_GLOW}GHOST-MAP · RED LOCAL{C.RESET}"+" "*39+f"{C.ORANGE}║{C.RESET}")
    lines.append(f"{C.ORANGE}╚{'═'*60}╝{C.RESET}")
    lines.append(f"  {C.ORANGE_GLOW}◆ GATEWAY{C.RESET}")
    lines.append(f"  {C.ORANGE_DIM}│{C.RESET}")

    for i,dev in enumerate(devices):
        last=i==len(devices)-1
        conn="└──" if last else "├──"
        is_bad=dev["ip"] in intruder_ips
        is_local=dev["ip"]==local_ip
        is_sel=i==sel
        vis=visits.get(dev["ip"],0)

        if is_bad:
            col=C.RED; marker=f"{C.RED}{C.BLINK}●{C.RESET}"; lbl=f" {C.RED}{C.BOLD}← INTRUSO{C.RESET}"
        elif is_local:
            col=C.ORANGE_GLOW; marker=f"{C.YELLOW_DIM}{C.BLINK}●{C.RESET}"; lbl=f" {C.YELLOW_DIM}← TÚ{C.RESET}"
        else:
            col=C.ORANGE_DIM; marker=f"{C.ORANGE_DIM}○{C.RESET}"; lbl=""

        if is_sel: col=C.ORANGE_GLOW
        cursor=f"{C.ORANGE_GLOW}▶{C.RESET} " if is_sel else "  "
        vstag=f" {C.GREEN_DIM}[✓✓]{C.RESET}" if vis>=2 else (f" {C.GREEN_DIM}[✓]{C.RESET}" if vis==1 else "")
        lines.append(f"  {C.ORANGE_DIM}{conn}{C.RESET} {cursor}{marker} {col}{dev['ip']:<16}{C.RESET}{C.GREY}{dev['vendor'][:12]:<14}{C.RESET}{C.ORANGE_DIM}{dev['hostname'][:18]:<20}{C.RESET}{lbl}{vstag}")
        if not last: lines.append(f"  {C.ORANGE_DIM}│{C.RESET}")

    lines.append("")
    ni=len(intruders)
    if ni: lines.append(f"  {C.RED}⚠ {ni} INTRUSO(S) · Dispositivos en rojo{C.RESET}")
    else:  lines.append(f"  {C.GREEN_DIM}◉ Monitor activo · Sin nuevas entradas{C.RESET}")
    lines.append(f"  {C.GREY}[↑↓] Nav  [ENTER] Detalles  [R] Rescan  [Q] Salir{C.RESET}")
    return lines

def show_device(dev, visits, force=False, intruder=False):
    ip=dev["ip"]; vis=visits.get(ip,0)
    if vis>=2 and not force:
        print(f"\n{C.ORANGE_DIM}Ya visitaste {ip} ({vis}x). Usa --in-f{C.RESET}\n"); return
    if not dev.get("ports"):
        print(f"{C.ORANGE_DIM}  → Escaneando puertos...{C.RESET}",end="\r")
        dev["ports"]=scan_ports(ip)
    ps=", ".join(str(p) for p in dev["ports"]) or "Ninguno"
    col=C.RED if intruder else C.ORANGE
    print(f"\n{col}╔{'═'*48}╗{C.RESET}")
    print(f"{col}║{C.RESET}  {C.BOLD}{'⚠ INTRUSO · ' if intruder else ''}DETALLES{C.RESET}"+" "*28+f"{col}║{C.RESET}")
    print(f"{col}╠{'═'*48}╣{C.RESET}")
    for k,v in [("IP",ip),("MAC",dev["mac"]),("VENDOR",dev["vendor"]),("HOSTNAME",dev["hostname"][:38]),("PUERTOS",ps[:38]),("VISITAS",str(vis+1))]:
        print(f"{col}║{C.RESET}  {C.ORANGE_DIM}{k:<10}{C.RESET}{v:<38}{col}║{C.RESET}")
    print(f"{col}╚{'═'*48}╝{C.RESET}\n")
    visits[ip]=vis+1; save_session(visits)

def interactive_map(devices, local_ip, visits, wl, force=False):
    sel=next((i for i,d in enumerate(devices) if d["ip"]==local_ip),0)
    intruders=[]; pending=[]
    def on_intruder(dev): intruders.append(dev); pending.append(dev)
    monitor=NetworkMonitor(get_local_network()[1],devices,wl,on_intruder)
    monitor.start()

    # Detectar si el terminal soporta raw mode (no todas las VMs lo hacen)
    try:
        import tty as _tty, termios as _termios
        _termios.tcgetattr(sys.stdin.fileno())
        TTY_OK = True
    except Exception:
        TTY_OK = False

    def read_key():
        """Lee una tecla. Usa raw mode si disponible, input() como fallback."""
        if not TTY_OK:
            return None, input("\n[q=salir, r=rescan, ENTER=detalles] > ").strip().lower()
        try:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            # Leer secuencia de escape para flechas
            if ch == "\x1b":
                try:
                    tty.setraw(fd)
                    sq = sys.stdin.read(2)
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    return "escape", sq
                except Exception:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
                    return "escape", ""
            return "key", ch
        except Exception:
            return None, input("\n> ").strip().lower()

    while True:
        if pending:
            dev=pending.pop(0); show_intruder_alert(dev)
            k=input("  > ").strip().lower()
            if k=="w": wl.add(dev["mac"].lower()); save_whitelist(wl); intruders.remove(dev)
            continue

        os.system("clear")
        for ln in render_map(devices,local_ip,sel,visits,wl,intruders): print(ln)

        mode, ch = read_key()

        if mode is None:
            # Modo fallback (input)
            if ch=="q": break
            if ch=="r": monitor.stop(); return "rescan"
            if ch in("","k","e"," "): # ENTER o k para detalles
                dev=devices[sel]; is_bad=dev["ip"] in {d["ip"] for d in intruders}
                os.system("clear"); show_device(dev,visits,force=force,intruder=is_bad)
                input(f"  {C.GREY}[ENTER]{C.RESET}")
        elif mode == "escape":
            if ch == "[A": sel=max(0,sel-1)
            elif ch == "[B": sel=min(len(devices)-1,sel+1)
        elif mode == "key":
            if ch in("q","Q"): break
            elif ch in("r","R"): monitor.stop(); return "rescan"
            elif ch in("\r","\n"," "):
                dev=devices[sel]; is_bad=dev["ip"] in {d["ip"] for d in intruders}
                os.system("clear"); show_device(dev,visits,force=force,intruder=is_bad)
                input(f"  {C.GREY}[ENTER]{C.RESET}")

    monitor.stop(); return "exit"

def main():
    p=argparse.ArgumentParser(); p.add_argument("--in-f",action="store_true")
    p.add_argument("--json",action="store_true"); p.add_argument("--silent",action="store_true")
    args=p.parse_args()
    if os.geteuid()!=0: print(f"{C.ORANGE_DIM}[!] sudo ghost-map{C.RESET}"); sys.exit(1)
    print(f"{C.ORANGE}  GHOST-MAP v2 · Detección de intrusos activa{C.RESET}\n")
    visits=load_session(); wl=load_whitelist()
    local_ip,subnet=get_local_network()
    action="rescan"
    while action=="rescan":
        devs=scan_network(subnet,silent=args.silent)
        if not devs: print(f"{C.ORANGE_DIM}[!] Sin dispositivos.{C.RESET}"); sys.exit(1)
        for d in devs: d["unknown"]=not is_known(d["mac"],wl)
        if args.json:
            fn=f"ghost-map-{time.strftime('%Y%m%d-%H%M%S')}.json"
            with open(fn,"w") as f: json.dump({"local_ip":local_ip,"devices":devs},f,indent=2)
            print(f"{C.ORANGE}→ {fn}{C.RESET}"); sys.exit(0)
        action=interactive_map(devs,local_ip,visits,wl,force=args.in_f)
    print(f"\n  {C.ORANGE_DIM}Sesión guardada.{C.RESET}\n")

if __name__=="__main__": main()
