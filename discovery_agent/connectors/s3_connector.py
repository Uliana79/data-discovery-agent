import boto3
from botocore.client import Config
import pandas as pd
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class S3Connector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
    
    def connect(self):
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=self.config.get('endpoint_url', 'http://localhost:9000'),
                aws_access_key_id=self.config.get('access_key', 'minioadmin'),
                aws_secret_access_key=self.config.get('secret_key', 'minioadmin'),
                config=Config(signature_version='s3v4'),
                region_name=self.config.get('region', 'us-east-1')
            )
            logger.info(f"Подключено к S3: {self.config.get('endpoint_url')}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к S3: {e}")
            return False
    
    def list_files(self, bucket: str, prefix: str = "") -> List[Dict[str, Any]]:
        """Списывает файлы в bucket"""
        if not self.client:
            raise Exception("Нет активного соединения")
        
        try:
            response = self.client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            files = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if any(key.endswith(ext) for ext in ['.csv', '.parquet', '.json', '.avro']):
                    files.append({
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'format': self._detect_format(key)
                    })
            return files
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов: {e}")
            return []
    
    def read_file(self, bucket: str, key: str, limit: int = 100) -> Dict[str, Any]:
        """Читает файл и возвращает структуру"""
        if not self.client:
            raise Exception("Нет активного соединения")
        
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
            
            format_type = self._detect_format(key)
            
            if format_type == 'csv':
                df = pd.read_csv(io.BytesIO(content), nrows=limit)
            elif format_type == 'parquet':
                df = pd.read_parquet(io.BytesIO(content))
            elif format_type == 'json':
                df = pd.read_json(io.BytesIO(content), lines=True, nrows=limit)
            else:
                return {'error': f'Unsupported format: {format_type}'}
            
            columns = []
            for col in df.columns:
                columns.append({
                    'name': col,
                    'data_type': str(df[col].dtype),
                    'sample_values': df[col].head(5).tolist()
                })
            
            return {
                'format': format_type,
                'columns': columns,
                'row_count': len(df),
                'sample_data': df.head(5).to_dict('records')
            }
        except Exception as e:
            logger.error(f"Ошибка чтения файла {key}: {e}")
            return {'error': str(e)}
    
    def _detect_format(self, key: str) -> str:
        """Определяет формат файла по расширению"""
        if key.endswith('.csv'):
            return 'csv'
        elif key.endswith('.parquet'):
            return 'parquet'
        elif key.endswith('.json'):
            return 'json'
        elif key.endswith('.avro'):
            return 'avro'
        return 'unknown'