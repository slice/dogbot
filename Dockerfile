FROM python:latest

COPY requirements.txt /src/dog/requirements.txt
WORKDIR /src/dog
RUN pip install -r requirements.txt
COPY . /src/dog
CMD ["python3", "dog.py"]
