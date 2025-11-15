# PROGETTO_LINGUA_2/Docker/nginx/Dockerfile
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY Docker/nginx/default.conf /etc/nginx/conf.d/default.conf
