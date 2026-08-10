#!/bin/bash
# Start the FastAPI backend and the Streamlit frontend together.
set -e

# Start the API in the background
uvicorn harness.api.app:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Give the API a moment to come up before Streamlit starts calling it
sleep 3

# Start Streamlit in the foreground (keeps the container alive)
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true

# If Streamlit exits, stop the API too
kill $API_PID
