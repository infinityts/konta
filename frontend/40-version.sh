#!/bin/sh
# La versión se escribe **al arrancar**, no al construir: con un ARG de build, podman reutilizaba la
# capa cacheada y el sello se quedaba en la versión vieja aunque el build dijera que fue bien. Es
# justo lo que este archivo existe para detectar, así que se escribe donde no hay caché que valga.
set -e
echo "${FINANZAS_VERSION:-desconocida}" > /usr/share/nginx/html/version.txt
