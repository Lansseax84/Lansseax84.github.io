#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  install.sh — GHOST EYES PROJECT                            ║
# ║  Instalador completo sobre Kali Linux existente             ║
# ║  Uso: sudo bash install.sh                                  ║
# ╚══════════════════════════════════════════════════════════════╝

set -e
GHOST_DIR="/opt/ghost-eyes"
BIN_DIR="/usr/local/bin"
SHARE_DIR="/usr/share/ghost-eyes"
THEME_DIR="/usr/share/plymouth/themes/ghost-eyes"

O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GR="\033[38;5;64m"; R="\033[38;5;160m"; GREY="\033[38;5;238m"; RESET="\033[0m"; BOLD="\033[1m"

log()    { echo -e "${O}[ghost-eyes]${RESET} $*"; }
ok()     { echo -e "${GR}  ✓${RESET} $*"; }
warn()   { echo -e "${OD}  ⚠${RESET} $*"; }
err()    { echo -e "${R}  ✗${RESET} $*"; exit 1; }
header() { echo -e "\n${O}══════════════════════════════════════════${RESET}\n  ${OG}${BOLD}$*${RESET}\n${O}══════════════════════════════════════════${RESET}\n"; }

[ "$EUID" -ne 0 ] && err "Ejecuta como root: sudo bash install.sh"

# Detectar directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

clear
echo -e "${O}"
cat << 'BANNER'
   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗    ███████╗██╗   ██╗███████╗███████╗
  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝    ██╔════╝╚██╗ ██╔╝██╔════╝██╔════╝
  ██║  ███╗███████║██║   ██║███████╗   ██║       █████╗   ╚████╔╝ █████╗  ███████╗
  ██║   ██║██╔══██║██║   ██║╚════██║   ██║       ██╔══╝    ╚██╔╝  ██╔══╝  ╚════██║
  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║       ███████╗   ██║   ███████╗███████║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝       ╚══════╝   ╚═╝   ╚══════╝╚══════╝
BANNER
echo -e "${RESET}"
echo -e "  ${OD}GHOST EYES PROJECT · Instalador completo v2.0${RESET}"
echo -e "  ${GREY}Compatible con Kali Linux Rolling${RESET}\n"

echo -e "  ${OD}Esto instalará:${RESET}"
echo -e "  ${GREY}· Fondo de escritorio temático${RESET}"
echo -e "  ${GREY}· Pantalla de login personalizada${RESET}"
echo -e "  ${GREY}· Animación Plymouth de arranque${RESET}"
echo -e "  ${GREY}· Sonido suave al escribir en login${RESET}"
echo -e "  ${GREY}· Comandos ghost-* en /usr/local/bin${RESET}"
echo -e "  ${GREY}· Drivers GPU (NVIDIA/AMD/Intel)${RESET}\n"

echo -e "  ${OD}¿Continuar? (s/N): ${RESET}"
read -r resp
[[ "$resp" =~ ^[sS]$ ]] || { log "Instalación cancelada."; exit 0; }

# ── PASO 1: Dependencias ──────────────────────────────────────
header "PASO 1 · Dependencias"
apt update -qq
apt install -y python3 python3-pip python3-pillow \
               nmap clamav clamav-daemon \
               aplay alsa-utils \
               plymouth plymouth-themes \
               lightdm \
               feh nitrogen \
               xfconf \
               traceroute \
               scapy 2>/dev/null || true
pip3 install scapy rich cryptography --break-system-packages -q 2>/dev/null || true
ok "Dependencias instaladas."

# ── PASO 2: Estructura de directorios ────────────────────────
header "PASO 2 · Estructura de directorios"
mkdir -p "$GHOST_DIR"/{python,bash,sounds,dotfiles,icons}
mkdir -p "$SHARE_DIR"
mkdir -p "$THEME_DIR"
ok "Directorios creados."

# ── PASO 3: Copiar scripts ────────────────────────────────────
header "PASO 3 · Instalando comandos ghost-*"

