FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY parser/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY parser/parser.py parser/run.py ./
COPY api ./api
COPY scripts ./scripts

CMD ["python", "run.py"]
