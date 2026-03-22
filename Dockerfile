# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
WORKDIR /app
# Create non-root user for security compliance
RUN groupadd -r mcpUser && useradd -r -g mcpUser mcpUser
# Copy only the installed dependencies and code
COPY --from=builder /root/.local /home/mcpUser/.local
COPY ./src .
# Set environment and permissions
ENV PATH=/home/mcpUser/.local/bin:$PATH
RUN chown -R mcpUser:mcpUser /app
USER mcpUser
EXPOSE 8080
CMD ["python", "main.py"]
