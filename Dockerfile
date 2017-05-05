FROM python:latest

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

WORKDIR /src
ADD ./requirements.txt /src/requirements.txt
RUN pip install -r requirements.txt
ADD . /src

CMD ["python3", "dog.py"]
