-- Estado del agente. NO vive en la base de n8n a proposito: esa tiene 139
-- tablas propias y mezclar datos de la aplicacion ahi hace que una migracion
-- de n8n pueda chocar con lo nuestro y que los respaldos queden confusos.
--
-- Postgres ejecuta los .sql de /docker-entrypoint-initdb.d SOLO la primera vez
-- que inicializa el volumen. En un despliegue nuevo esto corre solo; sobre un
-- volumen que ya existe hay que aplicarlo a mano:
--
--   docker exec -i n8n-postgres-1 psql -U n8n -d agente < n8n/esquema.sql

CREATE DATABASE agente;

\connect agente

-- El historial completo de cada conversacion, tal como lo consume el servicio:
-- `responder()` recibe los mensajes enteros porque el estado vive AQUI, no en
-- el proceso del agente.
CREATE TABLE IF NOT EXISTS conversaciones (
  sender_id   text PRIMARY KEY,
  mensajes    jsonb NOT NULL DEFAULT '[]'::jsonb,
  actualizado timestamptz NOT NULL DEFAULT now()
);

-- Deduplicacion por `mid`. No es opcional: Instagram reenvia el mismo evento
-- si el webhook no responde 200 a tiempo, y sin esto el cliente recibe la
-- misma respuesta dos o tres veces.
CREATE TABLE IF NOT EXISTS mids (
  mid   text PRIMARY KEY,
  visto timestamptz NOT NULL DEFAULT now()
);

-- Para poder purgar los viejos sin escanear la tabla entera.
CREATE INDEX IF NOT EXISTS mids_visto_idx ON mids (visto);
