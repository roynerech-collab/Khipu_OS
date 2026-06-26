import os
import json
import time
import urllib.request
import urllib.parse
import re
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 1. CREDENCIALES INYECTADAS DESDE EL .BAT
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
try:
    MI_TELEGRAM_ID = int(os.environ.get("MI_TELEGRAM_ID", "0"))
except ValueError:
    MI_TELEGRAM_ID = 0

DB_FILE = './khipu_db.json'

# Colores ANSI para el CMD
C = '\033[96m'  # Cyan
G = '\033[92m'  # Green
R = '\033[91m'  # Red
Y = '\033[93m'  # Yellow
W = '\033[0m'   # White/Reset
GR = '\033[90m' # Gray

def load_db():
    if not os.path.exists(DB_FILE):
        return {"ic": 0, "tc": 3.75, "a": [{"n": "Efectivo", "v": 0, "c": "liq"}], "l": [], "t": [], "last_msg_id": None}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if "tc" not in data: data["tc"] = 3.75
        if "ic" not in data: data["ic"] = 0
        return data

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_btc_price_pen(tc_manual):
    try:
        req = urllib.request.Request('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as res:
            data = json.loads(res.read().decode())
            usd = float(data['price'])
            return usd * tc_manual, usd
    except Exception as e:
        print(f"{R}[!] Advertencia: No se pudo conectar a Binance ({e}){W}")
        return None, None

def print_terminal_report(db, btc_pen):
    cap_liq = sum(x['v'] for x in db['a'] if x.get('c') == 'liq' or 'c' not in x)
    cap_cri = sum(x['v'] * btc_pen for x in db['a'] if x.get('c') == 'cri') if btc_pen else 0
    cap_bi = sum(x['v'] for x in db['a'] if x.get('c') == 'bi')
    cap_ve = sum(x['v'] for x in db['a'] if x.get('c') == 've')
    
    pasivos = sum(x['v'] for x in db['l'])
    activos = cap_liq + cap_cri + cap_bi + cap_ve
    capital = db.get('ic', 0)
    utilidades = activos - pasivos - capital
    patrimonio = capital + utilidades

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
    add_line(" LEYENDA DE COMANDOS RAPIDOS:", "#AAAAAA", GR)
    add_line(" -50 Gasto      |  /tc 3.80 (Cambiar TC)      ", "#AAAAAA", GR)
    add_line(" +50 Ingreso    |  /ic 1000 (Capital Inicial) ", "#AAAAAA", GR)
    add_line(" /ajuste Cuenta = Valor                       ", "#AAAAAA", GR)
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
    for x in db['a']:
        v = x['v'] * btc_pen if x.get('c')=='cri' and btc_pen else x['v']
        total_activos += v
        nombre = x['n'][:18] # Truncar si es muy largo
        add_line(f"  {nombre:<18}  : S/ {v:>15,.2f}", "#FFFFFF", W)
    
    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line(f"TOTAL ACTIVOS         : S/ {total_activos:>15,.2f}", "#00E676", G)
    add_line("==========================================================", "#00FFFF", C)
    add_line(" (Usa el boton 'Refrescar Balance' para volver)           ", "#AAAAAA", GR)
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
    if not db['l']:
        add_line("  Libre de deudas en este momento.                        ", "#AAAAAA", GR)
    else:
        for x in db['l']:
            v = x['v']
            total_pasivos += v
            nombre = x['n'][:18]
            add_line(f"  {nombre:<18}  : S/ {v:>15,.2f}", "#FFFFFF", W)
    
    add_line("----------------------------------------------------------", "#00FFFF", C)
    add_line(f"TOTAL PASIVOS         : S/ {total_pasivos:>15,.2f}", "#FF5252", R)
    add_line("==========================================================", "#00FFFF", C)
    add_line(" (Usa el boton 'Refrescar Balance' para volver)           ", "#AAAAAA", GR)
    add_line("==========================================================", "#00FFFF", C)
    print("\n")
    return lines

def generar_imagen_exacta(lines):
    try:
        font = ImageFont.truetype("consola.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("cour.ttf", 24)
        except:
            font = ImageFont.load_default()

    line_height = 32
    width = 860
    height = len(lines) * line_height + 60

    img = Image.new('RGB', (width, height), color='#0A0A0A')
    draw = ImageDraw.Draw(img)

    x, y = 30, 30
    for text, hex_color in lines:
        draw.text((x, y), text, font=font, fill=hex_color)
        y += line_height

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def get_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "💸 Gasto", "callback_data": "cmd_gasto"},
                {"text": "💰 Ingreso", "callback_data": "cmd_ingreso"}
            ],
            [
                {"text": "💎 Ver Activos", "callback_data": "cmd_activos"},
                {"text": "🔴 Ver Pasivos", "callback_data": "cmd_pasivos"}
            ],
            [
                {"text": "📊 Refrescar Balance", "callback_data": "cmd_estado"}
            ]
        ]
    }

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=5)
    except: pass

