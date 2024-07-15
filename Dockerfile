FROM python:3.9-slim-bookworm
WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY src ./
CMD ["python", "/app/main.py"]
