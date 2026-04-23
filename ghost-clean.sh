#!/bin/bash
# ghost-clean — GHOST EYES PROJECT
# Limpieza visual del sistema: caché, logs, archivos temporales
# Uso: ghost-clean [--deep] [--logs] [--cache] [--dry-run]

O="\033[38;5;166m"; OD="\033[38;5;130m"; OG="\033[38;5;208m"
GR="\033[38;5;64m"; R="\033[38;5;160m"; Y="\033[38;5;136m"
GREY="\033[38;5;238m"; W="\033[38;5;255m"; RESET="\033[0m"; BOLD="\033[1m"

DRY=0
DEEP=0
DO_LOGS=0
DO_CACHE=0
DO_ALL=1

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --deep)    DEEP=1 ;;
    --logs)    DO_LOGS=1; DO_ALL=0 ;;
    --cache)   DO_CACHE=1; DO_ALL=0 ;;
    --help|-h)
      echo -e "${O}ghost-clean${RESET} — Limpiador visual del sistema"
      echo ""
      echo -e "  ${OD}Uso:${RESET} ghost-clean [opciones]"
      echo -e "  ${OD}--dry-run${RESET}  Solo muestra qué haría, sin borrar nada"
      echo -e "  ${OD}--deep${RESET}     Limpieza profunda (thumbnails, Python cache, etc)"
      echo -e "  ${OD}--logs${RESET}     Solo limpiar logs"
      echo -e "  ${OD}--cache${RESET}    Solo limpiar caché"
      echo ""
      exit 0
      ;;
  esac
done

# ── Funciones ─────────────────────────────────────────────────

log()    { echo -e "${O}[ghost-clean]${RESET} $*"; }
ok()     { echo -e "  ${GR}✓${RESET} $*"; }
warn()   { echo -e "  ${Y}⚠${RESET} $*"; }
skip()   { echo -e "  ${GREY}·${RESET} $*"; }

TOTAL_FREED=0  # bytes

# Obtener tamaño de un path en bytes
size_of() {
  local path="$1"
  if [ -e "$path" ]; then
    du -sb "$path" 2>/dev/null | awk '{print $1}' || echo 0
  else
    echo 0
  fi
}

# Formato legible
fmt_size() {
  local bytes="$1"
  if   [ "$bytes" -ge 1073741824 ]; then awk "BEGIN{printf \"%.2f GB\", $bytes/1073741824}"
  elif [ "$bytes" -ge 1048576 ];    then awk "BEGIN{printf \"%.1f MB\", $bytes/1048576}"
  elif [ "$bytes" -ge 1024 ];       then awk "BEGIN{printf \"%.0f KB\", $bytes/1024}"
  else echo "${bytes} B"
  fi
}

# Barra de progreso simple
progress() {
  local label="$1" idx="$2" total="$3"
  local pct=$(( idx * 100 / total ))
  local filled=$(( idx * 20 / total ))
  local bar="${OG}$(printf '█%.0s' $(seq 1 $filled 2>/dev/null || echo ''))${GREY}$(printf '░%.0s' $(seq 1 $(( 20 - filled )) 2>/dev/null || echo ''))${RESET}"
  printf "\r  ${bar} ${GREY}%3d%%${RESET}  %s" "$pct" "$label"
}

# Limpiar un directorio/archivo con animación
clean_item() {
  local desc="$1"
  local path="$2"
  local sudo_prefix="${3:-}"

  if [ ! -e "$path" ]; then
    skip "$desc — no existe"
    return
  fi

  local sz
  sz=$(size_of "$path")

  if [ "$DRY" -eq 1 ]; then
    warn "[DRY] $desc — liberaría $(fmt_size $sz)"
    return
  fi

  # Mostrar antes
  printf "  ${OD}▸${RESET} %-40s" "$desc"

  if $sudo_prefix rm -rf "$path" 2>/dev/null; then
    local freed="$sz"
    TOTAL_FREED=$(( TOTAL_FREED + freed ))
    echo -e "  ${GR}✓ $(fmt_size $freed)${RESET}"
  else
    echo -e "  ${Y}⚠ sin permiso${RESET}"
  fi
}

