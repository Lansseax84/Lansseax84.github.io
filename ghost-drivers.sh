#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  ghost-drivers — GHOST EYES PROJECT                         ║
# ║  Instalador universal de drivers GPU para Kali Linux        ║
# ║  Soporta: NVIDIA (todas series), AMD, Intel                 ║
# ╚══════════════════════════════════════════════════════════════╝

set -e
O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
G="\033[38;5;238m"; R="\033[38;5;160m"; GR="\033[38;5;64m"; RESET="\033[0m"; BOLD="\033[1m"

log()    { echo -e "${O}[ghost-drivers]${RESET} $*"; }
ok()     { echo -e "${GR}[  OK  ]${RESET} $*"; }
warn()   { echo -e "${OD}[ WARN ]${RESET} $*"; }
err()    { echo -e "${R}[ FAIL ]${RESET} $*"; exit 1; }
header() { echo -e "\n${O}══════════════════════════════════════════${RESET}\n  ${OG}${BOLD}$*${RESET}\n${O}══════════════════════════════════════════${RESET}\n"; }

[ "$EUID" -ne 0 ] && err "Ejecuta como root: sudo bash ghost-drivers.sh"

clear
echo -e "${O}"
cat << 'EOF'
  ██████╗ ██████╗ ██╗██╗   ██╗███████╗██████╗ ███████╗
  ██╔══██╗██╔══██╗██║██║   ██║██╔════╝██╔══██╗██╔════╝
  ██║  ██║██████╔╝██║██║   ██║█████╗  ██████╔╝███████╗
  ██║  ██║██╔══██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║
  ██████╔╝██║  ██║██║ ╚████╔╝ ███████╗██║  ██║███████║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝
EOF
echo -e "${RESET}"
echo -e "  ${OD}GHOST EYES · Instalador universal de drivers GPU${RESET}"
echo -e "  ${G}NVIDIA · AMD · Intel · Kali Linux Rolling${RESET}\n"
sleep 1

# ── DETECCIÓN AUTOMÁTICA DE GPU ──────────────────────────────
header "DETECCIÓN DE HARDWARE"

GPU_INFO=$(lspci | grep -i "vga\|3d\|display" 2>/dev/null || echo "")
log "GPUs detectadas:\n${G}${GPU_INFO}${RESET}\n"

NVIDIA_CARD=$(echo "$GPU_INFO" | grep -i nvidia | head -1)
AMD_CARD=$(echo "$GPU_INFO"    | grep -i "amd\|radeon\|advanced micro" | head -1)
INTEL_CARD=$(echo "$GPU_INFO"  | grep -i intel | head -1)

# Detectar serie NVIDIA para saber qué driver usar
NVIDIA_SERIES=""
if [ -n "$NVIDIA_CARD" ]; then
  if echo "$NVIDIA_CARD" | grep -qiE "RTX 50|GB20|GB21"; then
    NVIDIA_SERIES="blackwell"
  elif echo "$NVIDIA_CARD" | grep -qiE "RTX 40|AD10"; then
    NVIDIA_SERIES="ada"
  elif echo "$NVIDIA_CARD" | grep -qiE "RTX 30|GA10"; then
    NVIDIA_SERIES="ampere"
  elif echo "$NVIDIA_CARD" | grep -qiE "RTX 20|GTX 16|TU1"; then
    NVIDIA_SERIES="turing"
  elif echo "$NVIDIA_CARD" | grep -qiE "GTX 10|GP1"; then
    NVIDIA_SERIES="pascal"
  elif echo "$NVIDIA_CARD" | grep -qiE "GTX 9|GTX 8|GM"; then
    NVIDIA_SERIES="maxwell"
  else
    NVIDIA_SERIES="legacy"
  fi
fi

echo -e "  ${OD}NVIDIA : ${OG}${NVIDIA_CARD:-No detectada}${RESET}"
[ -n "$NVIDIA_SERIES" ] && echo -e "  ${OD}Serie  : ${OG}${NVIDIA_SERIES}${RESET}"
echo -e "  ${OD}AMD    : ${OG}${AMD_CARD:-No detectada}${RESET}"
echo -e "  ${OD}Intel  : ${OG}${INTEL_CARD:-No detectada}${RESET}\n"

# Confirmación
echo -e "  ${OD}¿Instalar drivers automáticamente? (s/N):${RESET} "
read -r resp
[[ "$resp" =~ ^[sS]$ ]] || { log "Abortado."; exit 0; }

# ── LIMPIEZA PREVIA ───────────────────────────────────────────
header "LIMPIEZA DE DRIVERS ANTERIORES"

# Parar display manager
for dm in gdm3 lightdm sddm; do
  systemctl is-active --quiet "$dm" 2>/dev/null && { log "Deteniendo $dm..."; systemctl stop "$dm" || true; }
done

apt-get purge -y "nvidia*" "libnvidia*" 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true
ok "Limpieza completada."

# ── DEPENDENCIAS COMUNES ──────────────────────────────────────
header "DEPENDENCIAS BASE"
apt update -qq
apt install -y linux-headers-$(uname -r) build-essential dkms pkg-config \
               firmware-linux firmware-linux-nonfree 2>/dev/null || true
ok "Dependencias base instaladas."

# ── INSTALAR SEGÚN GPU ────────────────────────────────────────

