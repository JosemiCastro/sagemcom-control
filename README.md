# Sagemcom Control

App local para ver los dispositivos conectados a tu Sagemcom F@st 3686
y **encender/apagar su acceso a internet por MAC**, a tu antojo.

Funciona con la API interna del router (librería `python-sagemcom-api`),
la misma que usa su panel web. **Se ejecuta en tu red local**:
el router (192.168.0.1) solo es accesible desde casa.

## Requisitos

- Python 3.11+
- Estar conectado a la red del Sagemcom
- Usuario y contraseña del router (los de la pegatina: `user` + clave)

## Instalación

```bash
cd sagemcom-control
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edita .env con tus datos
```

## Paso 0 — Descubrir el parámetro de bloqueo (solo una vez)

Cada firmware expone el bloqueo en un parámetro distinto. Este script
busca candidatos en el modelo de datos del router:

```bash
python discover.py
```

Te mostrará ramas como `Device.WiFi...`, `Device.X_SAGEMCOM...` con
pistas (Parental, MACFilter, Block...). Busca un parámetro que sea
una **lista de MACs** (modo denegar) o un **flag por dispositivo**.

Cuando lo encuentres, ponlo en `.env`:

```ini
# Ejemplo (ajusta a lo que devuelva discover.py en tu firmware):
BLOCK_LIST_XPATH=Device.WiFi.AccessPoint.1.X_SAGEMCOM_MACFilter.DenyList
BLOCK_LIST_SEP=,
```

Si tu firmware no expone ningún parámetro escribible para bloqueo,
el listado de dispositivos seguirá funcionando y el script te lo dirá.

## Uso

```bash
python app.py
```

Abre http://localhost:8000 en el móvil o PC (conectado a tu wifi).
Verás los dispositivos con su MAC, IP y nombre, y un interruptor
para cortarles / devolverles internet.

El estado de bloqueados se guarda en `blocked.json`.

## Docker (opcional)

```bash
docker build -t sagemcom-control .
docker run --rm -p 8000:8000 --env-file .env sagemcom-control
```

## Seguridad

- Tus credenciales viven solo en tu `.env` local. No se envían a ningún
  sitio: todo el tráfico va de tu máquina al router (192.168.0.1).
- No subas tu `.env` a ningún repo.