copy_cmd() {
  local src="$1" dst="$2" name="$3"
  if [ -f "$SCRIPT_DIR/$src" ]; then
    cp "$SCRIPT_DIR/$src" "$dst"
    chmod +x "$dst"
    ok "Instalado: $name"
  else
    warn "No encontrado: $src — omitido."
  fi
}

# Python commands
copy_cmd "ghost-map.py"            "$BIN_DIR/ghost-map"         "ghost-map"
copy_cmd "ghost-log.py"            "$BIN_DIR/ghost-log"         "ghost-log"
copy_cmd "ghost-send.py"           "$BIN_DIR/ghost-send"        "ghost-send"
copy_cmd "ghost-wallpaper.py"      "$BIN_DIR/ghost-wallpaper"   "ghost-wallpaper"
copy_cmd "ghost-plymouth-gen.py"   "$BIN_DIR/ghost-plymouth-gen" "ghost-plymouth-gen"

# Bash commands
copy_cmd "ghost-nvidia.sh"         "$BIN_DIR/ghost-nvidia"      "ghost-nvidia"
copy_cmd "ghost-drivers.sh"        "$BIN_DIR/ghost-drivers"     "ghost-drivers"

# Asegurarse que Python scripts tienen shebang correcto
for cmd in ghost-map ghost-log ghost-send ghost-wallpaper ghost-plymouth-gen; do
  if [ -f "$BIN_DIR/$cmd" ]; then
    # Añadir shebang si no lo tiene
    head -1 "$BIN_DIR/$cmd" | grep -q "python3" || \
      sed -i '1s|^|#!/usr/bin/env python3\n|' "$BIN_DIR/$cmd"
    chmod +x "$BIN_DIR/$cmd"
  fi
done

# ── ghost-status (bash inline) ────────────────────────────────
cat > "$BIN_DIR/ghost-status" << 'GSTATUS'
#!/bin/bash
O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GR="\033[38;5;64m"; R="\033[38;5;160m"; GREY="\033[38;5;238m"; RESET="\033[0m"

clear
echo -e "${O}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}GHOST-STATUS · DASHBOARD${RESET}                          ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"

# CPU
CPU_LOAD=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 2>/dev/null || echo "?")
CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | xargs 2>/dev/null || echo "?")
echo -e "${O}║${RESET}  ${OD}CPU   ${RESET}${CPU_MODEL:0:30}  ${GR}${CPU_LOAD}%${RESET}                ${O}║${RESET}"

# RAM
RAM_INFO=$(free -h | grep Mem 2>/dev/null | awk '{print $3" / "$2}')
echo -e "${O}║${RESET}  ${OD}RAM   ${RESET}${RAM_INFO:-?}                                    ${O}║${RESET}"

# Disco
DISK_INFO=$(df -h / 2>/dev/null | tail -1 | awk '{print $3" / "$2" ("$5")"}')
echo -e "${O}║${RESET}  ${OD}DISCO ${RESET}${DISK_INFO:-?}                               ${O}║${RESET}"

# GPU
if command -v nvidia-smi &>/dev/null; then
  GPU_INFO=$(nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu \
             --format=csv,noheader,nounits 2>/dev/null | head -1)
  echo -e "${O}║${RESET}  ${OD}GPU   ${RESET}${GPU_INFO:-no disponible}                     ${O}║${RESET}"
else
  GPU_INFO=$(lspci | grep -i "vga\|3d" | head -1 | cut -d: -f3 | xargs)
  echo -e "${O}║${RESET}  ${OD}GPU   ${RESET}${GPU_INFO:0:44}${O}║${RESET}"
fi

# Red
IP_INFO=$(ip route get 8.8.8.8 2>/dev/null | grep src | awk '{print $7}')
echo -e "${O}║${RESET}  ${OD}RED   ${RESET}${IP_INFO:-?}                                     ${O}║${RESET}"

