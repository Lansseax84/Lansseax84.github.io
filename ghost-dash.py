#!/usr/bin/env python3
# ghost-dash — GHOST EYES PROJECT
# Panel personal: clima, notas, recordatorios, reloj ASCII
# Uso: ghost-dash [--note "texto"] [--remind "texto" --in 10] [--weather ciudad]

import sys, os, json, time, argparse, subprocess, re
from datetime import datetime, timedelta
import urllib.request, urllib.error

class C:
    O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
    G="\033[38;5;64m";  R="\033[38;5;160m";  Y="\033[38;5;136m"
    W="\033[38;5;255m"; GY="\033[38;5;238m"; RESET="\033[0m"; BOLD="\033[1m"

DATA_DIR  = os.path.expanduser("~/.ghost-dash")
NOTES_F   = os.path.join(DATA_DIR, "notes.json")
REMIND_F  = os.path.join(DATA_DIR, "reminders.json")

def ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in [NOTES_F, REMIND_F]:
        if not os.path.exists(f):
            with open(f, "w") as fh:
                json.dump([], fh)

def load(path):
    try:
        with open(path) as f: return json.load(f)
    except: return []

def save(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2, ensure_ascii=False)

# ── RELOJ ASCII ───────────────────────────────────────────────
DIGITS = {
    '0': ["┌─┐","│ │","└─┘"],
    '1': ["  │","  │","  │"],
    '2': ["┌─┐","┌─┘","└─┘"],
    '3': ["┌─┐","└─┤","└─┘"],
    '4': ["│ │","└─┤","  │"],
    '5': ["┌─┐","└─┐","└─┘"],
    '6': ["┌─┐","├─┐","└─┘"],
    '7': ["┌─┐","  │","  │"],
    '8': ["┌─┐","├─┤","└─┘"],
    '9': ["┌─┐","└─┤","└─┘"],
    ':': [" "," ●"," "],
}

def render_clock(t_str):
    """Renderiza hora en ASCII art."""
    rows = ["", "", ""]
    for ch in t_str:
        d = DIGITS.get(ch, [" ", " ", " "])
        for i in range(3):
            rows[i] += d[i] + " "
    return rows