def send_photo_direct(chat_id, photo_bytes, keyboard=None):
    boundary = uuid.uuid4().hex
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n")
    body.extend(f"{chat_id}\r\n".encode('utf-8'))
    
    if keyboard:
        body.extend(f"--{boundary}\r\n".encode('utf-8'))
        body.extend(b"Content-Disposition: form-data; name=\"reply_markup\"\r\n\r\n")
        body.extend(json.dumps(keyboard).encode('utf-8') + b"\r\n")
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"photo\"; filename=\"balance.png\"\r\n")
    body.extend(b"Content-Type: image/png\r\n\r\n")
    body.extend(photo_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode('utf-8'))
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode())
            return True, data.get('result', {}).get('message_id')
    except Exception as e:
        print(f"{R}[!] Error de red enviando foto nueva: {e}{W}")
        return False, None

def edit_photo_direct(chat_id, message_id, photo_bytes, keyboard=None):
    boundary = uuid.uuid4().hex
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageMedia"
    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n")
    body.extend(f"{chat_id}\r\n".encode('utf-8'))
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"message_id\"\r\n\r\n")
    body.extend(f"{message_id}\r\n".encode('utf-8'))
    
    media_json = json.dumps({"type": "photo", "media": "attach://new_photo"})
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"media\"\r\n\r\n")
    body.extend(media_json.encode('utf-8') + b"\r\n")
    
    if keyboard:
        body.extend(f"--{boundary}\r\n".encode('utf-8'))
        body.extend(b"Content-Disposition: form-data; name=\"reply_markup\"\r\n\r\n")
        body.extend(json.dumps(keyboard).encode('utf-8') + b"\r\n")
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(b"Content-Disposition: form-data; name=\"new_photo\"; filename=\"balance.png\"\r\n")
    body.extend(b"Content-Type: image/png\r\n\r\n")
    body.extend(photo_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode('utf-8'))
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return True
    except Exception as e:
        # Falla normalmente si el usuario borro el mensaje del bot
        return False

