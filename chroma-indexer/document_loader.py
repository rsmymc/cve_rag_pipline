import os
import json
import boto3
import logging
from langchain_core.documents import Document

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

def process_s3_json_to_document(data: dict, s3_key: str) -> Document | None:
    try:
        cve_id = data.get("cveMetadata", {}).get("cveId", "Unknown ID")
        description = data.get("containers", {}).get("cna", {}).get("descriptions", [{}])[0].get("value", "No description provided")
        references = data.get("containers", {}).get("cna", {}).get("references", [])
        ref_urls = [ref.get("url") for ref in references]

        page_content = f"Description: {description}\nReferences: {', '.join(ref_urls)}"
        metadata = {
            "cve_id": cve_id,
            "source_s3_key": s3_key
        }

        return Document(page_content=page_content, metadata=metadata)

    except Exception as e:
        print(f"❌ Failed to process {s3_key}: {e}")
        return None

def read_all_s3_documents():
    documents = []
    bucket = os.getenv("S3_BUCKET", "cve-rag-pipline-bucket")
    prefix = os.getenv("S3_PREFIX", "cves/2025/")
    logger.info(f"📦 Reading from S3 bucket: {bucket}, prefix: {prefix}")

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    total_files = 0
    total_success = 0
    total_failed = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                total_files += 1
                try:
                    response = s3.get_object(Bucket=bucket, Key=key)
                    content = response["Body"].read()
                    data = json.loads(content)
                    doc = process_s3_json_to_document(data, key)
                    if doc:
                        documents.append(doc)
                        total_success += 1
                    else:
                        logger.warning(f"⚠️ No document returned for: {key}")
                except Exception as e:
                    total_failed += 1
                    logger.error(f"❌ Failed to process {key}: {e}")

    logger.info(
        f"✅ S3 read complete: {total_success} documents loaded, {total_failed} failed, out of {total_files} files.")
    return documents