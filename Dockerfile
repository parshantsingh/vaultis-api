FROM python:3.13-slim

WORKDIR /app

# Don't write .pyc files (throwaway in a container) and flush stdout/stderr immediately
# instead of buffering, so `docker compose logs` shows output as it happens, not in batches.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
