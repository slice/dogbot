#!/usr/bin/env bash

scp config.prod.yml shiba:~/dogbot/config.yml

ssh shiba -t << ENDSSH
cd ~/dogbot; git pull
cd ~/dogbot; docker-compose kill
cd ~/dogbot; docker-compose up -d --build --force-recreate
ENDSSH
