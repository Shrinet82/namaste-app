FROM python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir "PyYAML==5.3"
COPY app.py .
EXPOSE 8080
USER 10001
CMD ["python", "-u", "app.py"]
