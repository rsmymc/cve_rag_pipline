import os
import json
from langchain_core.documents import Document

def process_json_to_document(file_path):
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)

        cve_id = data.get("cveMetadata", {}).get("cveId", "Unknown ID")
        description = data.get("containers", {}).get("cna", {}).get("descriptions", [{}])[0].get("value", "No description provided")
        references = data.get("containers", {}).get("cna", {}).get("references", [])
        ref_urls = [ref.get("url") for ref in references]

        page_content = f"Description: {description}\nReferences: {', '.join(ref_urls)}"
        metadata = {
            "cve_id": cve_id,
            "source_file": file_path
        }

        return Document(page_content=page_content, metadata=metadata)

    except Exception as e:
        print(f"❌ Failed to process {file_path}: {e}")
        return None

def read_all_json_documents(root_folder):
    documents = []
    for subdir, _, files in os.walk(root_folder):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(subdir, file)
                doc = process_json_to_document(file_path)
                if doc:
                    documents.append(doc)
    return documents
