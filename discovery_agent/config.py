import os
from dotenv import load_dotenv

load_dotenv()

SOURCE_DB_CONFIG = {
    "host": os.getenv("SOURCE_DB_HOST", "localhost"),
    "port": int(os.getenv("SOURCE_DB_PORT", 5433)),
    "user": os.getenv("SOURCE_DB_USER", "source_user"),
    "password": os.getenv("SOURCE_DB_PASSWORD", "source_pass"),
    "database": os.getenv("SOURCE_DB_NAME", "source_db"),
    "service_name": os.getenv("SOURCE_DB_SERVICE_NAME", "postgres_source"),
    "schema": os.getenv("SOURCE_DB_SCHEMA", "public")
}

S3_CONFIG = {
    "endpoint_url": os.getenv("S3_ENDPOINT", "http://localhost:9000"),
    "access_key": os.getenv("S3_ACCESS_KEY", "minioadmin"),
    "secret_key": os.getenv("S3_SECRET_KEY", "minioadmin"),
    "bucket": os.getenv("S3_BUCKET", "data-contracts"),
    "prefix": os.getenv("S3_PREFIX", ""),
    "region": os.getenv("S3_REGION", "us-east-1"),
    "service_name": os.getenv("S3_SERVICE_NAME", "s3_source")
}

raw_token = os.getenv("OPENMETADATA_TOKEN", "")
if not raw_token:
    raw_token = os.environ.get("OPENMETADATA_TOKEN", "")

OPENMETADATA_CONFIG = {
    "url": os.getenv("OPENMETADATA_URL", "http://localhost:8585"),
    "token": raw_token.strip().replace('\r', '').replace('\n', '').replace(' ', '')
}

if not OPENMETADATA_CONFIG["token"]:
    print("Токен OpenMetadata не найден!")
    
YANDEXGPT_CONFIG = {
    "folder_id": os.getenv("YANDEX_FOLDER_ID", ""),
    "iam_token": os.getenv("YANDEX_IAM_TOKEN", ""),         
    "model": os.getenv("YANDEXGPT_MODEL", "yandexgpt-lite")
}