install_nvidia() {
  header "NVIDIA · Instalando drivers"

  # Bloquear nouveau
  cat > /etc/modprobe.d/ghost-nouveau-blacklist.conf << 'BL'
blacklist nouveau
options nouveau modeset=0
BL
  ok "nouveau bloqueado."

  case "$NVIDIA_SERIES" in
    blackwell)
      log "RTX 5060/5070/5080/5090 (Blackwell) — Requiere nvidia-open-dkms 570.169+"
      # Añadir non-free si no está
      sed -i 's/kali-rolling$/kali-rolling contrib non-free non-free-firmware/' /etc/apt/sources.list 2>/dev/null || true
      apt update -qq
      apt install -y nvidia-open-dkms nvidia-driver || \
      apt install -y nvidia-kernel-open-dkms nvidia-driver
      ;;
    ada|ampere)
      log "RTX 30/40 (Ampere/Ada) — Driver 535+ propietario o open"
      apt install -y nvidia-driver nvidia-kernel-dkms
      ;;
    turing)
      log "RTX 20 / GTX 16 (Turing) — Driver 470-535"
      apt install -y nvidia-driver nvidia-kernel-dkms
      ;;
    pascal)
      log "GTX 10 (Pascal) — Driver 470"
      apt install -y nvidia-driver nvidia-kernel-dkms
      ;;
    maxwell)
      log "GTX 9/8 (Maxwell) — Driver 390 legacy"
      apt install -y nvidia-legacy-390xx-driver nvidia-legacy-390xx-kernel-dkms 2>/dev/null || \
      apt install -y nvidia-driver
      ;;
    legacy|*)
      log "GPU NVIDIA antigua — instalando driver recomendado"
      apt install -y nvidia-driver
      ;;
  esac

  # Parámetros GRUB para todas las series
  GRUB_FILE="/etc/default/grub"
  CMDLINE=$(grep "^GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" | cut -d'"' -f2)
  for PARAM in "nvidia-drm.modeset=1"; do
    echo "$CMDLINE" | grep -q "$PARAM" || CMDLINE="$CMDLINE $PARAM"
  done
  # Solo para Blackwell añadir parámetro extra
  if [ "$NVIDIA_SERIES" = "blackwell" ]; then
    echo "$CMDLINE" | grep -q "NVreg_OpenRmEnableUnsupportedGpus" || \
      CMDLINE="$CMDLINE nvidia.NVreg_OpenRmEnableUnsupportedGpus=1"
  fi
  sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"$CMDLINE\"|" "$GRUB_FILE"
  update-grub
  update-initramfs -u -k all
  ok "NVIDIA instalada. Serie: $NVIDIA_SERIES"
}

install_amd() {
  header "AMD · Instalando drivers"
  log "AMD usa el driver amdgpu incluido en el kernel — configurando firmware y mesa..."

  apt install -y \
    firmware-amd-graphics \
    mesa-vulkan-drivers \
    mesa-va-drivers \
    mesa-vdpau-drivers \
    libgl1-mesa-dri \
    xserver-xorg-video-amdgpu 2>/dev/null || true

  # Activar amdgpu en GRUB si no está
  GRUB_FILE="/etc/default/grub"
  CMDLINE=$(grep "^GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_FILE" | cut -d'"' -f2)
  echo "$CMDLINE" | grep -q "amdgpu.dc=1" || CMDLINE="$CMDLINE amdgpu.dc=1"
  sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"$CMDLINE\"|" "$GRUB_FILE"
  update-grub
  ok "AMD instalada — driver amdgpu del kernel con firmware actualizado."
}

install_intel() {
  header "Intel · Instalando drivers"
  log "Intel integrada — instalando mesa, i915, va-api y vulkan..."

  apt install -y \
    intel-media-va-driver \
    intel-media-va-driver-non-free \
    mesa-vulkan-drivers \
    mesa-va-drivers \
    libgl1-mesa-dri \
    xserver-xorg-video-intel 2>/dev/null || true

  ok "Intel instalada — i915 + Mesa + VA-API."
}

# ── EJECUTAR SEGÚN HARDWARE DETECTADO ────────────────────────
[ -n "$NVIDIA_CARD" ] && install_nvidia
[ -n "$AMD_CARD"    ] && install_amd
[ -n "$INTEL_CARD"  ] && install_intel

if [ -z "$NVIDIA_CARD" ] && [ -z "$AMD_CARD" ] && [ -z "$INTEL_CARD" ]; then
  warn "No se detectó GPU reconocida. Instalando drivers genéricos..."
  apt install -y mesa-utils xserver-xorg-video-all 2>/dev/null || true
fi

# ── RESUMEN FINAL ─────────────────────────────────────────────
header "INSTALACIÓN COMPLETADA"
echo -e "  ${OD}Verificación rápida:${RESET}"
[ -n "$NVIDIA_CARD" ] && echo -e "  ${G}✓ NVIDIA${RESET} — verifica con: nvidia-smi"
[ -n "$AMD_CARD"    ] && echo -e "  ${G}✓ AMD${RESET}    — verifica con: glxinfo | grep renderer"
[ -n "$INTEL_CARD"  ] && echo -e "  ${G}✓ Intel${RESET}  — verifica con: glxinfo | grep renderer"
echo ""
echo -e "  ${OD}¿Reiniciar ahora? (s/N):${RESET} "
read -r resp
[[ "$resp" =~ ^[sS]$ ]] && reboot
