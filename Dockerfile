# The API image. Builds its own index during the build so it never starts empty.
FROM python:3.13-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data/raw ./data/raw

# Ingest at build time: reads data/raw, writes store/. Fails the build if anything is wrong,
# which is the point. No model key is needed for this step.
RUN python -m app.ingest.run

# PORT comes from Railway. APP_ALLOWED_ORIGINS and the keys are Railway variables.
EXPOSE 8020
CMD ["python", "-m", "app.api.run"]
