# Cloud Run read-only con snapshot semanal

Esta variante publica la app web en **Google Cloud Run** sin migrar la base de datos:

- la app sigue usando `FastAPI + frontend same-origin`
- la nube es `read-only`
- cada domingo tu PC sube `data/feb.sqlite` a **Google Cloud Storage**
- la revision nueva de Cloud Run descarga esa snapshot al arrancar
- los informes viven en almacenamiento efimero y pueden desaparecer tras refresco o cold start

## Arquitectura

- `Cloud Run`
- `Google Cloud Storage` con un objeto fijo, por ejemplo `gs://tu-bucket/snapshots/feb.sqlite`
- `max instances = 1`
- `min instances = 0`
- `APP_STORAGE_ROOT=/tmp`
- `APP_STORAGE_MODE=gcs_snapshot`
- `REPORT_STORAGE_MODE=ephemeral`

## Variables de entorno

- `APP_ENV=production`
- `APP_STORAGE_ROOT=/tmp`
- `APP_STORAGE_MODE=gcs_snapshot`
- `REPORT_STORAGE_MODE=ephemeral`
- `SQLITE_BUCKET=tu-bucket`
- `SQLITE_OBJECT=snapshots/feb.sqlite`
- `SQLITE_LOCAL_PATH=/tmp/feb.sqlite`
- `SQLITE_SNAPSHOT_VERSION=bootstrap`
- `SESSION_SECRET=<secreto largo>`
- `ADMIN_PASSWORD_HASH=<hash Argon2>`

## Service account de Cloud Run

La service account asociada al servicio de Cloud Run solo necesita leer la snapshot:

- `roles/storage.objectViewer` sobre el bucket

## Despliegue inicial

1. Compila la imagen o despliega desde el repo.
2. Crea el bucket y sube una primera snapshot:

```powershell
gcloud storage buckets create gs://tu-bucket --location=US-CENTRAL1
gcloud storage cp data\feb.sqlite gs://tu-bucket/snapshots/feb.sqlite
```

3. Despliega Cloud Run:

```powershell
gcloud run deploy feb-analytics `
  --source . `
  --region us-central1 `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --min-instances 0 `
  --max-instances 1 `
  --set-env-vars APP_ENV=production,APP_STORAGE_ROOT=/tmp,APP_STORAGE_MODE=gcs_snapshot,REPORT_STORAGE_MODE=ephemeral,SQLITE_BUCKET=tu-bucket,SQLITE_OBJECT=snapshots/feb.sqlite,SQLITE_LOCAL_PATH=/tmp/feb.sqlite,SQLITE_SNAPSHOT_VERSION=bootstrap
```

4. Anade despues:
- `SESSION_SECRET`
- `ADMIN_PASSWORD_HASH`

## Publish semanal desde tu PC

El repo incluye:

- `scripts/sync_and_publish.py`
- `scripts/cloud_publish_config.example.json`

Flujo:

1. Copia el ejemplo a `data/cloud_publish_config.json`.
2. Rellena:
   - `GCP_PROJECT_ID`
   - `GCP_REGION`
   - `CLOUD_RUN_SERVICE`
   - `GCS_BUCKET`
   - `GCS_OBJECT`
   - `GOOGLE_APPLICATION_CREDENTIALS`
3. La tarea dominical actual seguira llamando al mismo script.
4. Si el config existe y esta activo, al final del sync:
   - sube `data/feb.sqlite`
   - actualiza `SQLITE_SNAPSHOT_VERSION`
   - Cloud Run levanta una revision nueva con la snapshot nueva

## Comportamiento esperado

- La app cloud nunca escribe datos FEB.
- La actualizacion semanal se sigue haciendo solo en tu PC.
- Los informes generados en cloud no son persistentes.
