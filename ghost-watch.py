#!/usr/bin/env python3
# ghost-watch — GHOST EYES PROJECT
# Dashboard live del sistema — se actualiza cada segundo
# Uso: ghost-watch [--interval 1] [--gpu] [--net]

import sys, os, time, argparse, subprocess, socket, re
from datetime import datetime, timedelta

class C:
    O  = "\033[38;5;166m";  OD = "\033[38;5;130m"; OG = "\033[38;5;208m"
    G  = "\033[38;5;64m";   Y  = "\033[38;5;136m";  R  = "\033[38;5;160m"
    W  = "\033[38;5;255m";  GR = "\033[38;5;238m";  RESET = "\033[0m"
    BOLD = "\033[1m";       CLEAR = "\033[2J\033[H"

# ── Lecturas del sistema ──────────────────────────────────────

def read_cpu():
    """Lee uso CPU desde /proc/stat."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        vals = list(map(int, line.split()[1:]))
        idle  = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        return total, idle
    except Exception:
        return 0, 0

_cpu_prev = (0, 0)

def get_cpu_percent():
    global _cpu_prev
    total, idle = read_cpu()
    pt, pi = _cpu_prev
    _cpu_prev = (total, idle)
    if total == pt:
        return 0.0
    try:
        pct = 100.0 * (1.0 - (idle - pi) / (total - pt))
        return max(0.0, min(100.0, pct))
    except ZeroDivisionError:
        return 0.0

def get_ram():
    """Lee RAM desde /proc/meminfo."""
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])  # kB
    except Exception:
        return 0, 0, 0
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    used  = total - avail
    return used, total, avail

def get_disk():
    """Lee uso de disco en /."""
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free  = st.f_bavail * st.f_frsize
        used  = total - free
        return used, total, free
    except Exception:
        return 0, 0, 0

_net_prev = {}

def get_net_speed():
    """Calcula velocidad de red desde /proc/net/dev."""
    global _net_prev
    ifaces = {}
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" not in line:
                    continue
                iface, data = line.split(":", 1)
                iface = iface.strip()
                if iface in ("lo",):
                    continue
                vals = data.split()
                rx = int(vals[0])
                tx = int(vals[8])
                ifaces[iface] = (rx, tx)
    except Exception:
        return {}, {}

    speeds_rx = {}
    speeds_tx = {}
    for iface, (rx, tx) in ifaces.items():
        if iface in _net_prev:
            prx, ptx = _net_prev[iface]
            speeds_rx[iface] = max(0, rx - prx)
            speeds_tx[iface] = max(0, tx - ptx)
        else:
            speeds_rx[iface] = 0
            speeds_tx[iface] = 0
    _net_prev = ifaces
    return speeds_rx, speeds_tx

def get_uptime():
    """Lee uptime desde /proc/uptime."""
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        return str(timedelta(seconds=int(secs)))
    except Exception:
        return "?"

def get_loadavg():
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            return parts[0], parts[1], parts[2]
    except Exception:
        return "?", "?", "?"

def get_cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":")[1].strip()[:40]
    except Exception:
        pass
    return "Desconocido"

def get_top_procs(n=5):
    """Top procesos por uso de CPU."""
    try:
        r = subprocess.run(
            ["ps", "aux", "--sort=-%cpu"],
            capture_output=True, text=True, timeout=3
        )
        lines = r.stdout.strip().split("\n")[1:n+1]
        procs = []
        for line in lines:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                procs.append({
                    "user": parts[0][:8],
                    "pid":  parts[1],
                    "cpu":  parts[2],
                    "mem":  parts[3],
                    "cmd":  parts[10][:28]
                })
        return procs
    except Exception:
        return []

def get_gpu_nvidia():
    """Info GPU NVIDIA via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0 and r.stdout.strip():
            parts = [p.strip() for p in r.stdout.strip().split(",")]
            return {
                "name":   parts[0][:30] if len(parts) > 0 else "?",
                "temp":   parts[1] if len(parts) > 1 else "?",
                "util":   parts[2] if len(parts) > 2 else "?",
                "mem_used": parts[3] if len(parts) > 3 else "?",
                "mem_total": parts[4] if len(parts) > 4 else "?",
            }
    except Exception:
        pass
    return None

def get_temp():
    """Lee temperatura CPU desde thermal zones o coretemp."""
    temps = []
    # /sys/class/thermal
    try:
        thermal = "/sys/class/thermal"
        if os.path.exists(thermal):
            for zone in sorted(os.listdir(thermal)):
                if zone.startswith("thermal_zone"):
                    try:
                        with open(f"{thermal}/{zone}/temp") as f:
                            t = int(f.read().strip()) / 1000
                            if t > 0:
                                temps.append(t)
                    except Exception:
                        pass
    except Exception:
        pass
    return temps[0] if temps else None

# ── Barra visual ──────────────────────────────────────────────

