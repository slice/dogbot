#!/usr/bin/env bash

scp config.prod.yml shiba:~/dogbot/config.yml
scp .env shiba:~/dogbot/.env

ssh shiba -t << ENDSSH
cd ~/dogbot; git fetch --all
cd ~/dogbot; git reset --hard origin/master
cd ~/dogbot; docker-compose stop
cd ~/dogbot; docker-compose up -d --build --force-recreate
ENDSSH
