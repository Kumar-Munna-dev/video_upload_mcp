# Small Python image that runs the MCP server as a web server
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY youtube_mcp.py .
CMD ["python", "youtube_mcp.py", "http"]
