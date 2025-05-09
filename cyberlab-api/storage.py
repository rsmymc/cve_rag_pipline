import json
import boto3
from datetime import datetime

# S3 client
s3 = boto3.client('s3')

def upload_lecture_json_to_s3(json_data, bucket_name, s3_key):
    """
    Uploads a JSON object (dict) directly to S3 as a file.
    """
    json_string = json.dumps(json_data, indent=2)
    s3.put_object(
        Body=json_string,
        Bucket=bucket_name,
        Key=s3_key,
        ContentType='application/json'
    )
    print(f"[S3] Uploaded JSON to s3://{bucket_name}/{s3_key}")

def download_from_s3(bucket_name, s3_key, local_file_path):
    """Downloads a file from S3 to local path."""
    s3.download_file(bucket_name, s3_key, local_file_path)
    print(f"[S3] Downloaded s3://{bucket_name}/{s3_key} to {local_file_path}")


# DynamoDB table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('CyberlabHighlights')

def put_highlight_record_from_json(data: dict):

    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow().isoformat()

    table.put_item(Item=data)
    print(f"[DynamoDB] Stored highlight in lecture {data['lecture_id']}")

def put_multiple_highlights(highlights: list):
    for h in highlights:
        put_highlight_record_from_json(h)

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
