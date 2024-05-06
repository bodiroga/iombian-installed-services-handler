FROM python:3.9.2-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY src ./
CMD ["python", "/app/main.py"]
