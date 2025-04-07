import os
import logging
from ollama import Client

# === Logging Setup ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Config from Environment ===
OLLAMA_HOST = os.getenv("OLLAMA_HOST")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

def test_ollama_basic():
    logger.info(f"🧪 Testing Ollama at {OLLAMA_HOST} with model '{OLLAMA_MODEL}'...")
    client = Client(host=OLLAMA_HOST)
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "user", "content":  "Define XSS in one sentence."}
        ]
    )
    return response['message']['content']

# === Prompt Templates ===
def build_system_prompt(content: str) -> str:
    return f"""You are an expert consultant helping executive advisors to get relevant information from internal documents.

Generate your response by following the steps below:
1. Recursively break down the question into smaller questions.
2. For each question/directive:
   2a. Select the most relevant information from the context in light of the conversation history.
3. Generate a draft response using selected information.
4. Remove duplicate content from draft response.
5. Generate your final response after adjusting it to increase accuracy and relevance.
6. Do not try to summarise the answers, explain it properly.
6. Only show your final response!

Constraints:
1. DO NOT PROVIDE ANY EXPLANATION OR DETAILS OR MENTION THAT YOU WERE GIVEN CONTEXT.
2. Don't mention that you are not able to find the answer in the provided context.
3. Don't make up the answers by yourself.
4. Try your best to provide answer from the given context.

CONTENT:
{content}
"""

def build_user_prompt(question: str) -> str:
    return f"""
==============================================================
Based on the above context, please provide the answer to the following question:
{question}
"""

# === Main RAG Function ===
def generate_rag_response(content: str, question: str, model: str = OLLAMA_MODEL, host: str = OLLAMA_HOST) -> str:
    logger.info(f"🔌 Connecting to Ollama at {host} using model '{model}'")

    client = Client(host=host)
    system_prompt = build_system_prompt(content)
    user_prompt = build_user_prompt(question)

    logger.info("🧠 Sending prompt to Ollama...")
    stream = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        stream=True
    )

    full_response = ''
    for chunk in stream:
        full_response += chunk['message']['content']

    logger.info("✅ Received response from Ollama.")
    return full_response