def show_clock():
    now  = datetime.now()
    hour = now.strftime("%H:%M")
    date = now.strftime("%A, %d de %B de %Y")
    rows = render_clock(hour)
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}RELOJ{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")
    for row in rows:
        print(f"  {C.OG}  {row}{C.RESET}")
    print(f"  {C.OD}  {date}{C.RESET}")

# ── CLIMA ─────────────────────────────────────────────────────
def get_weather(city=""):
    """Obtiene clima de wttr.in en formato ASCII."""
    try:
        city_enc = city.replace(" ", "+") if city else ""
        url = f"https://wttr.in/{city_enc}?format=4&lang=es"
        req = urllib.request.Request(url,
              headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return None

def show_weather(city=""):
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}CLIMA{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")

    data = get_weather(city)
    if data:
        for line in data.split("\n")[:6]:
            print(f"  {C.W}{line}{C.RESET}")
    else:
        # Intentar formato más simple
        try:
            url2 = f"https://wttr.in/{city.replace(' ','+')}?format=%C+%t+%h&lang=es"
            req  = urllib.request.Request(url2, headers={"User-Agent":"curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                simple = r.read().decode().strip()
            print(f"  {C.W}{simple}{C.RESET}")
        except Exception:
            print(f"  {C.GY}· Sin conexión — clima no disponible{C.RESET}")

# ── NOTAS ─────────────────────────────────────────────────────
def add_note(text):
    notes = load(NOTES_F)
    note  = {"id": len(notes)+1, "text": text,
              "created": datetime.now().isoformat()}
    notes.append(note)
    save(NOTES_F, notes)
    print(f"  {C.G}✓ Nota #{note['id']} guardada:{C.RESET} {text}")

def del_note(nid):
    notes = load(NOTES_F)
    before = len(notes)
    notes  = [n for n in notes if n.get("id") != int(nid)]
    save(NOTES_F, notes)
    if len(notes) < before:
        print(f"  {C.G}✓ Nota #{nid} eliminada.{C.RESET}")
    else:
        print(f"  {C.R}Nota #{nid} no encontrada.{C.RESET}")

def show_notes():
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}NOTAS{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")
    notes = load(NOTES_F)
    if not notes:
        print(f"  {C.GY}· Sin notas. Añade con: ghost-dash --note \"texto\"{C.RESET}")
        return
    for n in notes[-8:]:  # Últimas 8
        ts = n.get("created","")[:10]
        print(f"  {C.OD}#{n['id']}{C.RESET}  {C.W}{n['text'][:48]}{C.RESET}  "
              f"{C.GY}{ts}{C.RESET}")
    if len(notes) > 8:
        print(f"  {C.GY}  ... y {len(notes)-8} notas más{C.RESET}")

# ── RECORDATORIOS ─────────────────────────────────────────────
def add_reminder(text, minutes):
    reminders = load(REMIND_F)
    trigger   = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    rid       = len(reminders) + 1
    reminders.append({"id": rid, "text": text, "trigger": trigger, "done": False})
    save(REMIND_F, reminders)
    print(f"  {C.G}✓ Recordatorio #{rid} en {minutes} min:{C.RESET} {text}")

def check_reminders():
    """Muestra recordatorios pendientes y activa los que vencen."""
    reminders = load(REMIND_F)
    now = datetime.now()
    changed = False
    due = []

    for r in reminders:
        if r.get("done"): continue
        try:
            trigger = datetime.fromisoformat(r["trigger"])
        except Exception:
            continue
        if now >= trigger:
            due.append(r)
            r["done"] = True
            changed = True

    if changed:
        save(REMIND_F, reminders)

    return due, [r for r in reminders if not r.get("done")]

def show_reminders():
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}RECORDATORIOS{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")

    due, pending = check_reminders()

    # Mostrar vencidos
    for r in due:
        print(f"  {C.R}🔔 ¡AHORA! {C.RESET}{C.W}{r['text'][:50]}{C.RESET}")

    # Mostrar pendientes
    if not pending and not due:
        print(f"  {C.GY}· Sin recordatorios. Añade con: ghost-dash --remind \"texto\" --in 30{C.RESET}")
    else:
        now = datetime.now()
        for r in pending[:6]:
            try:
                trigger = datetime.fromisoformat(r["trigger"])
                diff    = trigger - now
                mins    = int(diff.total_seconds() / 60)
                time_str = f"en {mins}m" if mins < 60 else f"en {mins//60}h {mins%60}m"
            except Exception:
                time_str = "?"
            print(f"  {C.Y}⏰{C.RESET}  {C.W}{r['text'][:42]}{C.RESET}  "
                  f"{C.OD}{time_str}{C.RESET}")

# ── TIP DEL DÍA ───────────────────────────────────────────────
TIPS = [
    "ghost-map detecta intrusos en tiempo real en tu red local",
    "Usa ghost-clean --deep para liberar GB de espacio en disco",
    "ghost-log --watch muestra errores del sistema en tiempo real",
    "ghost-trace te muestra exactamente por dónde viajan tus datos",
    "ghost-shield analiza tu sistema en busca de vulnerabilidades",
    "ghost-send cifra tus mensajes con AES-256 automáticamente",
    "Alias rápidos: gm=ghost-map, gl=ghost-log, gs=ghost-status",
    "ghost-watch --full muestra CPU, GPU, RAM y red en tiempo real",
]

def show_tip():
    import hashlib
    day_idx = int(hashlib.md5(datetime.now().strftime("%Y%m%d").encode()).hexdigest(), 16)
    tip = TIPS[day_idx % len(TIPS)]
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}TIP DEL DÍA{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OD}💡{C.RESET}  {C.W}{tip}{C.RESET}")

# ── RESUMEN RÁPIDO SISTEMA ────────────────────────────────────
def show_quick_sys():
    print(f"\n  {C.O}{'─'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}SISTEMA RÁPIDO{C.RESET}")
    print(f"  {C.O}{'─'*54}{C.RESET}")

    def rn(cmd):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
            return r.stdout.strip()
        except: return "?"

    cpu  = rn("top -bn1 | grep 'Cpu(s)' | awk '{printf \"%.0f\", $2}'")
    ram  = rn("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    disk = rn("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")'")
    ip   = rn("ip route get 8.8.8.8 2>/dev/null | grep src | awk '{print $7}'")

    def bar(pct_str, w=16):
        try:
            v = int(re.search(r'\d+', pct_str or "0").group())
        except: v = 0
        f = int(v / 100 * w)
        col = C.R if v > 85 else (C.Y if v > 65 else C.G)
        return col + "█"*f + C.GY + "░"*(w-f) + C.RESET

    cpu_pct = f"{cpu}%" if cpu else "?"
    print(f"  {C.OD}CPU  {C.RESET} {bar(cpu)}  {C.OG}{cpu_pct}{C.RESET}")
    print(f"  {C.OD}RAM  {C.RESET} {C.W}{ram}{C.RESET}")
    print(f"  {C.OD}DISCO{C.RESET} {C.W}{disk}{C.RESET}")
    print(f"  {C.OD}IP   {C.RESET} {C.OG}{ip or 'sin red'}{C.RESET}")

def print_banner():
    print(f"{C.O}")
    print(r"  ██████╗  █████╗ ███████╗██╗  ██╗")
    print(r"  ██╔══██╗██╔══██╗██╔════╝██║  ██║")
    print(r"  ██║  ██║███████║███████╗███████║")
    print(r"  ██║  ██║██╔══██║╚════██║██╔══██║")
    print(r"  ██████╔╝██║  ██║███████║██║  ██║")
    print(r"  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")
    print(f"{C.RESET}")
    print(f"  {C.OD}GHOST EYES · Panel personal visual{C.RESET}\n")

def main():
    ensure_dir()
    p = argparse.ArgumentParser(description="ghost-dash — Panel personal")
    p.add_argument("--note",    type=str, default=None, help="Añadir nota")
    p.add_argument("--del-note",type=int, default=None, help="Eliminar nota por ID")
    p.add_argument("--remind",  type=str, default=None, help="Añadir recordatorio")
    p.add_argument("--in",      type=int, default=30,   dest="minutes",
                   help="Minutos para el recordatorio (default: 30)")
    p.add_argument("--weather", type=str, default="",   help="Ciudad para el clima")
    p.add_argument("--notes",   action="store_true",    help="Solo mostrar notas")
    p.add_argument("--silent",  action="store_true")
    args = p.parse_args()

    # Acciones directas
    if args.note:
        add_note(args.note); return
    if args.del_note:
        del_note(args.del_note); return
    if args.remind:
        add_reminder(args.remind, args.minutes); return
    if args.notes:
        show_notes(); return

    # Dashboard completo
    if not args.silent:
        print_banner()

    show_clock()
    show_weather(args.weather)
    show_quick_sys()
    show_notes()
    show_reminders()
    show_tip()
    print()

if __name__ == "__main__":
    main()