# ── BANNER ────────────────────────────────────────────────────

clear
echo -e "${O}"
cat << 'BANNER'
   ██████╗██╗     ███████╗ █████╗ ███╗   ██╗
  ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║
  ██║     ██║     █████╗  ███████║██╔██╗ ██║
  ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║
  ╚██████╗███████╗███████╗██║  ██║██║ ╚████║
   ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝
BANNER
echo -e "${RESET}"
echo -e "  ${OD}GHOST EYES · Limpiador visual del sistema${RESET}"
[ "$DRY" -eq 1 ] && echo -e "  ${Y}MODO DRY-RUN — no se borrará nada${RESET}"
echo ""

# Espacio libre antes
FREE_BEFORE=$(df / --output=avail -BK | tail -1 | tr -dK)

# ════════════════════════════════════════════════════════════
# 1. APT / DPKG CACHE
# ════════════════════════════════════════════════════════════

if [ "$DO_ALL" -eq 1 ] || [ "$DO_CACHE" -eq 1 ]; then
  echo -e "\n${O}── CACHÉ APT ────────────────────────────────${RESET}\n"

  APT_CACHE_SIZE=$(size_of /var/cache/apt/archives)
  echo -e "  ${OD}Caché actual: ${OG}$(fmt_size $APT_CACHE_SIZE)${RESET}\n"

  if [ "$DRY" -eq 0 ]; then
    printf "  ${OD}▸${RESET} %-40s" "Limpiando caché APT..."
    if apt-get clean -qq 2>/dev/null; then
      echo -e "  ${GR}✓${RESET}"
      TOTAL_FREED=$(( TOTAL_FREED + APT_CACHE_SIZE ))
    else
      echo -e "  ${Y}⚠ necesita sudo${RESET}"
    fi

    printf "  ${OD}▸${RESET} %-40s" "Eliminando paquetes obsoletos..."
    if apt-get autoremove -y -qq 2>/dev/null; then
      echo -e "  ${GR}✓${RESET}"
    else
      echo -e "  ${Y}⚠ necesita sudo${RESET}"
    fi

    printf "  ${OD}▸${RESET} %-40s" "Limpiando listas desactualizadas..."
    if apt-get autoclean -qq 2>/dev/null; then
      echo -e "  ${GR}✓${RESET}"
    fi
  else
    warn "[DRY] apt clean — liberaría $(fmt_size $APT_CACHE_SIZE)"
    warn "[DRY] apt autoremove"
    warn "[DRY] apt autoclean"
  fi
fi

# ════════════════════════════════════════════════════════════
# 2. LOGS DEL SISTEMA
# ════════════════════════════════════════════════════════════

if [ "$DO_ALL" -eq 1 ] || [ "$DO_LOGS" -eq 1 ]; then
  echo -e "\n${O}── LOGS DEL SISTEMA ─────────────────────────${RESET}\n"

  # Journal systemd
  JOURNAL_SIZE=$(journalctl --disk-usage 2>/dev/null | grep -oP '[\d.]+[KMGT]?B' | head -1 || echo "0B")
  echo -e "  ${OD}Journal systemd: ${OG}${JOURNAL_SIZE}${RESET}"

  if [ "$DRY" -eq 0 ]; then
    printf "  ${OD}▸${RESET} %-40s" "Compactando journal (mantiene 50MB)..."
    if journalctl --vacuum-size=50M -q 2>/dev/null; then
      echo -e "  ${GR}✓${RESET}"
    else
      echo -e "  ${GREY}· sin systemd o sin permiso${RESET}"
    fi
  else
    warn "[DRY] journalctl --vacuum-size=50M"
  fi

  # Logs rotados
  for logdir in /var/log; do
    ROTATED=$(find "$logdir" -name "*.gz" -o -name "*.1" -o -name "*.old" 2>/dev/null | wc -l)
    if [ "$ROTATED" -gt 0 ]; then
      SZ=$(find "$logdir" \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) \
           -exec du -sb {} + 2>/dev/null | awk '{s+=$1}END{print s+0}')
      clean_item "Logs rotados en $logdir ($ROTATED archivos)" \
        "$logdir" "find $logdir \( -name '*.gz' -o -name '*.1' -o -name '*.old' \) -delete"

      if [ "$DRY" -eq 0 ]; then
        find "$logdir" \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) \
          -delete 2>/dev/null || true
        TOTAL_FREED=$(( TOTAL_FREED + SZ ))
        ok "Logs rotados eliminados — $(fmt_size $SZ)"
      else
        warn "[DRY] find $logdir -name '*.gz' ... — liberaría $(fmt_size $SZ)"
      fi
    fi
  done

  # ghost-nvidia-kali log si existe
  if [ -f /var/log/ghost-nvidia-kali.log ]; then
    clean_item "Log ghost-nvidia-kali" /var/log/ghost-nvidia-kali.log
  fi
