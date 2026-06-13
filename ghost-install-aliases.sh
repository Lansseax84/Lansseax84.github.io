#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  ghost-install-aliases.sh — GHOST EYES PROJECT                  ║
# ║  Instala todos los comandos ghost-* de forma permanente          ║
# ║  Para ejecutarlos desde cualquier lugar sin ir a Descargas       ║
# ║                                                                  ║
# ║  Con sudo   → instala en /usr/local/bin (todos los usuarios)     ║
# ║  Sin sudo   → instala en ~/.local/bin   (solo tu usuario)        ║
# ║                                                                  ║
# ║  Uso: bash ghost-install-aliases.sh                              ║
# ║   o:  sudo bash ghost-install-aliases.sh                         ║
# ╚══════════════════════════════════════════════════════════════════╝

O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GR="\033[38;5;64m"; R="\033[38;5;160m";  Y="\033[38;5;136m"
GY="\033[38;5;238m"; RESET="\033[0m";    BOLD="\033[1m"

log()    { echo -e "${O}[ghost-aliases]${RESET} $*"; }
ok()     { echo -e "  ${GR}✓${RESET} $*"; }
warn()   { echo -e "  ${Y}⚠${RESET} $*"; }
err()    { echo -e "  ${R}✗${RESET} $*"; }
header() {
  echo -e "\n${O}══════════════════════════════════════════════════${RESET}"
  echo -e "  ${OG}${BOLD}$*${RESET}"
  echo -e "${O}══════════════════════════════════════════════════${RESET}\n"
}

clear
echo -e "${O}"
cat << 'BANNER'
   █████╗ ██╗     ██╗ █████╗ ███████╗███████╗███████╗
  ██╔══██╗██║     ██║██╔══██╗██╔════╝██╔════╝██╔════╝
  ███████║██║     ██║███████║███████╗█████╗  ███████╗
  ██╔══██║██║     ██║██╔══██║╚════██║██╔══╝  ╚════██║
  ██║  ██║███████╗██║██║  ██║███████║███████╗███████║
  ╚═╝  ╚═╝╚══════╝╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
BANNER
echo -e "${RESET}"
echo -e "  ${OD}GHOST EYES · Instalador de comandos permanentes${RESET}\n"

# ── Detectar directorio del script ──────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log "Carpeta de scripts detectada: ${OG}${SCRIPT_DIR}${RESET}"

# ── Decidir destino según privilegios ───────────────────────
if [ "$EUID" -eq 0 ]; then
  INSTALL_DIR="/usr/local/bin"
  SCOPE="sistema (todos los usuarios)"
else
  INSTALL_DIR="$HOME/.local/bin"
  SCOPE="usuario actual ($USER)"
fi

log "Destino de instalación: ${OG}${INSTALL_DIR}${RESET} — ${GY}${SCOPE}${RESET}"
mkdir -p "$INSTALL_DIR"

# ── Detectar usuario real (por si se usa sudo) ───────────────
if [ -n "$SUDO_USER" ]; then
  REAL_USER="$SUDO_USER"
  REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
  REAL_USER="$USER"
  REAL_HOME="$HOME"
fi

# ── Definir todos los comandos ghost-* ───────────────────────
# Formato: "nombre_comando:archivo_fuente:necesita_sudo"
declare -a COMMANDS=(
  "ghost-map:ghost-map.py:si"
  "ghost-log:ghost-log.py:no"
  "ghost-send:ghost-send.py:no"
  "ghost-trace:ghost-trace.py:no"
  "ghost-watch:ghost-watch.py:no"
  "ghost-wallpaper:ghost-wallpaper.py:no"
  "ghost-plymouth-gen:ghost-plymouth-gen.py:si"
  "ghost-clean:ghost-clean.sh:si"
  "ghost-nvidia:ghost-nvidia.sh:si"
  "ghost-nvidia-kali:ghost-nvidia-kali.sh:si"
  "ghost-drivers:ghost-drivers.sh:si"
  "ghost-rescue:ghost-rescue.sh:si"
  "ghost-boot-login:ghost-boot-login.sh:si"
  "ghost-desktop:ghost-desktop.sh:no"
  "ghost-build-iso:ghost-build-iso.sh:si"
)

