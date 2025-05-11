#!/bin/sh

# Start the Ollama service in the background
ollama serve &

# Wait a few seconds for the server to come online
sleep 10

# Pull the model
ollama pull gemma:2b

# Keep the server running in the foreground
tail -f /dev/null
