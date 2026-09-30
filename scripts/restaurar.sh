#!/usr/bin/env bash
# Restaura un respaldo en una base **de destino** (por defecto, una de comprobación).
#
# En la máquina nueva se usa igual, cambiando el contenedor y el destino. Restaurar en una base
# aparte primero es lo que permite comprobar los números sin tocar la buena.
set -euo pipefail

CARPETA="${1:?uso: restaurar.sh <carpeta-del-respaldo> [base_destino]}"
BD_DESTINO="${2:-finanzas_verificacion}"
CONTENEDOR="${KONTA_DB_CONTENEDOR:-konta-db}"
USUARIO="${KONTA_USUARIO:-finanzas}"
ARCHIVOS_DESTINO="${KONTA_ARCHIVOS:-/var/lib/konta/archivos}"

[ -f "$CARPETA/base.dump" ] || { echo "No encuentro $CARPETA/base.dump"; exit 1; }

echo "==> Restaurando en la base «$BD_DESTINO»"
podman cp "$CARPETA/base.dump" "$CONTENEDOR:/tmp/restaurar.dump"
podman exec "$CONTENEDOR" psql -U "$USUARIO" -d postgres -c "drop database if exists $BD_DESTINO"
podman exec "$CONTENEDOR" psql -U "$USUARIO" -d postgres -c "create database $BD_DESTINO owner $USUARIO"
podman exec "$CONTENEDOR" pg_restore -U "$USUARIO" -d "$BD_DESTINO" --no-owner /tmp/restaurar.dump
podman exec "$CONTENEDOR" rm -f /tmp/restaurar.dump

if [ -f "$CARPETA/archivos.tar.gz" ]; then
  echo "==> Archivos: se dejan en $ARCHIVOS_DESTINO (mira que no pises los que ya hay)"
  echo "    tar -xzf $CARPETA/archivos.tar.gz -C $(dirname "$ARCHIVOS_DESTINO")"
fi

echo "==> Restaurado. Comprueba los números con:"
echo "    python scripts/verificar_migracion.py <url_original> <url_copia>"
