#!/usr/bin/env bash
# Respaldo completo de Konta: base, archivos y variables.
#
# Deja las tres cosas juntas y un manifiesto con lo que había, para poder comprobar después que la
# copia es fiel (con scripts/verificar_migracion.py). No imprime secretos: las variables se copian
# tal cual, nunca por pantalla.
set -euo pipefail

CONTENEDOR="${KONTA_DB_CONTENEDOR:-konta-db}"
BD="${KONTA_BD:-finanzas}"
USUARIO="${KONTA_USUARIO:-finanzas}"
ARCHIVOS="${KONTA_ARCHIVOS:-/var/lib/konta/archivos}"
AMBIENTE="${KONTA_AMBIENTE:-/etc/konta/ia.env}"
DESTINO="${KONTA_RESPALDOS:-/var/backups/konta}"
SELLO="$(date +%Y%m%d-%H%M%S)"
CARPETA="$DESTINO/$SELLO"

mkdir -p "$CARPETA"
echo "==> Respaldo en $CARPETA"

echo "--> Base de datos"
podman exec "$CONTENEDOR" pg_dump -U "$USUARIO" -d "$BD" -Fc -f /tmp/konta-$SELLO.dump
podman cp "$CONTENEDOR:/tmp/konta-$SELLO.dump" "$CARPETA/base.dump"
podman exec "$CONTENEDOR" rm -f "/tmp/konta-$SELLO.dump"

echo "--> Archivos guardados"
if [ -d "$ARCHIVOS" ]; then
  tar -czf "$CARPETA/archivos.tar.gz" -C "$(dirname "$ARCHIVOS")" "$(basename "$ARCHIVOS")"
else
  echo "    (no hay carpeta de archivos: nada que copiar)"
fi

echo "--> Variables de entorno (sin imprimirlas)"
if [ -f "$AMBIENTE" ]; then
  cp "$AMBIENTE" "$CARPETA/ia.env"
  chmod 600 "$CARPETA/ia.env"
fi

echo "--> Manifiesto"
{
  echo "sello: $SELLO"
  echo "base: $BD"
  echo "usuarios: $(podman exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BD" -tAc 'select count(*) from usuarios')"
  echo "transacciones: $(podman exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BD" -tAc 'select count(*) from transacciones')"
  echo "facturas: $(podman exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BD" -tAc 'select count(*) from facturas')"
  echo "archivos: $(find "$ARCHIVOS" -type f 2>/dev/null | wc -l)"
  echo "archivos_bytes: $(du -sb "$ARCHIVOS" 2>/dev/null | cut -f1)"
  echo "version_esquema: $(podman exec "$CONTENEDOR" psql -U "$USUARIO" -d "$BD" -tAc 'select version_num from alembic_version')"
  echo "peso_dump: $(stat -c%s "$CARPETA/base.dump")"
  echo "sha256_dump: $(sha256sum "$CARPETA/base.dump" | cut -d' ' -f1)"
} > "$CARPETA/manifiesto.txt"
cat "$CARPETA/manifiesto.txt" | sed 's/^/    /'

echo "==> Listo. Para restaurar: scripts/restaurar.sh $CARPETA base_destino"
