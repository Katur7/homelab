FROM python:3.13-alpine
RUN apk add --no-cache docker-cli docker-cli-compose git
WORKDIR /app
COPY updater.py .
CMD ["python3", "updater.py"]
