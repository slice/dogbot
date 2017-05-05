FROM python:latest

ADD ./schema.sql /docker-entrypoint-initdb.d/dogbot-schema.sql

WORKDIR /src
ADD ./requirements.txt /src/requirements.txt
RUN pip install -r requirements.txt
ADD . /src

CMD ["python3", "dog.py"]