# ════════════════════════════════════════════════════════════
header "PASO 1 · INSTALAR COMANDOS EN ${INSTALL_DIR}"
# ════════════════════════════════════════════════════════════

INSTALLED=()
SKIPPED=()
CREATED_INLINE=()

for entry in "${COMMANDS[@]}"; do
  CMD_NAME=$(echo "$entry"  | cut -d: -f1)
  SRC_FILE=$(echo "$entry"  | cut -d: -f2)
  NEEDS_SUDO=$(echo "$entry" | cut -d: -f3)
  SRC_PATH="${SCRIPT_DIR}/${SRC_FILE}"
  DST_PATH="${INSTALL_DIR}/${CMD_NAME}"

  if [ ! -f "$SRC_PATH" ]; then
    warn "${CMD_NAME} — archivo no encontrado: ${SRC_FILE}"
    SKIPPED+=("$CMD_NAME")
    continue
  fi

  # Copiar al destino
  cp "$SRC_PATH" "$DST_PATH"

  # Asegurar shebang correcto según tipo
  case "$SRC_FILE" in
    *.py)
      FIRST_LINE=$(head -1 "$DST_PATH")
      if [[ "$FIRST_LINE" != "#!/usr/bin/env python3"* ]]; then
        # Insertar shebang al principio
        echo -e "#!/usr/bin/env python3\n$(cat "$DST_PATH")" > "$DST_PATH"
      fi
      ;;
    *.sh)
      FIRST_LINE=$(head -1 "$DST_PATH")
      if [[ "$FIRST_LINE" != "#!/bin/bash"* ]] && [[ "$FIRST_LINE" != "#!/usr/bin/env bash"* ]]; then
        echo -e "#!/bin/bash\n$(cat "$DST_PATH")" > "$DST_PATH"
      fi
      ;;
  esac

  # Permisos de ejecución
  chmod +x "$DST_PATH"

  # Wrapper sudo para comandos que lo necesitan
  if [ "$NEEDS_SUDO" = "si" ] && [ "$EUID" -ne 0 ]; then
    # Crear wrapper que añade sudo automáticamente
    WRAPPER_PATH="${INSTALL_DIR}/${CMD_NAME}"
    cat > "$WRAPPER_PATH" << WRAPPER
#!/bin/bash
# Ghost Eyes wrapper — ejecuta con sudo automáticamente
if [ "\$EUID" -ne 0 ]; then
  echo -e "\033[38;5;166m[ghost-eyes]\033[0m Este comando requiere privilegios de administrador."
  exec sudo "${DST_PATH}.real" "\$@"
else
  exec "${DST_PATH}.real" "\$@"
fi
WRAPPER
    # Mover el real
    mv "$DST_PATH" "${DST_PATH}.real" 2>/dev/null || true
    # Si falla el mv, simplemente usar el directo
    if [ ! -f "${DST_PATH}.real" ]; then
      cp "$SRC_PATH" "${DST_PATH}.real"
    fi
    chmod +x "$WRAPPER_PATH" "${DST_PATH}.real"
  fi

  ok "${CMD_NAME} → ${DST_PATH}"
  INSTALLED+=("$CMD_NAME")
done

