import logging
import uuid
from typing import Dict, List
from s3_scanner import S3Scanner
from transformers.contract_transformer import ContractTransformer
from clients.openmetadata_client import OpenMetadataClient
from ai.yandex_client import YandexGPTClient
from config import OPENMETADATA_CONFIG, YANDEXGPT_CONFIG, S3_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_container_uuid_from_openmetadata(client, folder_name: str) -> str:
    """Получает UUID контейнера (S3-папки) из OpenMetadata"""
    service = S3_CONFIG.get("service_name", "s3_source")
    bucket = S3_CONFIG.get("bucket", "data-contracts")
    fqn = f"{service}.{bucket}.{folder_name}"    
    try:
        result = client._request("GET", f"containers/name/{fqn}")
        if result and result.get('id'):
            logger.info(f"   Найден UUID контейнера: {result['id'][:8]}...")
            return result['id']
    except Exception as e:
        logger.warning(f"   Контейнер {fqn} не найден: {e}")
    return None


def get_existing_contract_for_entity(client, entity_id: str) -> Dict:
    """Проверяет, есть ли контракт для папки по entity.id"""
    contracts = client.list_data_contracts()
    for contract in contracts.get('data', []):
        entity = contract.get('entity', {})
        if entity.get('id') == entity_id:
            logger.info(f"   Найден существующий контракт: {contract.get('name')}")
            return contract
    return None


def create_contract_for_folder(client, transformer, folder_meta: Dict, ai_client=None) -> bool:
    """Создаёт контракт для папки в S3"""
    try:
        folder_name = folder_meta['folder_name']
        
        logger.info(f"Обрабатываем папку: {folder_name}")
        logger.info(f"  ai_client в функции: {ai_client is not None}")
        logger.info(f"  transformer.ai_client: {transformer.ai_client is not None}")
        
        container_uuid = get_container_uuid_from_openmetadata(client, folder_name)
        
        if not container_uuid:
            logger.error(f" Не найден UUID для папки {folder_name}")
            return False
        
        existing_contract = get_existing_contract_for_entity(client, container_uuid)
        
        if existing_contract:
            logger.info(f" Контракт для папки {folder_name} уже существует: {existing_contract.get('name')}")
            return False
        
        table_meta = {
            'table_name': folder_name,
            'columns': folder_meta.get('columns', []),
            'statistics': {'row_count': folder_meta.get('row_count', 0)},
            'sample_data': folder_meta.get('sample_data', []),
            'source_type': 's3_folder',
            'file_count': folder_meta.get('file_count', 0)
        }
        
        contract_data = transformer.table_to_contract(table_meta, container_uuid, source_type="s3")
        
        contract_data['entity']['type'] = 'container'
        
        if 'description' in contract_data:
            contract_data['description'] = (
                f"{contract_data['description']} "
                f"(Источник: S3, папка: {folder_name}, файлов: {folder_meta.get('file_count', 0)})"
            )
        
        if 'schema' in contract_data:
            del contract_data['schema']
        
        # import json
        # logger.info("="*60)
        # logger.info(f"JSON для {folder_name}:")
        # logger.info(json.dumps(contract_data, indent=2, ensure_ascii=False))
        # logger.info("="*60)
        
        result = client.create_data_contract(contract_data)
        
        if result and result.get('id'):
            logger.info(f"Контракт создан для папки {folder_name} (ID: {result['id'][:8]}...)")
            return True
        else:
            logger.error(f"Ошибка создания контракта для папки {folder_name}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info(" Запуск создания контрактов для S3 (папки)...")
    
    ai_client = None
    if YANDEXGPT_CONFIG.get("folder_id") and YANDEXGPT_CONFIG.get("iam_token"):
        logger.info("Инициализация YandexGPT (IAM-токен)")
        try:
            from ai.yandex_client import YandexGPTClient
            ai_client = YandexGPTClient(
                folder_id=YANDEXGPT_CONFIG["folder_id"],
                iam_token=YANDEXGPT_CONFIG["iam_token"]
            )
            logger.info("YandexGPT инициализирован успешно!")
        except Exception as e:
            logger.error(f"Ошибка инициализации YandexGPT: {e}")
    else:
        logger.warning("YandexGPT не настроен (нет IAM-токена или folder_id)")
    
    client = OpenMetadataClient(
        base_url=OPENMETADATA_CONFIG["url"],
        token=OPENMETADATA_CONFIG["token"]
    )
    
    try:
        user = client.get_logged_in_user()
        owner_id = user.get('id')
        owner_name = user.get('name')
        logger.info(f"Текущий пользователь: {owner_name} (ID: {owner_id})")
    except Exception as e:
        logger.warning(f"Не удалось получить пользователя: {e}")
        owner_id = None
        owner_name = "admin"
    
    logger.info(" Сканируем S3")
    scanner = S3Scanner()
    folders = scanner.scan_folders()
    
    if not folders:
        logger.error(" Нет папок для обработки")
        return
    
    logger.info(f" Найдено папок: {len(folders)}")
    
    transformer = ContractTransformer(ai_client, owner_id, owner_name)
    created = 0
    skipped = 0
    
    for folder_meta in folders:
        if create_contract_for_folder(client, transformer, folder_meta, ai_client):
            created += 1
        else:
            contract_name = f"{folder_meta['folder_name']}-contract"
            existing = client.list_data_contracts()
            exists = any(c.get('name') == contract_name for c in existing.get('data', []))
            if exists:
                skipped += 1


if __name__ == "__main__":
    main()