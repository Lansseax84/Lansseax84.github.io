#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  ghost-nvidia — GHOST EYES PROJECT                          ║
# ║  Instalador de drivers NVIDIA RTX 5060 (Blackwell) en Kali  ║
# ║  Uso: sudo bash ghost-nvidia.sh                             ║
# ╚══════════════════════════════════════════════════════════════╝
#
# NOTAS IMPORTANTES RTX 5060 (arquitectura Blackwell GB206):
#  · Requiere driver 570.169+ con módulos OPEN (no el propietario)
#  · El driver totalmente propietario NO funciona con Blackwell
#  · Necesita kernel 6.11+ (recomendado 6.14+)
#  · Debe arrancar en modo UEFI, NO en Legacy/CSM
#  · Si tienes pantalla negra tras instalar: es porque usaste
#    el driver propietario clásico. Este script lo corrige.

set -e

O="\033[38;5;166m"
OD="\033[38;5;130m"
OG="\033[38;5;208m"
G="\033[38;5;238m"
R="\033[38;5;160m"
GR="\033[38;5;22m"
RESET="\033[0m"
BOLD="\033[1m"

log()    { echo -e "${O}[ghost-nvidia]${RESET} $*"; }
ok()     { echo -e "${GR}[  OK  ]${RESET} $*"; }
warn()   { echo -e "${OD}[ WARN ]${RESET} $*"; }
err()    { echo -e "${R}[ FAIL ]${RESET} $*"; exit 1; }
header() { echo -e "\n${O}══════════════════════════════════════════${RESET}"; echo -e "  ${OG}${BOLD}$*${RESET}"; echo -e "${O}══════════════════════════════════════════${RESET}\n"; }

# ── Verificar root ───────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  err "Ejecuta como root: sudo bash ghost-nvidia.sh"
fi

clear
echo -e "${O}"
cat << 'EOF'
  ███╗   ██╗██╗   ██╗██╗██████╗ ██╗ █████╗
  ████╗  ██║██║   ██║██║██╔══██╗██║██╔══██╗
  ██╔██╗ ██║██║   ██║██║██║  ██║██║███████║
  ██║╚██╗██║╚██╗ ██╔╝██║██║  ██║██║██╔══██║
  ██║ ╚████║ ╚████╔╝ ██║██████╔╝██║██║  ██║
  ╚═╝  ╚═══╝  ╚═══╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝
EOF
echo -e "${RESET}"
echo -e "  ${OD}GHOST EYES · Instalador de drivers RTX 5060 (Blackwell)${RESET}"
echo -e "  ${G}Kali Linux · Arquitectura GB206 · Open Kernel Modules${RESET}\n"

sleep 1

# ── PASO 0: Verificar modo UEFI ──────────────────────────────
header "PASO 0 · Verificar modo UEFI"
if [ -d /sys/firmware/efi ]; then
  ok "Sistema arrancado en modo UEFI. Correcto."
else
  warn "Sistema en modo LEGACY/CSM. La RTX 5060 puede tener problemas."
  warn "Entra en la BIOS y activa el modo UEFI antes de continuar."
  warn "NVIDIA tiene una herramienta de firmware para la 5060 con BIOS legacy."
  echo -e "\n  ${OD}¿Continuar de todas formas? (s/N):${RESET} "
  read -r resp
  [[ "$resp" =~ ^[sS]$ ]] || err "Abortado. Activa UEFI primero."
fi

# ── PASO 1: Verificar kernel ─────────────────────────────────
header "PASO 1 · Verificar versión del kernel"
KERNEL=$(uname -r)
KERNEL_MAJ=$(uname -r | cut -d. -f1)
KERNEL_MIN=$(uname -r | cut -d. -f2)
log "Kernel detectado: ${OG}$KERNEL${RESET}"

if [ "$KERNEL_MAJ" -lt 6 ] || ([ "$KERNEL_MAJ" -eq 6 ] && [ "$KERNEL_MIN" -lt 11 ]); then
  warn "Kernel $KERNEL es demasiado antiguo para la RTX 5060."
  warn "Instalando kernel 6.11+ automáticamente..."
  apt update -qq
  apt install -y linux-image-amd64 linux-headers-amd64
  ok "Kernel actualizado. Necesitarás reiniciar al terminar."
  NEED_REBOOT=1
else
  ok "Kernel $KERNEL compatible con RTX 5060."
fi

# ── PASO 2: Limpiar drivers anteriores ──────────────────────
header "PASO 2 · Limpiar drivers NVIDIA anteriores"
log "Purgando todos los paquetes nvidia existentes..."

# Parar display manager primero
DM_RUNNING=""
for dm in gdm3 lightdm sddm; do
  if systemctl is-active --quiet "$dm" 2>/dev/null; then
    DM_RUNNING="$dm"
    log "Deteniendo display manager: $dm"
    systemctl stop "$dm" || true
    break
  fi
done

# Blacklist nouveau
log "Bloqueando driver nouveau (conflicto con NVIDIA)..."
cat > /etc/modprobe.d/ghost-nouveau-blacklist.conf << 'BLACKLIST'
blacklist nouveau
blacklist lbm-nouveau
options nouveau modeset=0
alias nouveau off
alias lbm-nouveau off
BLACKLIST
ok "nouveau bloqueado."

# Purgar nvidia
apt-get purge -y "nvidia*" "libnvidia*" "cuda*" 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true
ok "Drivers anteriores eliminados."

# ── PASO 3: Instalar dependencias ───────────────────────────
header "PASO 3 · Instalar dependencias y headers"
apt update
apt install -y \
  linux-headers-$(uname -r) \
  build-essential \
  dkms \
  pkg-config \
  libglvnd-dev \
  libglvnd0 \
  libgl1 \
  gcc \
  make
