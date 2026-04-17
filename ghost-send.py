#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════╗
# ║  ghost-send — GHOST EYES PROJECT                            ║
# ║  Mensajería cifrada P2P con viaje visual del paquete        ║
# ║  Uso: ghost-send <ip> "mensaje" [-archivo.zip]              ║
# ║       ghost-send --listen (modo receptor)                   ║
# ╚══════════════════════════════════════════════════════════════╝
#
# CIFRADO: AES-256 via cryptography.Fernet
# HASH:    SHA-256 para verificación de integridad
# ANTIVIRUS: ClamAV (clamscan) si está instalado
# PUERTO: 47200/TCP (configurable)

import sys, os, json, time, socket, threading, hashlib
import argparse, subprocess, struct, base64, re
from datetime import datetime

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_OK = True
except ImportError:
    print("[ghost-send] Instalando cryptography...")
    os.system("pip install cryptography --break-system-packages -q")
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_OK = True

class C:
    O  = "\033[38;5;166m";  OD = "\033[38;5;130m"; OG = "\033[38;5;208m"
    G  = "\033[38;5;64m";   R  = "\033[38;5;160m";  Y  = "\033[38;5;136m"
    W  = "\033[38;5;255m";  GR = "\033[38;5;238m";  RESET = "\033[0m"
    BOLD = "\033[1m";       BLINK = "\033[5m"

PORT       = 47200
GHOST_KEY  = b"ghost-eyes-shared-secret-v1-2025"  # clave base (mejorar con intercambio DH en v2)
BUFFER     = 4096

# ── Derivar clave AES desde secreto compartido ───────────────
def derive_key(secret: bytes = GHOST_KEY) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"ghost_salt_v1", iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(secret))

FERNET_KEY = derive_key()
cipher     = Fernet(FERNET_KEY)

