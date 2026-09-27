# Sagemcom Control

App local para ver los dispositivos de tu red y
**encender/apagar su acceso a internet por MAC**, a tu antojo.

Habla directamente con la web de tu Sagemcom F@st 3686 (firmware Vodafone/ONO):
el bloqueo usa la página **Filtro MAC en modo DENEGAR**, igual que si lo
hicieras a mano en http://192.168.0.1. **Se ejecuta en tu red local**:
el router solo es accesible desde casa.

## Requisitos

- Python 3.11+
- Estar conectado a la red del Sagemcom
- Usuario y contraseña del router (los de la pegatina: `user` + clave)

## Instalación (Windows PowerShell)

```powershell
cd sagemcom-control
pip install -r requirements.txt
copy .env.example .env
notepad .env   # rellena ROUTER_PASS con tu clave
```

## Probar la conexión (recomendado)

```powershell
python test_login.py
```

Debe mostrar `OK login` y la lista actual del filtro MAC del router.

## Uso

```powershell
python app.py
```

Abre http://localhost:8000 en el móvil o PC (conectado a tu wifi).
La app hace un barrido de la red, muestra cada dispositivo con su MAC e IP,
y un interruptor para cortarle / devolverle internet.

Los bloqueados aparecen también aunque estén apagados, para poder
desbloquearlos después.

## Docker (opcional)

```bash
docker build -t sagemcom-control .
docker run --rm -p 8000:8000 --env-file .env sagemcom-control
```

## Seguridad

- Tus credenciales viven solo en tu `.env` local. No se envían a ningún
  sitio: todo el tráfico va de tu máquina al router (192.168.0.1).
- No subas tu `.env` a ningún repo.
