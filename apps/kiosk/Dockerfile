FROM node:26-alpine AS build
WORKDIR /web
COPY apps/kiosk/package.json apps/kiosk/package-lock.json* ./
RUN npm install
COPY apps/kiosk ./
RUN npm run build

FROM nginx:alpine
COPY apps/kiosk/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
