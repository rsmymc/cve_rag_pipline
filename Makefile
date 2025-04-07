# === Docker Compose Commands ===
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

logs-indexer:
	docker compose logs -f chroma-indexer

# === Chroma Indexer Commands ===
run-indexer:
	docker exec -it chroma-indexer python indexer.py

# === Cleanup ===
clean:
	docker-compose down -v
	rm -rf chroma_data

# === Ollama Commands ===
pull:
	docker exec -it ollama ollama pull $(MODEL)
