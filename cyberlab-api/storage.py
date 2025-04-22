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
