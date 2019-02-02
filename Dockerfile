FROM gorialis/discord.py:3.7-alpine-full

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "lifesaver.cli"]
