FROM gorialis/discord.py:alpine-full

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "run.py"]
