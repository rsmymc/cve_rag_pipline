from flask import Flask, request, jsonify
#from generator import generate_highlights, process_highlights
from storage import upload_lecture_json_to_s3, put_highlight_record_from_json
import logging
# === Logging Config ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# === Flask Setup ===
app = Flask(__name__)

# === Routes ===
@app.route("/generate-lab", methods=["POST"])
def handle_lecture():
    try:
        data = request.get_json()
        if not data:
            logger.warning("❌ Invalid JSON received.")
            return jsonify({"error": "Invalid JSON"}), 400

        required_keys = {"lecture_id", "lecture_name", "lecture_content"}
        missing_keys = required_keys - data.keys()
        if missing_keys:
            logger.warning(f"❌ Missing fields: {missing_keys}")
            return jsonify({"error": f"Missing required fields: {', '.join(missing_keys)}"}), 400

        logger.info(f"📥 Received lecture ID {data['lecture_id']}: {data['lecture_name']}")

        #highlights = generate_highlights(data, use_existing_highlights=data.get("use_existing_highlights", False))
        result = ""
        #result = process_highlights(highlights, lecture_name=data["lecture_name"], use_existing_highlights=data.get("use_existing_highlights", False))
        logger.info(f"✅ Processed lecture_outputs and attached CVEs")

        return jsonify(result), 200

    except Exception as e:
        logger.exception("🔥 Unexpected error in /generate-lab")
        return jsonify({"error": str(e)}), 500

@app.route('/upload-lecture', methods=['POST'])
def upload_lecture():
    try:
        data = request.get_json()
        if not data:
            logger.warning("❌ Invalid JSON received.")
            return jsonify({"error": "Invalid JSON"}), 400

        required_keys = {"lecture_id", "lecture_name", "lecture_content"}
        missing_keys = required_keys - data.keys()
        if missing_keys:
            logger.warning(f"❌ Missing fields: {missing_keys}")
            return jsonify({"error": f"Missing required fields: {', '.join(missing_keys)}"}), 400

        logger.info(f"📥 Received lecture ID {data['lecture_id']}: {data['lecture_name']}")

        lecture_name = data["lecture_name"]
        s3_key = f"lectures/{lecture_name}.json"
        bucket = "cve-rag-pipline-bucket"

        upload_lecture_json_to_s3(data, bucket, s3_key)

        return jsonify({"message": f"Lecture {lecture_name} uploaded to S3"}), 200
    except Exception as e:
        logger.exception("🔥 Unexpected error in /upload-lecture")
        return jsonify({"error": str(e)}), 500

@app.route('/store-highlights', methods=['POST'])
def store_highlight():
    try:
        data = request.get_json()
        if not data:
            logger.warning("❌ Invalid JSON received.")
            return jsonify({"error": "Invalid JSON"}), 400

        # Expecting JSON in this format: {"lecture_id": "lec01", "highlights": [ ... ]}
        if not data or "lecture_id" not in data or "highlights" not in data:
            return jsonify({"error": "Required keys: lecture_id, highlights"}), 400

        lecture_id = data["lecture_id"]
        highlights = data["highlights"]

        for i, item in enumerate(highlights):
            required_fields = {"title", "discussion", "lab_opportunity"}
            missing_keys = required_fields - item.keys()
            if not required_fields.issubset(item.keys()):
                logger.warning(f"❌ Missing fields: {missing_keys}")
                return jsonify({"error": f"Missing required fields: {', '.join(missing_keys)}"}), 400

        put_highlight_record_from_json(data)

        return jsonify({"message": f"Highlight {data['lecture_id']} stored"}), 200

    except Exception as e:
        logger.exception("🔥 Unexpected error in /store-highlight")
        return jsonify({"error": str(e)}), 500

@app.route("/test-ollama", methods=["GET"])
def test_ollama_route():
    from ollama_client import test_ollama_basic

    try:
        result = test_ollama_basic()
        return jsonify({"status": "success", "response": result})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/test-chroma", methods=["POST"])
def test_chroma_query():
    try:
        data = request.get_json()
        if not data or "text" not in data:
            return jsonify({"error": "Missing 'text' in request"}), 400

        from generator import query_chromadb

        result = query_chromadb(data["text"])
        return jsonify({"result": result})
    except Exception as e:
        logger.error(f"❌ Error during ChromaDB query test: {e}")
        return jsonify({"error": str(e)}), 500

# === Entry Point ===
if __name__ == "__main__":
    logger.info("🚀 Starting cyberlab-api server on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