# ── Crear ghost-status como script inline ───────────────────
cat > "${INSTALL_DIR}/ghost-status" << 'GSTATUS'
#!/bin/bash
O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GR="\033[38;5;64m"; GY="\033[38;5;238m"; RESET="\033[0m"
clear
echo -e "${O}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}GHOST-STATUS · DASHBOARD${RESET}                          ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
CPU=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{printf "%.0f", $2}')
RAM=$(free -h 2>/dev/null | grep Mem | awk '{print $3" / "$2}')
DISK=$(df -h / 2>/dev/null | tail -1 | awk '{print $3" / "$2" ("$5")"}')
IP=$(ip route get 8.8.8.8 2>/dev/null | grep src | awk '{print $7}')
UPTIME=$(uptime -p 2>/dev/null | sed 's/up //')
echo -e "${O}║${RESET}  ${OD}CPU   ${RESET}${CPU:- ?}%                                       ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}RAM   ${RESET}${RAM:-?}                                    ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}DISCO ${RESET}${DISK:-?}                               ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}IP    ${RESET}${IP:-sin red}                                 ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}UPTIME${RESET} ${UPTIME:-?}                                ${O}║${RESET}"
if command -v nvidia-smi &>/dev/null; then
  GPU=$(nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu \
        --format=csv,noheader,nounits 2>/dev/null | head -1)
  echo -e "${O}║${RESET}  ${OD}GPU   ${RESET}${GPU:-?}                         ${O}║${RESET}"
fi
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OG}TOP PROCESOS${RESET}                                       ${O}║${RESET}"
ps aux --sort=-%cpu 2>/dev/null | tail -n +2 | head -4 | \
while read u p cp mp v r s t c cmd; do
  CMD_S=$(echo "$cmd" | cut -c1-22)
  echo -e "${O}║${RESET}  ${OD}${CMD_S}${RESET}$(printf '%*s' $((24-${#CMD_S})) '') CPU:${cp}%  MEM:${mp}%  ${O}║${RESET}"
done
echo -e "${O}╚══════════════════════════════════════════════════════╝${RESET}"
GSTATUS
chmod +x "${INSTALL_DIR}/ghost-status"
ok "ghost-status → ${INSTALL_DIR}/ghost-status (inline)"
INSTALLED+=("ghost-status")

# ── Crear ghost-help actualizado ─────────────────────────────
cat > "${INSTALL_DIR}/ghost-help" << 'GHELP'
#!/bin/bash
O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GY="\033[38;5;238m"; GR="\033[38;5;64m"; RESET="\033[0m"; BOLD="\033[1m"
echo -e "\n${O}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}${BOLD}GHOST EYES · COMANDOS DISPONIBLES${RESET}                     ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════════╣${RESET}"
cmds=(
  "ghost-map        Mapa visual de red + detección de intrusos"
  "ghost-status     Dashboard CPU / RAM / GPU / Red"
  "ghost-log        Logs del sistema en lenguaje humano"
  "ghost-send       Mensajería cifrada P2P entre IPs"
  "ghost-trace      Traceroute visual con colores por latencia"
  "ghost-watch      Dashboard live que se actualiza cada segundo"
  "ghost-clean      Limpieza de caché, logs y temporales"
  "ghost-wallpaper  Aplicar fondo de pantalla Ghost Eyes"
  "ghost-desktop    Tema completo escritorio XFCE naranja"
  "ghost-nvidia     Instalar drivers RTX 5060 Blackwell"
  "ghost-drivers    Instalador universal GPU (NVIDIA/AMD/Intel)"
  "ghost-rescue     Reparar GUI desde TTY"
  "ghost-boot-login Plymouth grande + login verde retro"
  "ghost-build-iso  Construir ISO booteable Ghost Eyes"
  "ghost-help       Este menú"
)
for cmd in "${cmds[@]}"; do
  NAME=$(echo "$cmd" | awk '{print $1}')
  DESC=$(echo "$cmd" | cut -d' ' -f2-)
  if command -v "$NAME" &>/dev/null; then
    STATUS="${GR}✓${RESET}"
  else
    STATUS="${OD}·${RESET}"
  fi
  echo -e "${O}║${RESET}  $STATUS ${OG}${NAME}${RESET}$(printf '%*s' $((18-${#NAME})) '') ${GY}${DESC}${RESET}"
