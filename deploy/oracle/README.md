# Oracle Cloud Free deploy

Este despliegue esta pensado para una VM de Oracle Cloud Always Free con:

- Docker
- Docker Compose
- esta carpeta copiada a `/opt/feb_scraper/deploy/oracle`
- un dominio apuntando a la VM

## 1. Preparar variables

1. Copia `env.example` a `.env`.
2. Rellena:
   - `APP_DOMAIN`
   - `ACME_EMAIL`
   - `SESSION_SECRET`
   - `ADMIN_PASSWORD_HASH`

## 2. Preparar Caddy

Asegurate de que `APP_DOMAIN` apunta a esta VM.

## 3. Levantar la app

```bash
sudo mkdir -p /srv/feb-data/data /srv/feb-data/output/reports
sudo chown -R $USER:$USER /srv/feb-data
cd /opt/feb_scraper/deploy/oracle
docker compose --env-file .env up -d --build
```

La app quedara en:

- `https://APP_DOMAIN`

## 4. Datos persistentes

La carpeta `HOST_STORAGE_ROOT` guarda:

- `/var/data/data/feb.sqlite`
- `/var/data/output/reports`

### Copiar la base de datos inicial

```bash
mkdir -p /srv/feb-data/data
cp /opt/feb_scraper/data/feb.sqlite /srv/feb-data/data/feb.sqlite
docker compose restart app
```

## 5. Arranque automatico

1. Copia `feb-analytics.service.example` a `/etc/systemd/system/feb-analytics.service`.
2. Ajusta `WorkingDirectory` si hace falta.
3. Activa el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable feb-analytics
sudo systemctl start feb-analytics
```

## 6. Backup minimo recomendado

Haz copia periodica de:

- la carpeta `HOST_STORAGE_ROOT`
- o al menos de:
  - `/srv/feb-data/data/feb.sqlite`
  - `/srv/feb-data/output/reports`
