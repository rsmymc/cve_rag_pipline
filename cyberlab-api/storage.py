import os
import json
import boto3
import logging
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# === Logging Config ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# S3 client
s3 = boto3.client('s3')

S3_BUCKET = os.getenv("S3_BUCKET", "default-bucket-name")
S3_PREFIX = os.getenv("S3_PREFIX", "lectures/")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "CyberlabHighlights")

def upload_lecture_json_to_s3(lecture_name, json_data):
    """
    Uploads a JSON object (dict) directly to S3 as a file.
    """
    json_string = json.dumps(json_data, indent=2)

    s3_key = f"{S3_PREFIX}{lecture_name}.json"

    s3.put_object(
        Body=json_string,
        Bucket=S3_BUCKET,
        Key=s3_key,
        ContentType='application/json'
    )
    logger.info(f"[S3] Uploaded JSON to s3://{S3_BUCKET}/{s3_key}")

def download_from_s3(lecture_name, local_file_path):
    """Downloads a file from S3 to local path."""

    s3_key = f"{S3_PREFIX}{lecture_name}.json"

    s3.download_file(S3_BUCKET, s3_key, local_file_path)
    logger.info(f"[S3] Downloaded s3://{S3_BUCKET}/{s3_key} to {local_file_path}")

def load_json_from_s3(lecture_name):
    try:
        s3_key = f"{S3_PREFIX}{lecture_name}.json"
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        logger.warning(f"⚠️ Failed to read {lecture_name} from S3: {e}")
        return None

# DynamoDB table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

def put_highlight(data: dict):

    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat()

    table.put_item(Item=data)
    print(f"[DynamoDB] Stored highlight in lecture {data['lecture_id']}")

def put_multiple_highlights(highlights: list):
    for h in highlights:
        put_highlight(h)

def get_highlight(lecture_id: str, highlight_id: str):
    """
    Retrieve a specific highlight by lecture_id and highlight_id.
    """
    response = table.get_item(Key={"lecture_id": lecture_id, "highlight_id": highlight_id})
    return response.get("Item")

def query_highlights_by_lecture(lecture_id: str):
    """
    Retrieve all highlights for a specific lecture_id.
    """
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('lecture_id').eq(lecture_id)
    )
    return response.get("Items", [])
