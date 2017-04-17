#!/bin/bash

# generate
python cmdlist/generate_wiki_page.py

# go to wiki
pushd ../dogbot.wiki

# commit push changes
git pull
git add .
git commit -m "generate"
git push

# come back
popd
