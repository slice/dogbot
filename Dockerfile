FROM gorialis/discord.py:rewrite-extras

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "run.py"]
