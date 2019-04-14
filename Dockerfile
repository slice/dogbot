FROM gorialis/discord.py:alpine

WORKDIR /app
COPY docker-requirements.txt ./
RUN pip install --no-cache-dir -r docker-requirements.txt

CMD ["python", "-m", "lifesaver.cli"]