fi

# ════════════════════════════════════════════════════════════
# 3. ARCHIVOS TEMPORALES
# ════════════════════════════════════════════════════════════

if [ "$DO_ALL" -eq 1 ] || [ "$DO_CACHE" -eq 1 ]; then
  echo -e "\n${O}── ARCHIVOS TEMPORALES ──────────────────────${RESET}\n"

  clean_item "/tmp (archivos >1 día)"       "/tmp"
  clean_item "/var/tmp"                      "/var/tmp"
  clean_item "Caché de miniaturas"           "$HOME/.cache/thumbnails"
  clean_item "Caché de sesión"               "/tmp/.ghost-map-session"

  # Deep clean
  if [ "$DEEP" -eq 1 ]; then
    echo -e "\n${O}── LIMPIEZA PROFUNDA ─────────────────────────${RESET}\n"

    clean_item "Python __pycache__"  "" # especial
    if [ "$DRY" -eq 0 ]; then
      SZ=$(find / -name "__pycache__" -type d 2>/dev/null | \
           xargs du -sb 2>/dev/null | awk '{s+=$1}END{print s+0}')
      find / -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
      find / -name "*.pyc" -delete 2>/dev/null || true
      TOTAL_FREED=$(( TOTAL_FREED + SZ ))
      ok "Python __pycache__ eliminados — $(fmt_size $SZ)"
    else
      warn "[DRY] find / -name '__pycache__' ..."
    fi

    clean_item "Caché pip"           "$HOME/.cache/pip"
    clean_item "Caché npm"           "$HOME/.npm/_cacache"
    clean_item "Caché de crash"      "/var/crash"
    clean_item "Core dumps"          "/var/lib/systemd/coredump"
  fi
fi

# ════════════════════════════════════════════════════════════
# RESUMEN FINAL
# ════════════════════════════════════════════════════════════

FREE_AFTER=$(df / --output=avail -BK 2>/dev/null | tail -1 | tr -dK || echo "$FREE_BEFORE")
REAL_FREED=$(( (FREE_AFTER - FREE_BEFORE) * 1024 ))

echo ""
echo -e "${O}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${O}║${RESET}  ${OG}${BOLD}GHOST-CLEAN · RESUMEN${RESET}                               ${O}║${RESET}"
echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"

if [ "$DRY" -eq 1 ]; then
  echo -e "${O}║${RESET}  ${Y}MODO DRY-RUN — ningún archivo fue eliminado${RESET}         ${O}║${RESET}"
else
  FREED_STR=$(fmt_size $TOTAL_FREED)
  echo -e "${O}║${RESET}  ${GR}Espacio estimado liberado : ${OG}${FREED_STR}${RESET}"  \
       "               ${O}║${RESET}"
  echo -e "${O}║${RESET}  ${OD}Espacio libre ahora       : ${OG}$(fmt_size $((FREE_AFTER * 1024)))${RESET}" \
       "               ${O}║${RESET}"
fi

echo -e "${O}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${O}║${RESET}  ${GREY}ghost-clean --deep   para limpieza más profunda${RESET}     ${O}║${RESET}"
echo -e "${O}║${RESET}  ${GREY}ghost-clean --dry-run para ver sin borrar${RESET}           ${O}║${RESET}"
echo -e "${O}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
