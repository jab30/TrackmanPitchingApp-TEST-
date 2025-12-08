# 1) Base image
FROM python:3.10-slim

# 2) Set working directory
WORKDIR /app

# 3) Copy & install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copy your app code
COPY . .

# 5) Run Shiny on 0.0.0.0:7860
CMD ["python", "-m", "shiny", "run", "app.py", "--host", "0.0.0.0", "--port", "7860"]
