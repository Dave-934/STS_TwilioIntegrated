# Use an official Python 3.11 image as the base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install uv, the fast package installer
RUN pip install uv

# Install the small, CPU-only version of PyTorch. This avoids the large NVIDIA packages.
RUN uv pip install --system --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the packages from your updated requirements.txt
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the rest of your project files into the container
COPY . .

# This is the command that will run when the container starts
CMD ["python", "telephony_agent.py", "start"]
