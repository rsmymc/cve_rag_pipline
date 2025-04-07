#!/bin/bash

# Step 1: Start Ollama server in the background
ollama serve &
OLLAMA_PID=$!

# Step 2: Wait until port 11434 is open (no curl required)
echo "⏳ Waiting for Ollama to start..."
until (echo > /dev/tcp/localhost/11434) >/dev/null 2>&1; do
  sleep 1
done
echo "✅ Ollama is ready."

IFS=','
# Step 3: Pull models
DEFAULT_MODELS=${DEFAULT_OLLAMA_MODELS:-mistral}
for model in $DEFAULT_MODELS; do
    if ollama list | grep -q "$model"; then
        echo "✅ Model '$model' already pulled."
    else
        echo "⏬ Pulling model: $model"
        ollama pull "$model"
    fi
done

# Step 4: Keep Ollama server running in foreground
wait $OLLAMA_PID
