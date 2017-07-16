FROM python:3

# create required directories
RUN mkdir /opt/dogbot

# install required dependencies
ADD requirements.txt /opt/dogbot
RUN pip install -r /opt/dogbot/requirements.txt

# install apt dependencies
RUN apt-get update
RUN apt-get install libffi-dev libopus-dev
RUN apt-get install libmagickwand-dev

# add source files
ADD . /opt/dogbot

WORKDIR /opt/dogbot
