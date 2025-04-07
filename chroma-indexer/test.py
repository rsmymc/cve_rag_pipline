import chromadb
from urllib.parse import urlparse
from chromadb.config import Settings

chroma_url = "http://chromadb:8000"  # Use localhost when running outside Docker
parsed = urlparse(chroma_url)

client = chromadb.HttpClient(
    host=parsed.hostname,
    port=parsed.port,
    settings=Settings()
)

# List all collections
collections = client.list_collections()
for col in collections:
    print(f"Collection: {col.name}")

    try:
        count = col.count()
        print(f" - Item count: {count}")
        print(f" - Sample: {col.peek()}")
    except Exception as e:
        print(f" - Error accessing collection: {e}")