def pct_bar(pct, width=20, thresholds=(60, 85)):
    pct = max(0.0, min(100.0, float(pct)))
    filled = int((pct / 100.0) * width)
    if pct >= thresholds[1]:
        col = C.R
    elif pct >= thresholds[0]:
        col = C.Y
    else:
        col = C.G
    bar = col + "█" * filled + C.GR + "░" * (width - filled) + C.RESET
    return bar, col

def fmt_bytes(b):
    if b < 1024:      return f"{b}B"
    if b < 1024**2:   return f"{b/1024:.1f}KB"
    if b < 1024**3:   return f"{b/1024**2:.1f}MB"
    return             f"{b/1024**3:.2f}GB"

def fmt_bytes_rate(b):
    return fmt_bytes(b) + "/s"

# ── Render del dashboard ──────────────────────────────────────

def render(interval, show_gpu, show_net, iteration, cpu_history):
    W_TERM = 66

    def row(label, value_str, bar=None, col=None):
        lbl = f"{C.OD}{label:<8}{C.RESET}"
        val = f"{col or C.OG}{value_str}{C.RESET}"
        bar_str = f"  {bar}" if bar else ""
        line = f"  {C.O}║{C.RESET}  {lbl} {val}{bar_str}"
        print(line)

    # ── HEADER ───────────────────────────────────────────────
    now = datetime.now().strftime("%H:%M:%S")
    print(f"{C.CLEAR}", end="")
    print(f"  {C.O}╔{'═'*W_TERM}╗{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.BOLD}{C.OG}GHOST-WATCH{C.RESET}  "
          f"{C.GR}Dashboard en tiempo real{C.RESET}"
          f"  {C.GR}{now}{C.RESET}"
          + " " * (W_TERM - 44) + f"  {C.O}║{C.RESET}")
    print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── CPU ──────────────────────────────────────────────────
    cpu_pct = get_cpu_percent()
    cpu_history.append(cpu_pct)
    if len(cpu_history) > 40:
        cpu_history.pop(0)

    cpu_bar, cpu_col = pct_bar(cpu_pct)
    cpu_model = get_cpu_model()
    la1, la5, la15 = get_loadavg()

    print(f"  {C.O}║{C.RESET}  {C.OD}CPU{C.RESET}  {cpu_col}{cpu_pct:5.1f}%{C.RESET}  "
          f"{cpu_bar}  {C.GR}{cpu_model[:28]}{C.RESET}" + " "*(W_TERM-60) + f"  {C.O}║{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.GR}       Carga: {la1} {la5} {la15}  "
          f"Uptime: {get_uptime()}{C.RESET}" + " "*(W_TERM-48) + f"  {C.O}║{C.RESET}")

    # Mini spark-line de CPU historia
    spark_chars = " ▁▂▃▄▅▆▇█"
    spark = ""
    for v in cpu_history[-36:]:
        idx = min(8, int(v / 100 * 8))
        spark += spark_chars[idx]
    if spark:
        print(f"  {C.O}║{C.RESET}  {C.GR}       {spark}{C.RESET}" + " "*(W_TERM-len(spark)-8) + f"  {C.O}║{C.RESET}")

    # Temperatura CPU
    temp = get_temp()
    if temp:
        tc = C.R if temp > 80 else (C.Y if temp > 65 else C.G)
        print(f"  {C.O}║{C.RESET}  {C.GR}       Temp CPU: {tc}{temp:.0f}°C{C.RESET}" + " "*(W_TERM-26) + f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── RAM ──────────────────────────────────────────────────
    used_kb, total_kb, _ = get_ram()
    if total_kb > 0:
        ram_pct = (used_kb / total_kb) * 100
        ram_bar, ram_col = pct_bar(ram_pct)
        used_g  = used_kb  / 1024 / 1024
        total_g = total_kb / 1024 / 1024
        print(f"  {C.O}║{C.RESET}  {C.OD}RAM{C.RESET}  {ram_col}{ram_pct:5.1f}%{C.RESET}  "
              f"{ram_bar}  {C.GR}{used_g:.1f}GB / {total_g:.1f}GB{C.RESET}" + " "*(W_TERM-60) + f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── DISCO ────────────────────────────────────────────────
    used_b, total_b, _ = get_disk()
    if total_b > 0:
        disk_pct = (used_b / total_b) * 100
        disk_bar, disk_col = pct_bar(disk_pct, thresholds=(70, 90))
        print(f"  {C.O}║{C.RESET}  {C.OD}DISCO{C.RESET} {disk_col}{disk_pct:5.1f}%{C.RESET}  "
              f"{disk_bar}  {C.GR}{fmt_bytes(used_b)} / {fmt_bytes(total_b)}{C.RESET}" + " "*(W_TERM-62) + f"  {C.O}║{C.RESET}")

    print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── RED ──────────────────────────────────────────────────
    if show_net:
        speeds_rx, speeds_tx = get_net_speed()
        if speeds_rx:
            for iface in list(speeds_rx.keys())[:2]:
                rx = speeds_rx.get(iface, 0)
                tx = speeds_tx.get(iface, 0)
                rx_col = C.R if rx > 5*1024*1024 else (C.Y if rx > 1*1024*1024 else C.G)
                tx_col = C.R if tx > 5*1024*1024 else (C.Y if tx > 1*1024*1024 else C.G)
                print(f"  {C.O}║{C.RESET}  {C.OD}RED{C.RESET}   {C.GR}{iface:<8}{C.RESET}  "
                      f"↓{rx_col}{fmt_bytes_rate(rx):<12}{C.RESET}  "
                      f"↑{tx_col}{fmt_bytes_rate(tx):<12}{C.RESET}" + " "*(W_TERM-54) + f"  {C.O}║{C.RESET}")
        print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── GPU ──────────────────────────────────────────────────
    if show_gpu:
        gpu = get_gpu_nvidia()
        if gpu:
            gpu_util_val = gpu['util'].replace('%','').strip()
            try:
                gpu_pct = float(gpu_util_val)
            except ValueError:
                gpu_pct = 0
            gpu_bar, gpu_col = pct_bar(gpu_pct)
            tc = C.R if float(gpu['temp']) > 85 else (C.Y if float(gpu['temp']) > 70 else C.G)
            print(f"  {C.O}║{C.RESET}  {C.OD}GPU{C.RESET}  {gpu_col}{gpu_pct:5.1f}%{C.RESET}  "
                  f"{gpu_bar}  {tc}{gpu['temp']}°C{C.RESET}  "
                  f"{C.GR}{gpu['mem_used']}MB/{gpu['mem_total']}MB{C.RESET}" + " "*(W_TERM-64) + f"  {C.O}║{C.RESET}")
            print(f"  {C.O}║{C.RESET}  {C.GR}       {gpu['name']}{C.RESET}" + " "*(W_TERM-len(gpu['name'])-8) + f"  {C.O}║{C.RESET}")
        else:
            print(f"  {C.O}║{C.RESET}  {C.GR}GPU    no disponible (nvidia-smi no encontrado){C.RESET}" + " "*(W_TERM-48) + f"  {C.O}║{C.RESET}")
        print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")

    # ── TOP PROCESOS ──────────────────────────────────────────
    print(f"  {C.O}║{C.RESET}  {C.OG}TOP PROCESOS{C.RESET}" + " "*(W_TERM-13) + f"  {C.O}║{C.RESET}")
    procs = get_top_procs(5)
    for proc in procs:
        cpu_c = C.R if float(proc['cpu']) > 50 else (C.Y if float(proc['cpu']) > 20 else C.OG)
        print(f"  {C.O}║{C.RESET}  {C.GR}{proc['cmd']:<30}{C.RESET}  "
              f"PID:{C.GR}{proc['pid']:<7}{C.RESET}  "
              f"CPU:{cpu_c}{proc['cpu']:>5}%{C.RESET}  "
              f"MEM:{C.OD}{proc['mem']:>5}%{C.RESET}" + " "*(W_TERM-60) + f"  {C.O}║{C.RESET}")

    # ── FOOTER ───────────────────────────────────────────────
    print(f"  {C.O}╠{'═'*W_TERM}╣{C.RESET}")
    print(f"  {C.O}║{C.RESET}  {C.GR}Actualizando cada {interval}s  "
          f"│  Iter: {iteration}  "
          f"│  Ctrl+C para salir{C.RESET}" + " "*(W_TERM-52) + f"  {C.O}║{C.RESET}")
    print(f"  {C.O}╚{'═'*W_TERM}╝{C.RESET}")

def main():
    p = argparse.ArgumentParser(description="ghost-watch — Dashboard live del sistema")
    p.add_argument("--interval", type=float, default=1.0, help="Segundos entre actualizaciones")
    p.add_argument("--gpu",      action="store_true", help="Mostrar info GPU NVIDIA")
    p.add_argument("--net",      action="store_true", help="Mostrar velocidad de red")
    p.add_argument("--full",     action="store_true", help="Mostrar todo (GPU + red)")
    args = p.parse_args()

    show_gpu = args.gpu or args.full
    show_net = args.net or args.full

    print(f"{C.O}  GHOST-WATCH · Iniciando...{C.RESET}")
    time.sleep(0.5)

    # Primera lectura para calibrar CPU y red
    get_cpu_percent()
    get_net_speed()
    time.sleep(args.interval)

    cpu_history = []
    iteration   = 0

    try:
        while True:
            iteration += 1
            render(args.interval, show_gpu, show_net, iteration, cpu_history)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n\n  {C.OD}[ghost-watch] Detenido.{C.RESET}\n")

if __name__ == "__main__":
    main()
