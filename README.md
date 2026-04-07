# feb_scraper

## Desarrollo local

### Backend

```powershell
& ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
& ".venv\Scripts\python.exe" -m uvicorn backend.api.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend por defecto en `http://localhost:5173` y backend en `http://localhost:8000`.

## Publicacion segura V1

La app esta preparada para desplegarse en **Render** como un unico servicio Docker:

- backend FastAPI
- frontend compilado y servido por el propio backend
- SQLite e informes en disco persistente
- login interno con cookie de sesion

### Variables de entorno

- `APP_ENV=production`
- `APP_STORAGE_ROOT=/var/data`
- `SESSION_SECRET=<secreto largo aleatorio>`
- `ADMIN_PASSWORD_HASH=<hash Argon2 de la contrasena compartida>`
- `SESSION_TTL_HOURS=12`
- `ALLOWED_ORIGINS=` vacio si trabajas same-origin

### Generar el hash de la contrasena

```powershell
@'
from argon2 import PasswordHasher
print(PasswordHasher().hash("tu-contrasena-del-club"))
'@ | ".venv\Scripts\python.exe" -
```

### Render

El repo incluye:

- `Dockerfile`
- `render.yaml`

Pasos minimos:

1. Crear un Web Service en Render conectado al repo.
2. Montar un Persistent Disk en `/var/data`.
3. Definir `SESSION_SECRET` y `ADMIN_PASSWORD_HASH`.
4. Publicar con dominio propio y HTTPS.

### Comportamiento en produccion

- `docs`, `redoc` y `openapi.json` quedan desactivados.
- Los endpoints analiticos, informes y ficheros de informes exigen sesion valida.
- Se aplican cookies `HttpOnly`, `Secure` y `SameSite=Strict`.
- Se anaden headers basicos de seguridad y rate limiting en login e informes.

## Oracle Cloud Free

Si necesitas despliegue remoto gratis con persistencia, usa una VM Always Free en Oracle Cloud:

- `deploy/oracle/docker-compose.yml`
- `deploy/oracle/Caddyfile.example`
- `deploy/oracle/env.example`
- `deploy/oracle/feb-analytics.service.example`
- `deploy/oracle/README.md`

La idea es:

1. Crear una VM Ubuntu en Oracle Cloud Always Free.
2. Instalar Docker y Docker Compose.
3. Apuntar un dominio a la IP publica de la VM.
4. Levantar la app con `docker compose`.
5. Dejar Caddy delante para HTTPS automatico.
