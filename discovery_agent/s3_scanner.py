import logging
from connectors.s3_connector import S3Connector
from config import S3_CONFIG
from collections import defaultdict

logger = logging.getLogger(__name__)

class S3Scanner:
    def __init__(self):
        self.connector = S3Connector(S3_CONFIG)
        self.bucket = S3_CONFIG.get('bucket')
        self.prefix = S3_CONFIG.get('prefix', '')
    
    def scan_folders(self):
        """Сканирует папки в S3"""
        if not self.connector.connect():
            logger.error(" Не удалось подключиться к S3")
            return []
        
        try:
            files = self.connector.list_files(self.bucket, self.prefix)
            logger.info(f" Найдено файлов: {len(files)}")
            
            folders = defaultdict(lambda: {'files': [], 'file_paths': []})
            
            for file in files:
                key = file['key']
                if '/' in key:
                    folder_name = key.split('/')[0]
                else:
                    folder_name = key.split('.')[0]
                
                folders[folder_name]['files'].append(file)
                folders[folder_name]['file_paths'].append(key)
            
            logger.info(f" Найдено папок: {len(folders)}")
            
            results = []
            for folder_name, folder_data in folders.items():
                first_file = folder_data['files'][0]
                file_data = self.connector.read_file(self.bucket, first_file['key'])
                
                if 'error' in file_data:
                    logger.warning(f" Ошибка чтения {first_file['key']}: {file_data['error']}")
                    continue
                
                results.append({
                    'folder_name': folder_name,
                    'file_count': len(folder_data['files']),
                    'files': folder_data['files'],
                    'columns': file_data.get('columns', []),
                    'row_count': file_data.get('row_count', 0),
                    'sample_data': file_data.get('sample_data', []),
                    'format': first_file['format']
                })
                
                logger.info(f" Папка {folder_name}: {len(folder_data['files'])} файлов, {len(file_data.get('columns', []))} колонок")
            return results    
        except Exception as e:
            logger.error(f" Ошибка сканирования S3: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def scan_files(self):
        """Сканирует отдельные файлы"""
        if not self.connector.connect():
            logger.error(" Не удалось подключиться к S3")
            return []
        
        try:
            files = self.connector.list_files(self.bucket, self.prefix)
            logger.info(f" Найдено файлов: {len(files)}")
            
            results = []
            for file in files:
                logger.info(f" Читаем файл: {file['key']}")
                file_data = self.connector.read_file(self.bucket, file['key'])
                
                if 'error' in file_data:
                    logger.warning(f" Ошибка чтения {file['key']}: {file_data['error']}")
                    continue
                
                results.append({
                    'file_name': file['key'].split('/')[-1],
                    'file_path': file['key'],
                    'format': file['format'],
                    'size': file['size'],
                    'last_modified': file['last_modified'],
                    'columns': file_data.get('columns', []),
                    'row_count': file_data.get('row_count', 0),
                    'sample_data': file_data.get('sample_data', []),
                    'source_type': 's3'
                })
            
            return results
            
        except Exception as e:
            logger.error(f" Ошибка сканирования S3: {e}")
            return []