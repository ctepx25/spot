# Use an official lightweight Python image
FROM python:3.9-slim

# Set system environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (including curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Ensure the entrypoint script is executable
RUN chmod +x entrypoint.sh

# Expose Flask's default port
EXPOSE 5000

# Declare a volume for persisting the SQLite tracking history database
VOLUME ["/app/data"]

# Define environment variable placeholders (can be overridden at runtime)
ENV SPOT_FEED_ID="0FOq6U5ICzOEL4qCqbM8YrAOqUzP8uGUp" \
    TELEGRAM_BOT_TOKEN="" \
    TELEGRAM_CHAT_ID="" \
    POLL_INTERVAL="60"

# Use the entrypoint script to launch both the daemon and Flask dashboard
ENTRYPOINT ["./entrypoint.sh"]
