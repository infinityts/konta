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
