FROM python:3.7-alpine

WORKDIR /app

RUN apk add --no-cache build-base git python3-dev zlib-dev jpeg-dev \
  freetype-dev

# deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# src
COPY . .

CMD ["python", "-m", "lifesaver.cli"]
