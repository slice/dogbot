FROM gorialis/discord.py:alpine

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "lifesaver.cli"]
