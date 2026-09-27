# Router Control

App local para ver los dispositivos de tu red y **encender/apagar su
acceso a internet por MAC**, a tu antojo.

Funciona con dos routers a la vez:

- **Sagemcom F@st 3686** (firmware Vodafone/ONO, `192.168.0.1`): habla
  directamente con su web, usando la página **Filtro MAC en modo DENEGAR**.
- **TP-Link TL-WR940N v6** (`192.168.0.2`): usa su filtro MAC inalámbrico,
  también en modo DENEGAR.

Al bloquear un dispositivo, la app lo bloquea **en los dos routers**,
así da igual a qué wifi esté conectado. **Todo se ejecuta en tu red
local**: ningún dato sale de casa.

## Requisitos

- Python 3.11+
- Estar conectado a la red local
- Usuario y contraseña del Sagemcom (los de la pegatina: `user` + clave)
- Sesión web del TP-Link (ver abajo)

## Instalación (Windows PowerShell)

```powershell
cd sagemcom-control2
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Rellena en el `.env`:

- `ROUTER_PASS`: clave del Sagemcom
- `TPLINK_HOST`: IP del TP-Link (por defecto `192.168.0.2`)

## Sesión del TP-Link (una vez por reinicio del router)

El TP-Link cifra su web y no admite login automatizado, así que la app
reutiliza tu sesión del navegador:

1. Abre `http://192.168.0.2` en Chrome e inicia sesión.
2. Pulsa `F12` → pestaña **Consola** y ejecuta, una por una:
   - `location.href` → copia el token largo de la URL
     (lo que va entre `http://192.168.0.2/` y `/userRpm`)
   - `localStorage.getItem('encryptorAES')`
   - `localStorage.getItem('encryptorSeq')`
   - `localStorage.getItem('encryptorHash')`
   - `localStorage.getItem('encryptorRsa')`
3. Ejecuta y pega los 5 valores:

```powershell
python import_tplink_session.py
```

Se guardan en `tplink_session.json` (no se sube al repo).

## Uso

```powershell
python app.py
```

Abre http://localhost:8000. Verás cada dispositivo con su MAC, IP e
interruptor para cortarle / devolverle internet.

- **Renombrar**: toca el nombre del dispositivo.
- **Bloqueo manual**: si un dispositivo no aparece en el escaneo
  (p. ej. el firewall de Windows bloquea el ping), escribe su MAC en el
  campo "MAC manual" y pulsa Bloquear.
- Los bloqueados aparecen también aunque estén apagados, para poder
  desbloquearlos después.
- Los dispositivos del TP-Link llevan la etiqueta **TP-Link**.

## Desde el móvil

Con el PC encendido y en el mismo wifi, abre en el móvil:

```
http://IP-del-PC:8000
```

(averigua la IP con `ipconfig` en PowerShell). Si no carga, permite el
puerto 8000 en el firewall de Windows.

Para tenerlo como icono de app: en Chrome del móvil, menú ⋮ →
"Añadir a pantalla de inicio".

## Arranque automático (Windows)

Crea `RouterControl.bat` en el escritorio:

```powershell
Set-Content "$env:USERPROFILE\Desktop\RouterControl.bat" "@echo off"
Add-Content "$env:USERPROFILE\Desktop\RouterControl.bat" "cd /d $pwd"
Add-Content "$env:USERPROFILE\Desktop\RouterControl.bat" "pythonw app.py"
```

Para que arranque solo al encender el PC: `Win+R` → `shell:startup` →
copia ahí el `.bat`.

## Nota sobre móviles (MAC aleatoria)

Los móviles modernos cambian su MAC por privacidad y el bloqueo puede
dejar de pillarlos. Desactívalo para tu wifi en cada teléfono:

- **iPhone**: Ajustes → Wi-Fi → ⓘ de tu red → desactiva
  "Dirección Wi-Fi privada".
- **Android**: Ajustes → Wi-Fi → tu red → "Tipo de MAC" →
  "MAC del dispositivo".

## Tecnologías

- **Python 3.11+**
- **FastAPI** — API y servidor web de la app
- **Uvicorn** — servidor ASGI
- **requests** — comunicación HTTP con las webs de los routers
- **PyCryptodome** — cifrado AES-128-CBC para hablar con el TP-Link
  (ingeniería inversa de su `tpEncrypt.js`)
- **python-dotenv** — configuración en `.env`
- **HTML/CSS/JS** (vanilla, sin frameworks) — interfaz responsive,
  servida inline desde `app.py`
- **ThreadPoolExecutor** — barrido ping paralelo para descubrir
  dispositivos

## Docker (opcional)

```bash
docker build -t router-control .
docker run --rm -p 8000:8000 --env-file .env router-control
```

## Seguridad

- Tus credenciales viven solo en tu `.env` local. No se envían a ningún
  sitio: todo el tráfico va de tu máquina a los routers.
- No subas tu `.env` ni `tplink_session.json` a ningún repo
  (ya están en `.gitignore`).
