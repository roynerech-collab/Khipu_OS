import json
import os
import re
import time
import uuid
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# ==========================================
# CREDENCIALES LOCALES INYECTADAS POR EL SERVIDOR
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
try:
    MI_TELEGRAM_ID = int(os.environ.get("MI_TELEGRAM_ID", "0"))
except ValueError:
    MI_TELEGRAM_ID = 0

DB_FILE = "./khipu_db.json"
APP_VERSION = "12.0"
LIMA_TZ = timezone(timedelta(hours=-5))
MAX_TRANSACCIONES = 80

# Colores ANSI para la consola
C = "\033[96m"
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
W = "\033[0m"
GR = "\033[90m"


def nueva_db():
    return {
        "ic": 0,
        "tc": 3.75,
        "a": [{"n": "Efectivo", "v": 0, "c": "liq"}],
        "l": [],
        "t": [],
        "last_msg_id": None,
    }


def load_db():
    if not os.path.exists(DB_FILE):
        return nueva_db()

    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    base = nueva_db()
    for key, value in base.items():
        data.setdefault(key, value)
    return data


def save_db(data):
    tmp_file = f"{DB_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, DB_FILE)


def normalizar_numero(valor):
    return float(valor.replace(",", "."))


def hoy_lima():
    return datetime.now(LIMA_TZ).strftime("%Y-%m-%d")


def generar_id():
    return os.urandom(2).hex().upper()


