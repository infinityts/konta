# Etapa de build
FROM node:22 AS build
WORKDIR /app
RUN npm install -g pnpm@11.7.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Etapa de servicio (nginx sirve estáticos + proxy /api -> backend)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

# Qué versión (commit) sirve esta pantalla: se consulta en /version para comprobar que lo
# desplegado es lo que se cree (una pantalla vieja con un backend nuevo es un fallo real).
ARG FINANZAS_VERSION=desconocida
RUN echo "$FINANZAS_VERSION" > /usr/share/nginx/html/version.txt
