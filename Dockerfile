# ===============================
# Stage 1: Base
# ===============================
FROM python:3.10-slim

# Disable buffering for logs
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    ghostscript \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy your project files
COPY  chat_service.py llm_providers.py requirements.txt diagrams.zip  ./
COPY .env diagrams ./        
#COPY data ./data     # optional: if you have sample manuals or diagrams

RUN unzip diagrams.zip  && rm diagrams.zip 

# ===============================
# Stage 2: Python dependencies
# ===============================
RUN pip install --upgrade pip

# Install Python dependencies (add more if you use extra libs)
RUN pip install --no-cache-dir \
    flask flask-cors elasticsearch==8.19.1 requests python-dotenv tenacity tqdm \
    pymupdf pdfminer.six pdfplumber camelot-py[cv] pypdfium2 DBUtils pymysql python-pptx \
    && pip cache purge

# ===============================
# Stage 3: Entrypoint Configuration
# ===============================
# Default port (can override via .env)
EXPOSE 7001

# Environment variables (override at runtime)
ENV DOCS_ROOT=/data/manuals \
    ES_HOST=http://11.10.1.134:9200 \
    PORT=7001

# Run command — can be overridden by Docker Compose
CMD ["python", "chat_service.py"]