def get_btc_price_pen(tc_manual):
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers={"User-Agent": "KhipuOS/12.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            usd = float(data["price"])
            return usd * tc_manual, usd
    except Exception as e:
        print(f"{R}[AVISO] No se pudo consultar Binance: {e}{W}")
        return None, None


def valor_activo(item, btc_pen):
    if item.get("c") == "cri":
        return item.get("v", 0) * btc_pen if btc_pen else 0
    return item.get("v", 0)


def print_terminal_report(db, btc_pen):
    cap_liq = sum(x.get("v", 0) for x in db["a"] if x.get("c") == "liq" or "c" not in x)
    cap_cri = sum(valor_activo(x, btc_pen) for x in db["a"] if x.get("c") == "cri")
    cap_bi = sum(x.get("v", 0) for x in db["a"] if x.get("c") == "bi")
    cap_ve = sum(x.get("v", 0) for x in db["a"] if x.get("c") == "ve")

    pasivos = sum(x.get("v", 0) for x in db["l"])
    activos = cap_liq + cap_cri + cap_bi + cap_ve
    capital = db.get("ic", 0)
    utilidades = activos - pasivos - capital

    lines = []

    def add_line(text, hex_c, ansi_c):
        lines.append((text, hex_c))
        print(f"{ansi_c}{text}{W}")

    print("\n")
    add_line("==========================================================", "#00FFFF", C)
    add_line("              ESTADO DE SITUACION FINANCIERA              ", "#00E676", G)
    add_line("==========================================================", "#00FFFF", C)
    add_line("ACTIVOS", "#FFD54F", Y)
    add_line(f"  Liquido y Bancos  : S/ {cap_liq:>15,.2f}", "#FFFFFF", W)
    add_line(f"  Criptoactivos     : S/ {cap_cri:>15,.2f}", "#FFFFFF", W)
    add_line(f"  Bienes Inmuebles  : S/ {cap_bi:>15,.2f}", "#FFFFFF", W)
    add_line(f"  Vehiculos         : S/ {cap_ve:>15,.2f}", "#FFFFFF", W)
    add_line(f"TOTAL ACTIVO        : S/ {activos:>15,.2f}", "#00E676", G)
    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line("PASIVOS", "#FF5252", R)
    add_line(f"  Deudas y Oblig.   : S/ {pasivos:>15,.2f}", "#FFFFFF", W)
    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line("PATRIMONIO", "#00FFFF", C)
    add_line(f"  Capital Inicial   : S/ {capital:>15,.2f}", "#FFFFFF", W)
    add_line(f"  Utilidad Ejerc.   : S/ {utilidades:>15,.2f}", "#FFFFFF", W)
    add_line(f"TOTAL PAS. Y PAT.   : S/ {(pasivos + capital + utilidades):>15,.2f}", "#00E676", G)
    add_line("==========================================================", "#00FFFF", C)
    add_line(" COMANDOS RAPIDOS", "#AAAAAA", GR)
    add_line(" -50 Gasto      |  +50 Ingreso", "#AAAAAA", GR)
    add_line(" /tc 3.80       |  /ic 1000", "#AAAAAA", GR)
    add_line(" /ajuste Cuenta = Valor", "#AAAAAA", GR)
    add_line(" /ayuda", "#AAAAAA", GR)
    add_line("==========================================================", "#00FFFF", C)
    print("\n")
    return lines


def print_activos_report(db, btc_pen):
    lines = []

    def add_line(text, hex_c, ansi_c):
        lines.append((text, hex_c))
        print(f"{ansi_c}{text}{W}")

    print("\n")
    add_line("==========================================================", "#00FFFF", C)
    add_line("                    DETALLE DE ACTIVOS                    ", "#FFD54F", Y)
    add_line("==========================================================", "#00FFFF", C)
    total_activos = 0
    for x in db["a"]:
        v = valor_activo(x, btc_pen)
        total_activos += v
        nombre = x.get("n", "Activo")[:18]
        add_line(f"  {nombre:<18}  : S/ {v:>15,.2f}", "#FFFFFF", W)

    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line(f"TOTAL ACTIVOS         : S/ {total_activos:>15,.2f}", "#00E676", G)
    add_line("==========================================================", "#00FFFF", C)
    add_line(" Usa 'Refrescar Balance' para volver al resumen.          ", "#AAAAAA", GR)
    add_line("==========================================================", "#00FFFF", C)
    print("\n")
    return lines


def print_pasivos_report(db):
    lines = []

    def add_line(text, hex_c, ansi_c):
        lines.append((text, hex_c))
        print(f"{ansi_c}{text}{W}")

    print("\n")
    add_line("==========================================================", "#00FFFF", C)
    add_line("                    DETALLE DE PASIVOS                    ", "#FF5252", R)
    add_line("==========================================================", "#00FFFF", C)
    total_pasivos = 0
    if not db["l"]:
        add_line("  Libre de deudas en este momento.                        ", "#AAAAAA", GR)
    else:
        for x in db["l"]:
            v = x.get("v", 0)
            total_pasivos += v
            nombre = x.get("n", "Pasivo")[:18]
            add_line(f"  {nombre:<18}  : S/ {v:>15,.2f}", "#FFFFFF", W)

    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line(f"TOTAL PASIVOS         : S/ {total_pasivos:>15,.2f}", "#FF5252", R)
    add_line("==========================================================", "#00FFFF", C)
    add_line(" Usa 'Refrescar Balance' para volver al resumen.          ", "#AAAAAA", GR)
    add_line("==========================================================", "#00FFFF", C)
    print("\n")
    return lines


def generar_imagen_exacta(lines):
    try:
        font = ImageFont.truetype("consola.ttf", 24)
    except Exception:
        try:
            font = ImageFont.truetype("cour.ttf", 24)
        except Exception:
            font = ImageFont.load_default()

    line_height = 32
    width = 860
    height = len(lines) * line_height + 60

    img = Image.new("RGB", (width, height), color="#0A0A0A")
    draw = ImageDraw.Draw(img)

    x, y = 30, 30
    for text, hex_color in lines:
        draw.text((x, y), text, font=font, fill=hex_color)
        y += line_height

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def get_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "Gasto", "callback_data": "cmd_gasto"},
                {"text": "Ingreso", "callback_data": "cmd_ingreso"},
            ],
            [
                {"text": "Ver Activos", "callback_data": "cmd_activos"},
                {"text": "Ver Pasivos", "callback_data": "cmd_pasivos"},
            ],
            [{"text": "Refrescar Balance", "callback_data": "cmd_estado"}],
        ]
    }