done
echo -e "${O}╠══════════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${GY}Usa: ghost-<comando> --help  para más opciones${RESET}        ${O}║${RESET}"
echo -e "${O}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""
GHELP
chmod +x "${INSTALL_DIR}/ghost-help"
ok "ghost-help → ${INSTALL_DIR}/ghost-help"
INSTALLED+=("ghost-help")

# ════════════════════════════════════════════════════════════
header "PASO 2 · CONFIGURAR PATH Y ALIASES PERMANENTES"
# ════════════════════════════════════════════════════════════

# Bloque que se añade a .bashrc y .zshrc
SHELL_BLOCK="
# ════════════════════════════════════════════════════════════
# GHOST EYES PROJECT — Comandos permanentes
# Instalado automáticamente por ghost-install-aliases.sh
# ════════════════════════════════════════════════════════════

# Añadir al PATH si no está
if [[ \":\$PATH:\" != *\":${INSTALL_DIR}:\"* ]]; then
  export PATH=\"${INSTALL_DIR}:\$PATH\"
fi

# Aliases cortos
alias gm='ghost-map'
alias gl='ghost-log'
alias gs='ghost-status'
alias gw='ghost-watch'
alias gt='ghost-trace'
alias gc='ghost-clean'
alias gsend='ghost-send'
alias ghelp='ghost-help'

# Prompt naranja Ghost Eyes
export PS1='\[\033[38;5;166m\]ghost-eyes\[\033[38;5;238m\]:\[\033[38;5;130m\]\w\[\033[0m\]\$ '

# Colores para ls y grep
export LS_COLORS=\"di=38;5;166:ln=38;5;208:ex=38;5;208:*.sh=38;5;208:*.py=38;5;166\"
export GREP_COLORS=\"mt=38;5;208:fn=38;5;166\"
alias ls='ls --color=always'
alias grep='grep --color=always'

# ════════════════════════════════════════════════════════════
"

# Función para añadir bloque a un archivo de shell
add_to_shell_file() {
  local shell_file="$1"
  local marker="GHOST EYES PROJECT — Comandos permanentes"

  if [ ! -f "$shell_file" ]; then
    touch "$shell_file"
  fi

  if grep -q "$marker" "$shell_file" 2>/dev/null; then
    # Ya existe — actualizar el bloque
    # Borrar bloque anterior y añadir el nuevo
    python3 - "$shell_file" "$marker" << 'PYREPLACE'
import sys
path   = sys.argv[1]
marker = sys.argv[2]
with open(path) as f:
    content = f.read()

# Encontrar y eliminar bloque anterior
start_marker = "# ═══════════════════════════════════════"
# Buscar desde el comentario GHOST EYES hacia atrás hasta encontrar el bloque
lines = content.split('\n')
new_lines = []
skip = False
for i, line in enumerate(lines):
    if marker in line:
        # Retroceder para incluir la línea de === anterior
        if new_lines and '═══' in new_lines[-1]:
            new_lines.pop()
        if new_lines and new_lines[-1].strip() == '':
            new_lines.pop()
        skip = True
    elif skip and line.strip() == '# ════════════════════════════════════════════════════════════':
        # Fin del bloque ghost eyes
        skip = False
        # Saltar esta línea también
    elif not skip:
        new_lines.append(line)

with open(path, 'w') as f:
    f.write('\n'.join(new_lines))
PYREPLACE
    warn "${shell_file} — bloque anterior eliminado, añadiendo versión actualizada"
  fi

  echo "$SHELL_BLOCK" >> "$shell_file"
  ok "${shell_file} actualizado"
}

# .bashrc del usuario real
BASHRC="${REAL_HOME}/.bashrc"
add_to_shell_file "$BASHRC"

# .zshrc del usuario real
ZSHRC="${REAL_HOME}/.zshrc"
add_to_shell_file "$ZSHRC"

# Si root instaló, también actualizar /etc/skel para nuevos usuarios
if [ "$EUID" -eq 0 ]; then
  add_to_shell_file "/etc/skel/.bashrc"
  ok "/etc/skel/.bashrc actualizado (nuevos usuarios)"
fi

# ════════════════════════════════════════════════════════════
header "PASO 3 · VERIFICAR INSTALACIÓN"
# ════════════════════════════════════════════════════════════

echo -e "  ${OD}Comandos instalados en ${INSTALL_DIR}:${RESET}\n"

ALL_OK=true
for cmd in "${INSTALLED[@]}"; do
  BIN_PATH="${INSTALL_DIR}/${cmd}"
  if [ -x "$BIN_PATH" ]; then
    echo -e "  ${GR}✓${RESET}  ${OG}${cmd}${RESET}"
  else
    echo -e "  ${R}✗${RESET}  ${cmd} — fallo"
    ALL_OK=false
  fi
done

if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo ""
  echo -e "  ${Y}Omitidos (archivo no encontrado en ${SCRIPT_DIR}):${RESET}"
  for s in "${SKIPPED[@]}"; do
    echo -e "  ${Y}·${RESET} ${s}"
  done
fi

# ════════════════════════════════════════════════════════════
header "PASO 4 · APLICAR EN SESIÓN ACTUAL"
# ════════════════════════════════════════════════════════════

# Añadir al PATH de la sesión actual también
export PATH="${INSTALL_DIR}:$PATH"

# Crear archivo de entorno para sesión inmediata
ENV_FILE="/tmp/ghost-eyes-env.sh"
cat > "$ENV_FILE" << EOF
#!/bin/bash
export PATH="${INSTALL_DIR}:\$PATH"
alias gm='ghost-map'
alias gl='ghost-log'
alias gs='ghost-status'
alias gw='ghost-watch'
alias gt='ghost-trace'
alias gc='ghost-clean'
alias gsend='ghost-send'
alias ghelp='ghost-help'
export PS1='\[\033[38;5;166m\]ghost-eyes\[\033[38;5;238m\]:\[\033[38;5;130m\]\w\[\033[0m\]\$ '
echo -e "\033[38;5;166m[ghost-eyes]\033[0m Comandos activados en esta sesión."
EOF
chmod +x "$ENV_FILE"

# ════════════════════════════════════════════════════════════
echo ""
echo -e "${O}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}${BOLD}INSTALACIÓN COMPLETADA${RESET}                                   ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${GR}✓${RESET} ${#INSTALLED[@]} comandos instalados en ${INSTALL_DIR}         ${O}║${RESET}"
echo -e "${O}║${RESET}  ${GR}✓${RESET} PATH añadido permanentemente a .bashrc y .zshrc       ${O}║${RESET}"
echo -e "${O}║${RESET}  ${GR}✓${RESET} Aliases cortos: gm gl gs gw gt gc gsend ghelp         ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OD}PARA ACTIVAR EN ESTE TERMINAL AHORA MISMO:${RESET}            ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OG}  source ~/.bashrc${RESET}                                       ${O}║${RESET}"
echo -e "${O}║${RESET}    o abre un terminal nuevo                                ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OD}COMANDOS DISPONIBLES DESPUÉS:${RESET}                          ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OG}ghost-help${RESET}   Ver todos los comandos                      ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OG}ghost-map${RESET}    Mapa de red (= gm)                          ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OG}ghost-log${RESET}    Ver logs    (= gl)                          ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OG}ghost-watch${RESET}  Dashboard   (= gw)                          ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${GY}Log: /var/log/ghost-aliases.log${RESET}                         ${O}║${RESET}"
echo -e "${O}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# Activar en sesión actual automáticamente
log "Activando en sesión actual..."
# shellcheck disable=SC1090
source "$BASHRC" 2>/dev/null || true
log "Listo. Escribe ${OG}ghost-help${RESET} para ver todos los comandos."
echo ""