def show_alert_in_telegram(cb_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": cb_id, "text": text, "show_alert": True}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try: urllib.request.urlopen(req, timeout=5)
    except: pass

def procesar_comando(texto, db):
    texto = texto.strip()
    ahora = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")
    match = re.match(r'^([+-])\s*([\d\.]+)\s*(.*)', texto)
    
    if match:
        signo = match.group(1)
        monto = float(match.group(2))
        desc = match.group(3).strip() or "Operación General"
        monto_real = monto if signo == '+' else -monto
        
        cuenta_liq = next((x for x in db['a'] if x.get('c') == 'liq' or 'c' not in x), None)
        if not cuenta_liq:
            cuenta_liq = {"n": "Efectivo", "v": 0, "c": "liq"}
            db['a'].insert(0, cuenta_liq)
            
        cuenta_liq['v'] += monto_real
        tx_id = os.urandom(2).hex().upper()
        db['t'].insert(0, {"id": tx_id, "d": ahora, "desc": desc, "amt": monto_real, "cat": "Manual"})
        
        if len(db['t']) > 50: db['t'].pop()
        save_db(db)
        return True
    elif texto.lower().startswith('/tc '):
        try: db['tc'] = float(texto.split(' ')[1]); save_db(db); return True
        except: pass
    elif texto.lower().startswith('/ic '):
        try: db['ic'] = float(texto.split(' ')[1]); save_db(db); return True
        except: pass
    elif texto.lower().startswith('/ajuste '):
        try:
            partes = texto.split('=')
            cuenta = partes[0].replace('/ajuste', '').strip()
            nuevo_valor = float(partes[1].strip())
            for arr in [db['a'], db['l']]:
                for item in arr:
                    if item['n'].lower() == cuenta.lower():
                        item['v'] = nuevo_valor
                        save_db(db); return True
        except: pass
    elif texto.lower() == '/estado' or texto.lower() == '/start':
        return True

    return False

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{C}██████████████████████████████████████████████████")
    print("█             KHIPU_OS SERVER V11.0              █")
    print("█     (ARQUITECTURA ZERO-SPAM / EDICIÓN VIVA)    █")
    print(f"██████████████████████████████████████████████████{W}\n")

    if MI_TELEGRAM_ID == 0 or not TELEGRAM_TOKEN or "AQUI" in TELEGRAM_TOKEN:
        print(f"{R}[ERROR CRÍTICO] Configura TELEGRAM_TOKEN y MI_TELEGRAM_ID en start_khipu.bat{W}")
        time.sleep(15); return

    print(f"{G}[INFO]{W} Servidor online. Cero sábanas de texto activado...")
    last_update_id = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            payload = {"offset": last_update_id + 1, "timeout": 30}
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            
            with urllib.request.urlopen(req, timeout=35) as res:
                data = json.loads(res.read().decode())
                
                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        last_update_id = update['update_id']
                        
                        # --- MANEJO DE BOTONES (EDICIÓN VIVA DE IMAGEN) ---
                        if 'callback_query' in update:
                            cb = update['callback_query']
                            chat_id = cb['message']['chat']['id']
                            msg_id = cb['message']['message_id']
                            user_id = cb['from']['id']
                            cb_data = cb['data']
                            
                            if user_id != MI_TELEGRAM_ID: continue

                            print(f"\n{C}===================================================={W}")
                            print(f"{Y}[BOTÓN]{W} Acción solicitada: {cb_data}")
                            
                            if cb_data == 'cmd_gasto':
                                show_alert_in_telegram(cb['id'], "Escribe en el chat así:\n\n-50 Comida\n-100 Gasolina\n\nEl bot borrará tu mensaje automáticamente.")
                                print(f"{G}[ALERTA NATIVA]{W} Mostrada en pantalla del usuario.")
                            elif cb_data == 'cmd_ingreso':
                                show_alert_in_telegram(cb['id'], "Escribe en el chat así:\n\n+3000 Sueldo\n+200 Venta")
                                print(f"{G}[ALERTA NATIVA]{W} Mostrada en pantalla del usuario.")
                            else:
                                # Acusar recibo para que no se quede cargando el botón
                                try: urllib.request.urlopen(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery?callback_query_id={cb['id']}")
                                except: pass

                                db = load_db()
                                btc_pen, _ = get_btc_price_pen(db['tc'])

                                if cb_data == 'cmd_activos':
                                    lines = print_activos_report(db, btc_pen)
                                elif cb_data == 'cmd_pasivos':
                                    lines = print_pasivos_report(db)
                                elif cb_data == 'cmd_estado':
                                    lines = print_terminal_report(db, btc_pen)

                                img_bytes = generar_imagen_exacta(lines)
                                
                                print(f"{Y}[ACTUALIZANDO]{W} Sobrescribiendo imagen anterior (Zero-Spam)...")
                                ok = edit_photo_direct(chat_id, msg_id, img_bytes, keyboard=get_keyboard())
                                if not ok:
                                    print(f"{R}[AVISO]{W} No se pudo editar. Enviando nueva imagen.")
                                    send_photo_direct(chat_id, img_bytes, keyboard=get_keyboard())

                            print(f"{C}===================================================={W}")
                            continue

                        # --- MANEJO DE COMANDOS DE TEXTO ---
                        if 'message' in update and 'text' in update['message']:
                            msg = update['message']
                            chat_id = msg['chat']['id']
                            user_msg_id = msg['message_id']
                            user_id = msg['from']['id']
                            text = msg['text']

                            if user_id != MI_TELEGRAM_ID: continue

                            print(f"\n{C}===================================================={W}")
                            print(f"{Y}[RECEPCIÓN]{W} Comando : {text}")
                            
                            db = load_db()
                            success = procesar_comando(text, db)
                            
                            # Cero Rastro: Borrar el mensaje que el usuario acaba de escribir
                            delete_message(chat_id, user_msg_id)
                            
                            if success:
                                print(f"{G}[PROCESADO]{W} Base de datos actualizada.")
                                btc_pen, _ = get_btc_price_pen(db['tc'])
                                lines = print_terminal_report(db, btc_pen)
                                img_bytes = generar_imagen_exacta(lines)
                                
                                # Intentar editar el ultimo mensaje conocido, si no enviar uno nuevo
                                if db.get('last_msg_id'):
                                    print(f"{Y}[ACTUALIZANDO]{W} Modificando reporte anterior...")
                                    ok = edit_photo_direct(chat_id, db['last_msg_id'], img_bytes, keyboard=get_keyboard())
                                    if not ok:
                                        print(f"{Y}[ENVIANDO]{W} Enviando reporte nuevo (Botón anterior caducado).")
                                        ok, new_id = send_photo_direct(chat_id, img_bytes, keyboard=get_keyboard())
                                        if ok: db['last_msg_id'] = new_id; save_db(db)
                                else:
                                    ok, new_id = send_photo_direct(chat_id, img_bytes, keyboard=get_keyboard())
                                    if ok: db['last_msg_id'] = new_id; save_db(db)
                            else:
                                print(f"{R}[ERROR]{W} Comando inválido.")
                                # Si falla, mandar un pop up o no hacer nada (se borró el mensaje erróneo de todas formas)
                            
                            print(f"{C}===================================================={W}")

        except Exception as e:
            if "timed out" not in str(e).lower(): pass
        time.sleep(0.1)

if __name__ == "__main__":
    main()