def telegram_json(method, payload, timeout=8):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def delete_message(chat_id, message_id):
    try:
        telegram_json("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=5)
    except Exception:
        pass


def send_message(chat_id, text):
    try:
        telegram_json("sendMessage", {"chat_id": chat_id, "text": text}, timeout=8)
    except Exception as e:
        print(f"{R}[AVISO] No se pudo enviar mensaje: {e}{W}")


def multipart_photo(method, fields, file_field, photo_bytes, keyboard=None):
    boundary = uuid.uuid4().hex
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode("utf-8"))
        body.extend(f"{value}\r\n".encode("utf-8"))

    if keyboard:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b"Content-Disposition: form-data; name=\"reply_markup\"\r\n\r\n")
        body.extend(json.dumps(keyboard).encode("utf-8") + b"\r\n")

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f"Content-Disposition: form-data; name=\"{file_field}\"; filename=\"balance.png\"\r\n".encode("utf-8"))
    body.extend(b"Content-Type: image/png\r\n\r\n")
    body.extend(photo_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def send_photo_direct(chat_id, photo_bytes, keyboard=None):
    try:
        data = multipart_photo("sendPhoto", {"chat_id": chat_id}, "photo", photo_bytes, keyboard=keyboard)
        return True, data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"{R}[AVISO] Error enviando foto nueva: {e}{W}")
        return False, None


def edit_photo_direct(chat_id, message_id, photo_bytes, keyboard=None):
    try:
        multipart_photo(
            "editMessageMedia",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "media": json.dumps({"type": "photo", "media": "attach://new_photo"}),
            },
            "new_photo",
            photo_bytes,
            keyboard=keyboard,
        )
        return True
    except Exception:
        return False


def show_alert_in_telegram(cb_id, text):
    try:
        telegram_json(
            "answerCallbackQuery",
            {"callback_query_id": cb_id, "text": text, "show_alert": True},
            timeout=5,
        )
    except Exception:
        pass


def ack_callback(cb_id):
    try:
        telegram_json("answerCallbackQuery", {"callback_query_id": cb_id}, timeout=5)
    except Exception:
        pass


def procesar_comando(texto, db):
    texto = texto.strip()
    match = re.match(r"^([+-])\s*([0-9]+(?:[\.,][0-9]+)?)\s*(.*)", texto)

    if match:
        signo = match.group(1)
        monto = normalizar_numero(match.group(2))
        desc = match.group(3).strip() or "Operacion general"
        monto_real = monto if signo == "+" else -monto

        cuenta_liq = next((x for x in db["a"] if x.get("c") == "liq" or "c" not in x), None)
        if not cuenta_liq:
            cuenta_liq = {"n": "Efectivo", "v": 0, "c": "liq"}
            db["a"].insert(0, cuenta_liq)

        cuenta_liq["v"] += monto_real
        db["t"].insert(
            0,
            {"id": generar_id(), "d": hoy_lima(), "desc": desc, "amt": monto_real, "cat": "Manual"},
        )
        del db["t"][MAX_TRANSACCIONES:]
        save_db(db)
        return True, "Movimiento registrado."

    lower = texto.lower()

    if lower.startswith("/tc "):
        try:
            db["tc"] = normalizar_numero(texto.split(maxsplit=1)[1])
            save_db(db)
            return True, "Tipo de cambio actualizado."
        except Exception:
            return False, "Formato correcto: /tc 3.80"

    if lower.startswith("/ic "):
        try:
            db["ic"] = normalizar_numero(texto.split(maxsplit=1)[1])
            save_db(db)
            return True, "Capital inicial actualizado."
        except Exception:
            return False, "Formato correcto: /ic 1000"

    if lower.startswith("/ajuste "):
        try:
            cuenta, valor = texto[len("/ajuste "):].split("=", 1)
            cuenta = cuenta.strip()
            nuevo_valor = normalizar_numero(valor.strip())
            for arr in [db["a"], db["l"]]:
                for item in arr:
                    if item.get("n", "").lower() == cuenta.lower():
                        item["v"] = nuevo_valor
                        save_db(db)
                        return True, f"Ajuste aplicado a {item.get('n', cuenta)}."
            return False, f"No encontre la cuenta: {cuenta}"
        except Exception:
            return False, "Formato correcto: /ajuste Cuenta = Valor"

    if lower in ["/estado", "/start"]:
        return True, "Estado solicitado."

    if lower == "/ayuda":
        return False, ayuda_texto()

    return False, "Comando no reconocido. Usa /ayuda."


def ayuda_texto():
    return (
        "Khipu OS - comandos\n\n"
        "-50 Comida\n"
        "+3000 Sueldo\n"
        "/tc 3.80\n"
        "/ic 1000\n"
        "/ajuste Billetera = 15000\n"
        "/estado"
    )


def render_estado(db):
    btc_pen, _ = get_btc_price_pen(db.get("tc", 3.75))
    lines = print_terminal_report(db, btc_pen)
    return generar_imagen_exacta(lines)


