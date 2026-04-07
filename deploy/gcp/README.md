# Google Cloud free tier deploy

Esta variante esta pensada para una VM `e2-micro` del free tier de Google Cloud.
Para ahorrar RAM, no usa Docker.

## 1. VM recomendada

- Region: `us-central1`, `us-east1` o `us-west1`
- Machine type: `e2-micro`
- Disk: `30 GB` Standard Persistent Disk
- Firewall: permitir `HTTP` y `HTTPS`

## 2. Preparar la maquina

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl unzip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 3. Clonar el repo

```bash
cd /opt
sudo git clone https://github.com/bale2manos/feb_scraper.git
sudo chown -R $USER:$USER /opt/feb_scraper
cd /opt/feb_scraper
git switch codex/render-secure-club-v1
```

## 4. Instalar dependencias

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend
npm install
npm run build
cd ..
```

## 5. Crear almacenamiento persistente

```bash
sudo mkdir -p /srv/feb-data/data /srv/feb-data/output/reports
sudo chown -R $USER:$USER /srv/feb-data
```

## 6. Copiar la base de datos

```bash
cp /opt/feb_scraper/data/feb.sqlite /srv/feb-data/data/feb.sqlite
```

## 7. Configurar el servicio

1. Copia `deploy/gcp/feb-analytics.service.example` a `/etc/systemd/system/feb-analytics.service`.
2. Sustituye:
   - `SESSION_SECRET`
   - `ADMIN_PASSWORD_HASH`
3. Activa el servicio:

```bash
sudo cp deploy/gcp/feb-analytics.service.example /etc/systemd/system/feb-analytics.service
sudo nano /etc/systemd/system/feb-analytics.service
sudo systemctl daemon-reload
sudo systemctl enable feb-analytics
sudo systemctl start feb-analytics
```

## 8. Instalar Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

## 9. Configurar HTTPS

1. Apunta tu dominio a la IP publica de la VM.
2. Copia `deploy/gcp/Caddyfile.example` a `/etc/caddy/Caddyfile`.
3. Cambia `app.example.com` por tu dominio.
4. Reinicia Caddy:

```bash
sudo cp deploy/gcp/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

## 10. Comprobaciones

```bash
systemctl status feb-analytics
systemctl status caddy
curl http://127.0.0.1:8000/health
```

La web quedara en:

- `https://tu-dominio`
