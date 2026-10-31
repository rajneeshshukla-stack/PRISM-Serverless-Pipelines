# UNTESTED: Docker was not available in the environment where this repository was built.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