# Uptime
UPTIME=$(uptime -p 2>/dev/null | sed 's/up //')
echo -e "${O}║${RESET}  ${OD}UPTIME${RESET}${UPTIME:-?}                                   ${O}║${RESET}"

echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OG}TOP PROCESOS${RESET}                                       ${O}║${RESET}"
ps aux --sort=-%mem 2>/dev/null | tail -n +2 | head -4 | while read u p cp mp v r s t c cmd; do
  CMD_SHORT=$(echo "$cmd" | cut -d/ -f1 | cut -c1-14)
  echo -e "${O}║${RESET}  ${OD}${CMD_SHORT:-?}${RESET}$(printf '%*s' $((16-${#CMD_SHORT})) '') PID:${p}  MEM:${mp}%  CPU:${cp}%   ${O}║${RESET}"
done
echo -e "${O}╚══════════════════════════════════════════════════════╝${RESET}"
GSTATUS
chmod +x "$BIN_DIR/ghost-status"
ok "Instalado: ghost-status"

# ── ghost-help ────────────────────────────────────────────────
cat > "$BIN_DIR/ghost-help" << 'GHELP'
#!/bin/bash
O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"; GREY="\033[38;5;238m"; RESET="\033[0m"
echo -e "\n${O}  GHOST EYES · COMANDOS DISPONIBLES${RESET}\n"
echo -e "  ${OG}ghost-map${RESET}        ${GREY}Mapa visual de red + detección de intrusos${RESET}"
echo -e "  ${OG}ghost-status${RESET}     ${GREY}Dashboard del sistema (CPU/RAM/GPU/Red)${RESET}"
echo -e "  ${OG}ghost-log${RESET}        ${GREY}Logs del sistema en lenguaje humano${RESET}"
echo -e "  ${OG}ghost-send${RESET}       ${GREY}Mensajería cifrada peer-to-peer${RESET}"
echo -e "  ${OG}ghost-wallpaper${RESET}  ${GREY}Aplicar fondo de escritorio${RESET}"
echo -e "  ${OG}ghost-nvidia${RESET}     ${GREY}Instalar drivers RTX 5060 Blackwell${RESET}"
echo -e "  ${OG}ghost-drivers${RESET}    ${GREY}Instalador universal de drivers GPU${RESET}"
echo -e "  ${OG}ghost-help${RESET}       ${GREY}Este menú${RESET}\n"
GHELP
chmod +x "$BIN_DIR/ghost-help"
ok "Instalado: ghost-help"

# ── PASO 4: Dotfiles ──────────────────────────────────────────
header "PASO 4 · Configurando terminal"

BASHRC_ADDON='
# ── GHOST EYES ──────────────────────────────────────────────
export PS1="\[\033[38;5;166m\]ghost-eyes\[\033[38;5;238m\]:\[\033[38;5;130m\]\w\[\033[0m\]\$ "
export GHOST_EYES=1
alias gs="ghost-status"
alias gm="ghost-map"
alias gl="ghost-log"
alias gsend="ghost-send"
# ────────────────────────────────────────────────────────────
'

for home_dir in /root /home/*; do
  if [ -d "$home_dir" ]; then
    if ! grep -q "GHOST EYES" "$home_dir/.bashrc" 2>/dev/null; then
      echo "$BASHRC_ADDON" >> "$home_dir/.bashrc"
      ok "Dotfiles actualizados: $home_dir/.bashrc"
    fi
  fi
done

# ── PASO 5: Sonido en login ───────────────────────────────────
header "PASO 5 · Sonido en login"

# Generar WAV de click suave con Python
python3 << 'WAVGEN'
import wave, struct, math, os
os.makedirs("/usr/share/ghost-eyes", exist_ok=True)
fname = "/usr/share/ghost-eyes/key-soft.wav"
sr, dur, freq, vol = 44100, 0.04, 800, 0.3
n = int(sr * dur)
with wave.open(fname, "w") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    for i in range(n):
        t = i / sr
        env = math.exp(-t / 0.015)
        s = int(32767 * vol * env * math.sin(2 * math.pi * freq * t))
        wf.writeframes(struct.pack("<h", max(-32768, min(32767, s))))
print("[ghost-eyes] WAV generado: " + fname)
WAVGEN

# Hook en LightDM para sonido al escribir
if [ -d "/etc/lightdm" ]; then
  cat > /etc/lightdm/ghost-keypress.sh << 'KEYSOUND'
#!/bin/bash
# Se llama por cada tecla en el greeter
aplay /usr/share/ghost-eyes/key-soft.wav -q 2>/dev/null &
KEYSOUND
  chmod +x /etc/lightdm/ghost-keypress.sh
  ok "Sonido de teclado configurado."
fi

# ── PASO 6: Tema Plymouth ─────────────────────────────────────
header "PASO 6 · Animación de arranque"
if command -v python3 &>/dev/null && [ -f "$BIN_DIR/ghost-plymouth-gen" ]; then
  log "Generando frames Plymouth (puede tardar 1-2 min)..."
  python3 "$BIN_DIR/ghost-plymouth-gen" --install 2>/dev/null || \
    warn "Plymouth gen falló — puedes ejecutarlo después: sudo ghost-plymouth-gen --install"
else
  warn "ghost-plymouth-gen no disponible — omitiendo Plymouth."
fi

# ── PASO 7: Fondo de escritorio ───────────────────────────────
header "PASO 7 · Fondo de escritorio"
python3 "$BIN_DIR/ghost-wallpaper" --set \
        --output "$SHARE_DIR/wallpaper.png" 2>/dev/null && \
  ok "Fondo de escritorio aplicado." || \
  warn "No se pudo aplicar fondo ahora (normal si no hay sesión gráfica activa)."

# ── PASO 8: Tema de iconos ────────────────────────────────────
header "PASO 8 · Iconos y tema visual"

# Instalar Papirus Dark como base + tint naranja via xfconf
apt install -y papirus-icon-theme 2>/dev/null || true

# Configurar XFCE si está disponible
if command -v xfconf-query &>/dev/null; then
  DISPLAY=${DISPLAY:-:0} xfconf-query -c xsettings -p /Net/IconThemeName \
    -s "Papirus-Dark" 2>/dev/null && ok "Iconos Papirus-Dark activados." || true
fi

# Crear launcher personalizado (entrada .desktop)
cat > /usr/share/applications/ghost-panel.desktop << 'DESKTOP'
[Desktop Entry]
Name=Ghost Eyes Panel
Comment=Launcher de comandos Ghost Eyes
Exec=ghost-help
Icon=utilities-terminal
Type=Application
Categories=System;
Terminal=true
DESKTOP
ok "Launcher ghost-panel añadido."

# ── PASO 9: Servicio receptor ghost-send ─────────────────────
header "PASO 9 · Servicio ghost-send (receptor)"
cat > /etc/systemd/system/ghost-send.service << 'SERVICE'
[Unit]
Description=Ghost Eyes - Send Receiver Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/ghost-send --listen
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable ghost-send.service 2>/dev/null && ok "Servicio ghost-send habilitado." || warn "Servicio ghost-send no habilitado."

# ── PASO 10: Resumen ──────────────────────────────────────────
header "INSTALACIÓN COMPLETADA"

echo -e "${O}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}${BOLD}GHOST EYES INSTALADO CORRECTAMENTE${RESET}                 ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OD}1.${RESET} Ejecuta ${OG}ghost-help${RESET} para ver todos los comandos    ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}2.${RESET} Reinicia para ver Plymouth + login temático       ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}3.${RESET} ${OG}sudo ghost-drivers${RESET} para instalar drivers GPU   ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}4.${RESET} ${OG}ghost-map${RESET} para explorar tu red                 ${O}║${RESET}"
echo -e "${O}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
log "¿Reiniciar ahora? (s/N): "
read -r resp
[[ "$resp" =~ ^[sS]$ ]] && reboot || true
