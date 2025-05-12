from langchain.text_splitter import RecursiveCharacterTextSplitter
from document_loader import read_all_s3_documents
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

chunk_size=1000
chunk_overlap=200
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    length_function=len
)

documents = read_all_s3_documents()
chunks = text_splitter.split_documents(documents)

for doc in chunks:
    metadatas=[doc.metadata]
    documents=[doc.page_content]
    logger.info(f"metadatas: {metadatas} documents :{metadatas}")


logger.info(f"📦 Indexing {len(chunks)} chunks...")
