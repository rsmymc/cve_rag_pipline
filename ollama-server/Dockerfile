FROM ollama/ollama

COPY ollama-init.sh /ollama-init.sh
RUN chmod +x /ollama-init.sh

ENTRYPOINT [ "/bin/sh", "-c", "/ollama-init.sh" ]