ok "Dependencias instaladas."

# ── PASO 4: Añadir repositorio NVIDIA ───────────────────────
header "PASO 4 · Añadir repositorio NVIDIA para Debian/Kali"
log "Configurando repositorio contrib y non-free..."

# Kali usa repositorios Debian base
if ! grep -q "contrib non-free" /etc/apt/sources.list 2>/dev/null; then
  # Añadir non-free al sources si no está
  CURRENT_REPO=$(grep "^deb.*kali-rolling\|^deb.*kali" /etc/apt/sources.list | head -1 || echo "")
  if [ -n "$CURRENT_REPO" ]; then
    # Añadir contrib non-free non-free-firmware
    sed -i 's/kali-rolling$/kali-rolling contrib non-free non-free-firmware/' /etc/apt/sources.list
    ok "Repositorios contrib non-free añadidos a Kali."
  fi
fi
apt update -qq
ok "Repositorios actualizados."

# ── PASO 5: Instalar driver NVIDIA-OPEN ─────────────────────
header "PASO 5 · Instalar nvidia-open-dkms (Blackwell compatible)"
log "La RTX 5060 REQUIERE el driver -open (módulos open source del kernel)"
log "El driver propietario clásico NO es compatible con Blackwell."
log "Instalando nvidia-open-dkms + nvidia-driver..."

# Intentar desde repos primero
if apt-cache show nvidia-open-dkms 2>/dev/null | grep -q "570\|575\|580"; then
  apt install -y nvidia-open-dkms nvidia-driver
  ok "Driver nvidia-open-dkms instalado desde repositorio."
else
  warn "Versión 570+ no disponible en repo. Instalando desde nvidia-driver (open)..."
  # En Kali/Debian los paquetes se llaman diferente
  apt install -y nvidia-driver nvidia-kernel-open-dkms || {
    warn "Intentando método alternativo..."
    apt install -y nvidia-kernel-dkms nvidia-driver
  }
fi

# ── PASO 6: Configurar GRUB ──────────────────────────────────
header "PASO 6 · Configurar GRUB para RTX 5060"
log "Añadiendo parámetros de kernel necesarios..."

GRUB_FILE="/etc/default/grub"
CURRENT_CMDLINE=$(grep "^GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" | cut -d'"' -f2)

# Parámetros necesarios para RTX 5060 Blackwell
NEEDED_PARAMS="nvidia-drm.modeset=1 nvidia.NVreg_OpenRmEnableUnsupportedGpus=1"

NEW_CMDLINE="$CURRENT_CMDLINE"
for PARAM in $NEEDED_PARAMS; do
  if ! echo "$CURRENT_CMDLINE" | grep -q "$PARAM"; then
    NEW_CMDLINE="$NEW_CMDLINE $PARAM"
    log "Añadiendo parámetro: ${OG}$PARAM${RESET}"
  else
    ok "Parámetro ya presente: $PARAM"
  fi
done

# Actualizar GRUB
sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"$NEW_CMDLINE\"|" "$GRUB_FILE"
update-grub
ok "GRUB actualizado."

# ── PASO 7: Regenerar initramfs ──────────────────────────────
header "PASO 7 · Regenerar initramfs"
log "Actualizando initramfs con módulos NVIDIA open..."
update-initramfs -u -k all
ok "initramfs regenerado."

# ── PASO 8: Configurar módulos ───────────────────────────────
header "PASO 8 · Configurar módulos NVIDIA"
cat > /etc/modprobe.d/ghost-nvidia.conf << 'NVIDIA_CONF'
# GHOST EYES — Configuración NVIDIA RTX 5060 Blackwell
options nvidia-drm modeset=1
options nvidia NVreg_OpenRmEnableUnsupportedGpus=1
options nvidia NVreg_PreserveVideoMemoryAllocations=1
NVIDIA_CONF
ok "Módulos configurados."

# Habilitar servicios NVIDIA
for svc in nvidia-persistenced nvidia-hibernate nvidia-resume nvidia-suspend; do
  systemctl enable "$svc" 2>/dev/null && ok "Servicio habilitado: $svc" || true
done

# ── PASO 9: Reiniciar display manager ───────────────────────
header "PASO 9 · Estado final"
echo -e "  ${OD}PCI ID RTX 5060: ${OG}10de:2d05 (GB206)${RESET}"
echo -e "  ${OD}Driver mínimo  : ${OG}570.169 (-open modules)${RESET}"
echo -e "  ${OD}Kernel mínimo  : ${OG}6.11+ (recomendado 6.14+)${RESET}"
echo ""

if [ "${NEED_REBOOT}" = "1" ]; then
  warn "Se instaló un nuevo kernel. DEBES reiniciar antes de que funcione."
fi

echo -e "${O}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}${BOLD}INSTALACIÓN COMPLETADA${RESET}                               ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${OD}1.${RESET} Reinicia el sistema                                ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}2.${RESET} Verifica con: ${OG}nvidia-smi${RESET}                          ${O}║${RESET}"
echo -e "${O}║${RESET}  ${OD}3.${RESET} Si pantalla negra: arranca TTY (Ctrl+Alt+F3)      ${O}║${RESET}"
echo -e "${O}║${RESET}     y ejecuta: ${OG}sudo ghost-nvidia --rescue${RESET}              ${O}║${RESET}"
echo -e "${O}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
log "¿Reiniciar ahora? (s/N): "
read -r resp
if [[ "$resp" =~ ^[sS]$ ]]; then
  log "Reiniciando..."
  reboot
fi
