import os
import time
import uuid
import logging
import chromadb
from urllib.parse import urlparse
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from document_loader import read_all_json_documents
from embedding_wrapper import ChromaCompatibleEmbeddingFunction

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Environment Configuration ===
CHROMA_URL = os.getenv("CHROMA_URL")
COLLECTION_NAME = os.getenv("CHROMA_DB_MINILM_COLLECTION_NAME")
MODEL_NAME = os.getenv("CHROMA_DB_MINILM_MODEL_NAME")
CVES_FOLDER_PATH = os.getenv("CVES_FOLDER_PATH")

logger.info(f"🔗 ChromaDB URL: {CHROMA_URL}")
logger.info(f"📁 CVEs folder: {CVES_FOLDER_PATH}")
logger.info(f"🧠 Embedding model: {MODEL_NAME}")
logger.info(f"📚 Collection: {COLLECTION_NAME}")

# === Wait for ChromaDB to be ready ===
def wait_for_chromadb(host: str, port: int) -> chromadb.HttpClient:
    while True:
        try:
            client = chromadb.HttpClient(
                host=host,
                port=port,
                settings=Settings(allow_reset=False)
            )
            client.list_collections()
            logger.info("✅ Connected to ChromaDB")
            return client
        except Exception:
            logger.warning("⏳ Waiting for ChromaDB...")
            time.sleep(2)

parsed_url = urlparse(CHROMA_URL)
client = wait_for_chromadb(parsed_url.hostname, parsed_url.port)

# === Text Splitting and Indexing ===
def index_documents_into_chroma(collection, documents, chunk_size=1000, chunk_overlap=200):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    chunks = text_splitter.split_documents(documents)

    logger.info(f"📦 Indexing {len(chunks)} chunks...")
    for doc in chunks:
        collection.add(
            ids=[str(uuid.uuid4())],
            metadatas=[doc.metadata],
            documents=[doc.page_content]
        )

# === Main index build ===
def build_chroma_index():
    logger.info("🚀 Loading embedding model...")
    embedder = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    embedding_fn = ChromaCompatibleEmbeddingFunction(embedder)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn
    )

    documents = read_all_json_documents(CVES_FOLDER_PATH)
    index_documents_into_chroma(collection, documents)

# === Entry point ===
if __name__ == "__main__":
    start = time.time()
    logger.info(f"🕓 Starting indexing at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    build_chroma_index()
    duration = time.time() - start
    logger.info(f"✅ Done in {duration:.2f} seconds")
