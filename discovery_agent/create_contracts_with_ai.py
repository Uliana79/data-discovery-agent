import logging
from typing import List, Dict
from scanner import Scanner
from transformers.contract_transformer import ContractTransformer
from clients.openmetadata_client import OpenMetadataClient
from ai.yandex_client import YandexGPTClient
from config import SOURCE_DB_CONFIG, OPENMETADATA_CONFIG, YANDEXGPT_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_table_uuid(client, table_name: str) -> str:
    service = SOURCE_DB_CONFIG.get("service_name", "postgres_source")
    database = SOURCE_DB_CONFIG.get("database", "source_db")
    schema = SOURCE_DB_CONFIG.get("schema", "public")
    fqn = f"{service}.{database}.{schema}.{table_name}"
    try:
        result = client.get_table_by_name(fqn)
        if result and result.get("id"):
            return result["id"]
    except Exception as e:
        logger.error(f"Ошибка получения UUID для {table_name}: {e}")
    return None


def get_existing_contract_for_entity(client, entity_id: str) -> Dict:
    """Проверяет, есть ли контракт по entity.id"""
    contracts = client.list_data_contracts()
    for contract in contracts.get('data', []):
        entity = contract.get('entity', {})
        if entity.get('id') == entity_id:
            return contract
    return None


def main():    
    ai_client = None
    if YANDEXGPT_CONFIG.get("folder_id") and YANDEXGPT_CONFIG.get("iam_token"):
        logger.info("Инициализация YandexGPT")
        ai_client = YandexGPTClient(
            folder_id=YANDEXGPT_CONFIG["folder_id"],
            iam_token=YANDEXGPT_CONFIG["iam_token"]
        )
    else:
        logger.warning("YandexGPT не настроен")
    
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
    
    logger.info(" Сканируем PostgreSQL")
    scanner = Scanner()
    tables_metadata = scanner.scan_all_tables()
    
    if not tables_metadata:
        logger.error(" Нет данных")
        return
    
    logger.info(f" Найдено таблиц: {len(tables_metadata)}")
        
    transformer = ContractTransformer(ai_client, owner_id, owner_name)
    
    created = []
    skipped = []
    
    for table_meta in tables_metadata:
        table_name = table_meta["table_name"]
        
        table_uuid = get_table_uuid(client, table_name)
        if not table_uuid:
            logger.warning(f" Не найден UUID для {table_name}")
            continue
        
        existing_contract = get_existing_contract_for_entity(client, table_uuid)
        
        if existing_contract:
            logger.info(f" Контракт для {table_name} уже существует (ID: {existing_contract.get('id')[:8]}...)")
            skipped.append(table_name)
            continue
        
        logger.info(f" Создаём контракт для {table_name}")
        
        contract_data = transformer.table_to_contract(table_meta, table_uuid)
        result = client.create_data_contract(contract_data)
        
        if result and result.get("id"):
            created.append({
                "table": table_name,
                "contract_id": result.get("id"),
                "status": result.get("entityStatus", "Draft")
            })
            logger.info(f" Контракт создан: {table_name}")
        else:
            logger.error(f" Ошибка создания для {table_name}")

if __name__ == "__main__":
    main()