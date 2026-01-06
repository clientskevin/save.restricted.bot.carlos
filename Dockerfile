# Set the base image
FROM python:3.11-slim AS base

# Install required system packages
# Add non-free repository for unrar and install packages
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free" > /etc/apt/sources.list.d/non-free.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git build-essential python3-dev unrar && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file to the working directory
COPY . .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r no_deps_requirements.txt --no-deps

# Set the command to run the Python script
CMD [ "python", "main.py" ]