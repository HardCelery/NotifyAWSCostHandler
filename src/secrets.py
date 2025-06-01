import os
import json
import boto3 # type: ignore

def get_line_access_token() -> str:
    region = os.environ.get("AWS_REGION", "ap-northeast-1")
    secret_name = os.environ.get("SECRET_NAME", "linebot/credentials")

    secrets_client = boto3.client('secretsmanager', region_name=region)
    secret = secrets_client.get_secret_value(SecretId=secret_name)
    secret_dict = json.loads(secret['SecretString'])
    return secret_dict['LINE_ACCESS_TOKEN']

