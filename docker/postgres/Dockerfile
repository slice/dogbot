FROM postgres:latest

ENV POSTGRES_USER dogbot
ENV POSTGRES_DB dogbot
ENV POSTGRES_PASSWORD dogbot

COPY ./schema.sql /docker-entrypoint-initdb.d/schema.sql
