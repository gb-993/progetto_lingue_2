FROM python:3.11-slim

# Environment variables to improve Python behaviour
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory inside the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy project code into the container
COPY . /app

# Copy entrypoint script and mark it as executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the port used by Gunicorn
EXPOSE 8000

# Entrypoint will run database migrations, collect static files and start Gunicorn
ENTRYPOINT ["/entrypoint.sh"]