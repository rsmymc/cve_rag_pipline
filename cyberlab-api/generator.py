import json
import os
import logging
import chromadb
import time
from urllib.parse import urlparse
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from ollama_client import generate_rag_response

logger = logging.getLogger(__name__)

OUTPUT_FOLDER = "lecture_outputs"

def generate_highlights(lecture_data, use_existing_highlights=False):
    content = lecture_data["lecture_content"]
    lecture_name = lecture_data["lecture_name"]

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    filename = f"{lecture_name.replace(' ', '_')}_highlights.json"
    filepath = os.path.join(OUTPUT_FOLDER, filename)

    if use_existing_highlights and os.path.exists(filepath):
        logger.info(f"📂 Using cached highlights from: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    question = """
      Based on the provided lecture content, generate 1 key lecture_outputs in the following JSON format:
            {
              "title": "<Concise and informative title>",
              "related_slides": ["<Relevant slide titles or topics>"],
              "discussion": "<Brief yet detailed explanation of the key concept>",
              "lab_opportunity": "<Hands-on exercise that reinforces the discussed concept>"
            }

            **Instructions:**
            - Ensure each highlight is unique and covers distinct aspects of the lecture.
            - Use clear and precise language for both the title and discussion.
            - The related slides should be meaningful connections to the lecture's content.
            - For lab opportunities, prioritize practical exercises that reinforce the discussed concept and are feasible for students to implement.
            - No any comment or sentence rather than provided json structure, return lecture_outputs as json array

            Focus on producing lecture_outputs that are insightful, actionable, and well-balanced across theoretical concepts and practical exercises.
    """

    logger.info("🔁 Sending content to Ollama for highlight generation...")
    response = generate_rag_response(content, question)

    try:
        cleaned_json = json.loads(response.strip().strip('"'))
    except Exception as e:
        logger.error("❌ Failed to parse lecture_outputs from Ollama response")
        raise ValueError(f"Invalid JSON response from Ollama: {e}")

    with open(filepath, "w", encoding="utf-8") as json_file:
        json.dump(cleaned_json, json_file, indent=4, ensure_ascii=False)
        logger.info(f"📝 Highlights saved to {filename}")

    return cleaned_json

# === Load environment variables ===
CHROMA_URL = os.getenv("CHROMA_URL")
COLLECTION_NAME = os.getenv("CHROMA_DB_MINILM_COLLECTION_NAME")
MODEL_NAME = os.getenv("CHROMA_DB_MINILM_MODEL_NAME")

logger.info(f"🔗 ChromaDB URL: {CHROMA_URL}")
logger.info(f"🧠 Embedding model: {MODEL_NAME}")
logger.info(f"📚 Collection: {COLLECTION_NAME}")

# === Initialize ChromaDB client and collection ===
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

embedding_function_minilm = HuggingFaceEmbeddings(model_name=MODEL_NAME)

collection = client.get_collection( name=COLLECTION_NAME)

# === ChromaDB query using highlight text ===
def query_chromadb(highlight_text):
    logger.info(f"🔍 Querying ChromaDB for highlight: '{highlight_text[:60]}...'")

    try:
        results = collection.query(
            query_texts=[highlight_text],
            n_results=1,
            include=["metadatas", "documents"]
        )
    except Exception as e:
        logger.error(f"❌ ChromaDB query failed: {e}")
        return None

    if results and results.get("documents") and results["documents"][0]:
        match = {
            "page_content": results["documents"][0][0],
            "metadata": results["metadatas"][0][0]
        }
        logger.info(f"✅ Found match: {match['metadata'].get('cve_id', 'N/A')}")
        return [match]
    else:
        logger.warning("⚠️ No results returned from ChromaDB")
        return None

# === Ask Ollama to generate a lab setup for a CVE-highlight combo ===
def generate_lab_experience(cve_data, cybersecurity_topic):
    content = f"""
    Here is a cybersecurity highlight I would like to introduce in my class.

    Title: {cybersecurity_topic["title"]}

    Related Slides: {cybersecurity_topic["related_slides"]}

    Discussion: {cybersecurity_topic["discussion"]}

    Lab Opportunity: {cybersecurity_topic["lab_opportunity"]}

    Related CVE: {cve_data[0]["metadata"]["cve_id"]}
    Description: {cve_data[0]["page_content"]}
    """

    question = """
    Can you generate a basic lab setup for this CVE to help students understand its exploitation and mitigation? 
    generate in the following JSON format:
            {
              "vulnerable_code": "A vulnerable code example demonstrating the issue.",
              "fixed_version": "A fixed version of the code.",
              "docker_file": "A Dockerfile to set up and run the lab"
            }

    **Instructions:**
    - No any comment or sentence rather than provided JSON format as above and no any comment or explanation in the content of codes and docker file, return as json format
    - Return only valid JSON without extra formatting or markdown.
    """

    response = generate_rag_response(content, question)

    try:
        return json.loads(response.strip().strip('"'))
    except Exception as e:
        logger.error(f"❌ Failed to parse lab response: {e}")
        return {"error": "Lab generation failed"}

# === Main function to enrich lecture_outputs ===
def process_highlights(highlights, lecture_name=None, use_existing_highlights=False):
    if lecture_name:
        filename = f"{lecture_name.replace(' ', '_')}_labs.json"
        filepath = os.path.join(OUTPUT_FOLDER, filename)

        # If flag is set AND file exists — use it
        if use_existing_highlights and os.path.exists(filepath):
            logger.info(f"📂 Loading enriched labs from cache: {filepath}")
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)

    #Otherwise process highlights

    if isinstance(highlights, str):
        try:
            highlights_json = json.loads(highlights.strip().strip('"'))
        except Exception as e:
            logger.error(f"❌ Failed to parse lecture_outputs JSON: {e}")
            raise
    else:
        highlights_json = highlights  # already parsed

    for highlight in highlights_json:
        discussion = highlight.get("discussion", "")
        cve_match = query_chromadb(discussion)

        if cve_match:
            highlight["cve_match"] = cve_match
            highlight["lab_experience"] = generate_lab_experience(cve_match, highlight)
        else:
            highlight["cve_match"] = None
            highlight["lab_experience"] = "No related CVE found."

        # === Save enriched lecture_outputs if lecture_name is provided ===
    if lecture_name:
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(highlights_json, f, indent=4, ensure_ascii=False)
            logger.info(f"📦 Enriched lecture_outputs saved to {filepath}")

    return highlights_json