def actualizar_reporte(chat_id, db):
    img_bytes = render_estado(db)
    if db.get("last_msg_id"):
        print(f"{Y}[ACTUALIZANDO]{W} Modificando reporte anterior...")
        ok = edit_photo_direct(chat_id, db["last_msg_id"], img_bytes, keyboard=get_keyboard())
        if ok:
            return

    print(f"{Y}[ENVIANDO]{W} Enviando reporte nuevo.")
    ok, new_id = send_photo_direct(chat_id, img_bytes, keyboard=get_keyboard())
    if ok:
        db["last_msg_id"] = new_id
        save_db(db)


def mostrar_banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{C}==================================================")
    print(f"       KHIPU_OS SERVER V{APP_VERSION}")
    print("       Bot Telegram financiero")
    print(f"=================================================={W}\n")


def credenciales_validas():
    return bool(TELEGRAM_TOKEN and MI_TELEGRAM_ID and "AQUI" not in TELEGRAM_TOKEN.upper())


def main():
    mostrar_banner()

    if not credenciales_validas():
        print(f"{R}[ERROR] Configura TELEGRAM_TOKEN y MI_TELEGRAM_ID en LANZADOR.bat.{W}")
        time.sleep(15)
        return

    print(f"{G}[INFO]{W} Servidor online. Esperando mensajes de Telegram...")
    last_update_id = 0

    while True:
        try:
            data = telegram_json(
                "getUpdates",
                {"offset": last_update_id + 1, "timeout": 30},
                timeout=35,
            )

            for update in data.get("result", []):
                last_update_id = update["update_id"]

                if "callback_query" in update:
                    cb = update["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    msg_id = cb["message"]["message_id"]
                    user_id = cb["from"]["id"]
                    cb_data = cb.get("data", "")

                    if user_id != MI_TELEGRAM_ID:
                        ack_callback(cb["id"])
                        continue

                    print(f"\n{C}===================================================={W}")
                    print(f"{Y}[BOTON]{W} Accion solicitada: {cb_data}")

                    if cb_data == "cmd_gasto":
                        show_alert_in_telegram(cb["id"], "Escribe: -50 Comida o -100 Gasolina")
                    elif cb_data == "cmd_ingreso":
                        show_alert_in_telegram(cb["id"], "Escribe: +3000 Sueldo o +200 Venta")
                    else:
                        ack_callback(cb["id"])
                        db = load_db()
                        btc_pen, _ = get_btc_price_pen(db.get("tc", 3.75))

                        if cb_data == "cmd_activos":
                            lines = print_activos_report(db, btc_pen)
                        elif cb_data == "cmd_pasivos":
                            lines = print_pasivos_report(db)
                        else:
                            lines = print_terminal_report(db, btc_pen)

                        img_bytes = generar_imagen_exacta(lines)
                        ok = edit_photo_direct(chat_id, msg_id, img_bytes, keyboard=get_keyboard())
                        if not ok:
                            print(f"{Y}[ENVIANDO]{W} No se pudo editar. Enviando nueva imagen.")
                            ok, new_id = send_photo_direct(chat_id, img_bytes, keyboard=get_keyboard())
                            if ok:
                                db["last_msg_id"] = new_id
                                save_db(db)

                    print(f"{C}===================================================={W}")
                    continue

                if "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    user_msg_id = msg["message_id"]
                    user_id = msg["from"]["id"]
                    text = msg["text"]

                    if user_id != MI_TELEGRAM_ID:
                        continue

                    print(f"\n{C}===================================================={W}")
                    print(f"{Y}[RECEPCION]{W} Comando: {text}")

                    db = load_db()
                    success, message = procesar_comando(text, db)
                    delete_message(chat_id, user_msg_id)

                    if success:
                        print(f"{G}[PROCESADO]{W} {message}")
                        actualizar_reporte(chat_id, db)
                    else:
                        print(f"{R}[ERROR]{W} {message}")
                        if text.strip().lower() == "/ayuda":
                            send_message(chat_id, message)

                    print(f"{C}===================================================={W}")

        except KeyboardInterrupt:
            print(f"\n{Y}[INFO]{W} Servidor detenido manualmente.")
            break
        except Exception as e:
            if "timed out" not in str(e).lower():
                print(f"{R}[AVISO] Error temporal: {e}{W}")
            time.sleep(2)


if __name__ == "__main__":
    main()