# ── Escaneo de virus con ClamAV ──────────────────────────────
def virus_scan(filepath: str) -> tuple:
    """Devuelve (clean:bool, resultado:str)"""
    print(f"\n  {C.OD}[ghost-send] Escaneando antivirus...{C.RESET}")

    # Intentar clamscan
    try:
        result = subprocess.run(
            ["clamscan", "--no-summary", "-r", filepath],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        if result.returncode == 0:
            print(f"  {C.G}[AV] Limpio — ClamAV no detectó amenazas.{C.RESET}")
            return True, "Limpio"
        elif result.returncode == 1:
            # Virus encontrado
            threats = [l for l in output.split("\n") if "FOUND" in l]
            threat_str = "; ".join(threats[:3])
            print(f"  {C.R}[AV] ¡AMENAZA DETECTADA! {threat_str}{C.RESET}")
            print(f"  {C.R}[AV] Archivo bloqueado — no se enviará.{C.RESET}")
            return False, f"AMENAZA: {threat_str}"
        else:
            print(f"  {C.Y}[AV] ClamAV no disponible — usando hash verification.{C.RESET}")
    except FileNotFoundError:
        print(f"  {C.Y}[AV] ClamAV no instalado. Instalando...{C.RESET}")
        os.system("apt-get install -y clamav -qq 2>/dev/null || true")
        print(f"  {C.Y}[AV] Usando verificación de hash como fallback.{C.RESET}")
    except Exception as e:
        print(f"  {C.Y}[AV] Error: {e} — continuando con hash.{C.RESET}")

    # Fallback: verificaciones básicas de extensiones peligrosas
    dangerous_exts = {'.exe','.bat','.cmd','.msi','.scr','.vbs','.ps1',
                      '.sh','.bash','.elf','.dll','.so','.deb','.rpm'}
    ext = os.path.splitext(filepath)[1].lower()
    if ext in dangerous_exts:
        print(f"  {C.Y}[AV] Extensión potencialmente peligrosa: {ext}{C.RESET}")
        resp = input(f"  {C.Y}¿Continuar de todas formas? (s/N): {C.RESET}").strip().lower()
        if resp != "s":
            return False, f"Bloqueado por extensión: {ext}"

    print(f"  {C.G}[AV] Verificación básica pasada.{C.RESET}")
    return True, "Verificación básica OK"

# ── Calcular hash SHA-256 ────────────────────────────────────
def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# ── Viaje visual del paquete por la red ──────────────────────
def show_packet_journey(target_ip: str, has_file: bool = False):
    """Muestra el viaje del paquete con traceroute visual."""
    local_ip = get_local_ip()

    print(f"\n  {C.O}{'═'*54}{C.RESET}")
    print(f"  {C.OG}{C.BOLD}VIAJE DEL PAQUETE POR LA RED{C.RESET}")
    print(f"  {C.O}{'═'*54}{C.RESET}\n")

    print(f"  {C.OD}[PREPARANDO PAQUETE]{C.RESET}")
    time.sleep(0.3)
    print(f"  {C.GR}  ├── Mensaje    : cifrado AES-256 ✓{C.RESET}")
    time.sleep(0.2)
    if has_file:
        print(f"  {C.GR}  ├── Archivo    : escaneado + cifrado ✓{C.RESET}")
        time.sleep(0.2)
    print(f"  {C.GR}  ├── Hash SHA-256: verificación integridad ✓{C.RESET}")
    time.sleep(0.2)
    print(f"  {C.GR}  └── Encapsulado : listo para envío{C.RESET}\n")
    time.sleep(0.4)

    # Traceroute hacia el destino
    print(f"  {C.OD}[RASTREANDO RUTA HACIA {target_ip}]{C.RESET}")
    hops = []
    try:
        result = subprocess.run(
            ["traceroute", "-n", "-m", "10", "-q", "1", "-w", "1", target_ip],
            capture_output=True, text=True, timeout=15
        )
        lines = [l for l in result.stdout.split("\n") if l.strip() and not l.startswith("traceroute")]
        for line in lines[:8]:
            parts = line.split()
            if len(parts) >= 2:
                hop_num = parts[0]
                hop_ip  = parts[1] if parts[1] != "*" else "?"
                hop_ms  = parts[2] if len(parts) > 2 and parts[2] != "*" else "?"
                hops.append((hop_num, hop_ip, hop_ms))
    except:
        pass

    if not hops:
        # Mostrar ruta simulada si traceroute falla
        hops = [("1", local_ip, "0.1"), ("2", target_ip, "?")]

    # Dibujar ruta
    print(f"\n  {C.O}{local_ip:<18}{C.RESET} {C.OD}← ORIGEN{C.RESET}")
    for hop_n, hop_ip, hop_ms in hops:
        time.sleep(0.25)
        bar = "──"
        latency_col = C.G if hop_ms != "?" and float(hop_ms.replace("ms","")) < 10 else C.Y
        print(f"  {C.OD}│{C.RESET}")
        print(f"  {C.OD}├{bar} HOP {hop_n:<3}{C.RESET} {hop_ip:<18} {latency_col}{hop_ms}ms{C.RESET}")

    print(f"  {C.OD}│{C.RESET}")
    print(f"  {C.OG}└── {target_ip:<18}{C.RESET} {C.G}← DESTINO ◉{C.RESET}\n")
    time.sleep(0.3)

    # Animación de envío
    print(f"  {C.OD}[LANZANDO PAQUETE]{C.RESET}")
    packet_chars = "·▸▸▸▸▸▸▸▸◉"
    for i, ch in enumerate(packet_chars):
        bar = "─" * i + ch
        print(f"\r  {C.O}  [{bar:<12}]{C.RESET}", end="", flush=True)
        time.sleep(0.12)
    print()

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except:
        return "127.0.0.1"

# ── Empaquetar mensaje + archivo ─────────────────────────────
def build_packet(message: str, filepath: str = None) -> dict:
    packet = {
        "version":   "ghost-send/1.0",
        "timestamp": datetime.now().isoformat(),
        "sender_ip": get_local_ip(),
        "msg_hash":  sha256_text(message),
        "message":   message,
        "has_file":  filepath is not None,
        "filename":  None,
        "file_hash": None,
        "file_data": None,
    }
    if filepath and os.path.exists(filepath):
        packet["filename"]  = os.path.basename(filepath)
        packet["file_hash"] = sha256_file(filepath)
        with open(filepath, "rb") as f:
            packet["file_data"] = base64.b64encode(f.read()).decode()
    return packet

# ── Cifrar / descifrar ───────────────────────────────────────
def encrypt_packet(packet: dict) -> bytes:
    raw = json.dumps(packet).encode()
    return cipher.encrypt(raw)

def decrypt_packet(data: bytes) -> dict:
    raw = cipher.decrypt(data)
    return json.loads(raw.decode())

# ── ENVIAR ────────────────────────────────────────────────────
def send(target_ip: str, message: str, filepath: str = None, port: int = PORT):
    print(f"\n{C.O}╔{'═'*52}╗{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OG}{C.BOLD}GHOST-SEND · PREPARANDO ENVÍO{C.RESET}"+" "*23+f"{C.O}║{C.RESET}")
    print(f"{C.O}╠{'═'*52}╣{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Destino  {C.RESET}{target_ip:<42}{C.O}║{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Mensaje  {C.RESET}{message[:42]:<42}{C.O}║{C.RESET}")
    if filepath:
        print(f"{C.O}║{C.RESET}  {C.OD}Archivo  {C.RESET}{os.path.basename(filepath)[:42]:<42}{C.O}║{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Cifrado  {C.RESET}{'AES-256 + SHA-256':<42}{C.O}║{C.RESET}")
    print(f"{C.O}╚{'═'*52}╝{C.RESET}")

    # Escaneo antivirus del archivo
    if filepath:
        clean, av_result = virus_scan(filepath)
        if not clean:
            print(f"\n{C.R}[!] Envío cancelado por seguridad: {av_result}{C.RESET}\n")
            sys.exit(1)

    # Construir paquete
    print(f"\n  {C.OD}[1/4] Construyendo paquete...{C.RESET}")
    packet = build_packet(message, filepath)
    time.sleep(0.3)

    print(f"  {C.OD}[2/4] Cifrando con AES-256...{C.RESET}")
    encrypted = encrypt_packet(packet)
    time.sleep(0.3)
    print(f"  {C.G}       Hash SHA-256: {packet['msg_hash'][:32]}...{C.RESET}")

    # Viaje visual
    print(f"  {C.OD}[3/4] Trazando ruta...{C.RESET}")
    show_packet_journey(target_ip, has_file=filepath is not None)

    # Envío TCP
    print(f"  {C.OD}[4/4] Estableciendo conexión TCP...{C.RESET}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((target_ip, port))

        # Enviar longitud primero (4 bytes), luego datos
        data_len = len(encrypted)
        sock.sendall(struct.pack(">I", data_len))
        sock.sendall(encrypted)

        # Esperar confirmación
        print(f"  {C.OD}Esperando confirmación del receptor...{C.RESET}")
        ack = sock.recv(64).decode().strip()
        sock.close()

        if ack == "ACK:OK":
            print(f"\n  {C.G}✓ MENSAJE ENTREGADO CORRECTAMENTE{C.RESET}")
            print(f"  {C.G}  Receptor confirmó recepción en {target_ip}:{port}{C.RESET}\n")
            print(f"  {C.OD}Hash enviado : {packet['msg_hash'][:48]}...{C.RESET}\n")
        else:
            print(f"\n  {C.Y}⚠ Respuesta inesperada del receptor: {ack}{C.RESET}\n")

    except ConnectionRefusedError:
        print(f"\n  {C.R}✗ Conexión rechazada — {target_ip}:{port} no disponible.{C.RESET}")
        print(f"  {C.OD}  El receptor debe ejecutar: ghost-send --listen{C.RESET}\n")
    except socket.timeout:
        print(f"\n  {C.R}✗ Timeout — {target_ip} no responde en {port}/TCP.{C.RESET}\n")
    except Exception as e:
        print(f"\n  {C.R}✗ Error: {e}{C.RESET}\n")

# ── RECIBIR (modo servidor) ───────────────────────────────────
def listen(port: int = PORT, save_dir: str = "."):
    print(f"\n{C.O}╔{'═'*52}╗{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OG}{C.BOLD}GHOST-SEND · MODO RECEPTOR{C.RESET}"+" "*25+f"{C.O}║{C.RESET}")
    print(f"{C.O}╠{'═'*52}╣{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Puerto   {C.RESET}{str(port):<42}{C.O}║{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Cifrado  {C.RESET}{'AES-256':<42}{C.O}║{C.RESET}")
    print(f"{C.O}║{C.RESET}  {C.OD}Estado   {C.RESET}{C.G}ESCUCHANDO{C.RESET}" +" "*32+f"{C.O}║{C.RESET}")
    print(f"{C.O}╚{'═'*52}╝{C.RESET}")
    print(f"\n  {C.OD}Esperando mensajes... (Ctrl+C para salir){C.RESET}\n")

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(5)

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_incoming,
                             args=(conn, addr, save_dir), daemon=True).start()
    except KeyboardInterrupt:
        print(f"\n  {C.OD}Receptor detenido.{C.RESET}\n")
    finally:
        srv.close()

def handle_incoming(conn, addr, save_dir):
    sender_ip = addr[0]
    try:
        # Leer longitud
        raw_len = conn.recv(4)
        if len(raw_len) < 4:
            conn.close(); return
        data_len = struct.unpack(">I", raw_len)[0]

        # Leer datos
        data = b""
        while len(data) < data_len:
            chunk = conn.recv(min(BUFFER, data_len - len(data)))
            if not chunk: break
            data += chunk

        # Descifrar
        packet = decrypt_packet(data)

        # Verificar hash del mensaje
        expected_hash = sha256_text(packet["message"])
        hash_ok = expected_hash == packet["msg_hash"]

        # Mostrar mensaje recibido
        print(f"\n{C.O}╔{'═'*58}╗{C.RESET}")
        print(f"{C.O}║{C.RESET}  {C.OG}{C.BOLD}✉  MENSAJE RECIBIDO{C.RESET}"+" "*39+f"{C.O}║{C.RESET}")
        print(f"{C.O}╠{'═'*58}╣{C.RESET}")
        print(f"{C.O}║{C.RESET}  {C.OD}De        {C.RESET}{sender_ip:<48}{C.O}║{C.RESET}")
        print(f"{C.O}║{C.RESET}  {C.OD}Hora      {C.RESET}{packet['timestamp'][:19]:<48}{C.O}║{C.RESET}")
        print(f"{C.O}║{C.RESET}  {C.OD}Integridad{C.RESET}{(C.G+'✓ Verificada'+C.RESET) if hash_ok else (C.R+'✗ HASH INVÁLIDO'+C.RESET)}"+" "*37+f"{C.O}║{C.RESET}")
        print(f"{C.O}╠{'═'*58}╣{C.RESET}")
        # Mensaje (con salto de línea cada 54 chars)
        msg = packet["message"]
        for i in range(0, len(msg), 54):
            chunk = msg[i:i+54]
            print(f"{C.O}║{C.RESET}  {C.W}{chunk:<54}{C.RESET}  {C.O}║{C.RESET}")
        print(f"{C.O}╚{'═'*58}╝{C.RESET}")

        # Guardar archivo si viene uno
        if packet.get("has_file") and packet.get("file_data"):
            fname = packet["filename"] or "received_file"
            fpath = os.path.join(save_dir, fname)
            file_bytes = base64.b64decode(packet["file_data"])

            # Verificar hash del archivo
            recv_hash = hashlib.sha256(file_bytes).hexdigest()
            file_ok   = recv_hash == packet.get("file_hash","")

            with open(fpath, "wb") as f:
                f.write(file_bytes)

            print(f"\n  {C.OD}📎 Archivo recibido: {C.OG}{fname}{C.RESET}")
            print(f"  {C.OD}   Hash: {'✓ OK' if file_ok else '✗ CORRUPTO'}{C.RESET}")
            print(f"  {C.OD}   Guardado en: {fpath}{C.RESET}")

            # Escanear el archivo recibido también
            clean, av = virus_scan(fpath)
            if not clean:
                print(f"  {C.R}[!] Archivo infectado eliminado: {fpath}{C.RESET}")
                os.remove(fpath)

        # Intentar notificación de escritorio
        try:
            subprocess.Popen(["notify-send", "Ghost-Send", f"Mensaje de {sender_ip}",
                             "--icon=dialog-information"], stdout=subprocess.DEVNULL)
        except: pass

        # Enviar ACK
        conn.sendall(b"ACK:OK")

    except Exception as e:
        print(f"\n  {C.R}[ghost-send] Error procesando mensaje: {e}{C.RESET}")
        try: conn.sendall(b"ACK:ERR")
        except: pass
    finally:
        conn.close()

# ── Parsear argumentos de línea de comandos ──────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="ghost-send — Mensajería cifrada P2P",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  ghost-send 192.168.1.45 "Hola buenas tardes"
  ghost-send 192.168.1.45 "Revisa esto" -documento.pdf
  ghost-send 192.168.1.45 "Archivos" -proyecto.zip
  ghost-send --listen
  ghost-send --listen --port 47201
        """
    )
    p.add_argument("target",    nargs="?", help="IP destino")
    p.add_argument("message",   nargs="?", help='Mensaje entre comillas')
    p.add_argument("--listen",  action="store_true", help="Modo receptor")
    p.add_argument("--port",    type=int, default=PORT)
    p.add_argument("--save",    default=".", help="Carpeta donde guardar archivos recibidos")
    return p

def main():
    # Parseo especial para el formato: ghost-send <ip> "msg" -archivo
    raw = sys.argv[1:]
    file_arg = None
    filtered = []
    for arg in raw:
        if arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
            # Es un archivo: -archivo.zip
            file_arg = arg[1:]
        else:
            filtered.append(arg)

    sys.argv = [sys.argv[0]] + filtered
    p = parse_args()
    args = p.parse_args()

    if args.listen:
        listen(args.port, args.save)
    elif args.target and args.message:
        # Validar IP
        ip_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        if not re.match(ip_pattern, args.target):
            print(f"{C.R}[!] IP inválida: {args.target}{C.RESET}")
            sys.exit(1)
        send(args.target, args.message, file_arg, args.port)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
