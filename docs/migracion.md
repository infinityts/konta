# Migrar Konta a la máquina definitiva

La app vive hoy en un servidor de desarrollo (30 GB, disco al 91 %). La definitiva tendrá **500 GB o
más**. Esto es la lista de pasos, con lo que se puede comprobar en cada uno.

Lo que hay que llevarse son **cuatro cosas**: la base, los archivos de las facturas, las variables
(de IA y del informe) y el `.env` de los contenedores. El código no: eso está en git.

## 0. Antes de tocar nada

```bash
cd /opt/konta && git pull           # el código al día
podman exec konta-backend alembic current   # anota la versión del esquema
df -h /                              # cuánto ocupan la base y los archivos
du -sh /var/lib/konta/archivos
```

## 1. Respaldo (en la máquina vieja)

```bash
scripts/respaldo.sh
```

Deja en `/var/backups/konta/<fecha>/`:

| archivo | qué es |
|---|---|
| `base.dump` | la base en formato propio de Postgres (`pg_dump -Fc`) |
| `archivos.tar.gz` | los documentos guardados (`/var/lib/konta/archivos`) |
| `ia.env` | las variables (clave de IA, modelo, TRM, precios, dueño del informe) — en modo 600 |
| `manifiesto.txt` | qué había: filas por tabla, archivos, bytes, versión del esquema y **sha256** del dump |

**Comprueba el sha256** al copiarlo de máquina:

```bash
sha256sum base.dump     # tiene que dar lo mismo que en manifiesto.txt
```

## 2. Llevarlo a la máquina nueva

```bash
rsync -av --progress /var/backups/konta/<fecha>/ nueva:/var/backups/konta/<fecha>/
```

## 3. Base de datos (en la máquina nueva)

```bash
podman run -d --name konta-db --network konta-net \
  -e POSTGRES_USER=finanzas -e POSTGRES_PASSWORD=finanzas -e POSTGRES_DB=finanzas \
  -v /var/lib/konta/pgdata:/var/lib/postgresql/data -p 5433:5432 postgres:16

# restaurar en una base aparte primero, para comprobar sin tocar la buena
scripts/restaurar.sh /var/backups/konta/<fecha> finanzas_verificacion
```

## 4. Comprobar que los números cuadran (**el paso que no se puede saltar**)

```bash
python scripts/verificar_migracion.py \
  "postgresql+psycopg://finanzas:finanzas@127.0.0.1:5433/finanzas" \
  "postgresql+psycopg://finanzas:finanzas@127.0.0.1:5433/finanzas_verificacion"
```

Compara filas por tabla, **sumas de dinero** (ingresos, gastos, IVA), lecturas de IA y el **saldo de
cada usuario**, más una **huella md5** del contenido de las tablas con dinero: si un monto cambió
aunque el número de filas coincida, lo dice. Sale con código 1 si algo no cuadra.

Cuando diga *«La copia es fiel»*, se restaura en la base buena:

```bash
scripts/restaurar.sh /var/backups/konta/<fecha> finanzas
```

## 5. Archivos

```bash
mkdir -p /var/lib/konta/archivos
tar -xzf /var/backups/konta/<fecha>/archivos.tar.gz -C /var/lib/konta
find /var/lib/konta/archivos -type f | wc -l    # compáralo con el manifiesto
```

Si el disco nuevo es otro (por ejemplo `/datos`), se cambia con `FINANZAS_ALMACEN_RUTA`: la ruta
sale de configuración, no del código, así que no hay que tocar la app.

## 6. Contenedores y variables

```bash
# el .env de IA, en su sitio y con permisos cerrados
install -m 600 /var/backups/konta/<fecha>/ia.env /etc/konta/ia.env

podman build -t konta-backend ./backend
podman build -t konta-frontend ./frontend
podman run -d --name konta-backend --network konta-net --network-alias backend \
  -e FINANZAS_DATABASE_URL="postgresql+psycopg://finanzas:finanzas@db:5432/finanzas" \
  -e FINANZAS_SECRET_KEY="<la misma de siempre: si cambia, se cierran todas las sesiones>" \
  -e FINANZAS_TIMEZONE="America/Bogota" \
  # la versión se pasa al arrancar: con un ARG de build, la caché de podman se la come
  -e FINANZAS_VERSION="$(git rev-parse --short HEAD)" --env-file /etc/konta/ia.env \
  -v /var/lib/konta/archivos:/var/lib/konta/archivos:Z -p 8000:8000 konta-backend:latest
podman run -d --name konta-frontend --network konta-net -p 8082:80 konta-frontend:latest
```

**El `:Z` del volumen no es opcional** en un host con SELinux: sin él, el contenedor no puede
escribir y las facturas no se guardan (pasó, y se ve como «Permission denied»).

## 7. Certificados y URL

- Si la URL cambia, hay que **avisar a los usuarios** (el criterio de esta tarea) y actualizar el
  certificado (`certbot`, o el proxy que haya delante).
- Si se mantiene el dominio, lo único que cambia es a qué IP apunta.
- El asistente y la ayuda usan el **Ollama local**: en la máquina nueva hay que instalarlo y bajar
  `nomic-embed-text`, o la ayuda se queda en la búsqueda por palabras (funciona, pero encuentra
  menos). Se configura con `FINANZAS_OLLAMA_URL`.

## 8. Después de arrancar: la pasada de aceptación

```bash
python scripts/aceptacion.py --base http://<ip>:8082/api \
  --dsn "postgresql+psycopg://finanzas:finanzas@127.0.0.1:5433/finanzas"
```

Recorre en la app de verdad los caminos que tocan dinero y datos (crear usuario, subir y **releer
con IA**, el cupo y el almacenamiento, el asistente y su ayuda, **proponer y confirmar** una acción,
comprar y su recibo, los guardarraíles del informe y el borrado del archivo), saca una tabla y
**borra lo que creó**. Sale con código 1 si algo falla, así que sirve en un `if`. Con `--sin-ia`
corre sin gastar en el modelo.

## 9. Y a mano, lo que no se puede automatizar

```bash
curl -s localhost:8000/health                 # {"status":"ok",...}
podman exec konta-backend alembic current     # la misma versión del esquema que anotaste
podman exec konta-backend python -c "from app.archivos import limpiar_archivos_vencidos; print(limpiar_archivos_vencidos())"
```

Y a mano, con el usuario de siempre: entrar, ver el resumen, subir una factura y **releerla con
IA** (que es lo que toca la base, los archivos, la clave de IA y el Ollama, todo a la vez).

## 10. Si algo sale mal

La máquina vieja **no se apaga** hasta que la nueva esté comprobada: volver es cambiar el DNS otra
vez. Los datos no se pierden porque el respaldo sigue ahí y la base vieja queda intacta.

## Lo que no hay que llevarse

- **Los archivos de las facturas** caducan solos (7 a 15 días según el plan): no hace falta
  conservarlos más allá del respaldo.
- **Los temporales** de `.tools/` (documentos y capturas de pruebas): no van al repositorio ni a la
  máquina nueva.
