FROM python:3.12-slim
WORKDIR /app
COPY recommendation/requirements.txt /app/recommendation/requirements.txt
RUN python -m pip install --no-cache-dir -r recommendation/requirements.txt
COPY recommendation /app/recommendation
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python"]
