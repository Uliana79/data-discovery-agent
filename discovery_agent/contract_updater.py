from typing import List, Dict
import logging
from scanner import Scanner
from clients.openmetadata_client import OpenMetadataClient
from transformers.contract_transformer import ContractTransformer
from config import OPENMETADATA_CONFIG, SOURCE_DB_CONFIG
from transformers.contract_transformer import normalize_sql_type

logger = logging.getLogger(__name__)

def normalize_data_type(data_type: str) -> str:
    """Приводит тип данных к единому формату для сравнения"""
    if not data_type:
        return ''
    
    t = data_type.lower().strip()
    t = t.split('(')[0]
    t = t.replace(' without time zone', '')
    t = t.replace(' with time zone', '')
    
    type_map = {
        'int': 'integer',
        'int4': 'integer',
        'int8': 'bigint',
        'smallint': 'smallint',
        'bigint': 'bigint',
        'varchar': 'varchar',
        'character varying': 'varchar',
        'char': 'char',
        'text': 'text',
        'timestamp': 'timestamp',
        'timestamptz': 'timestamp',
        'date': 'date',
        'boolean': 'boolean',
        'bool': 'boolean',
        'numeric': 'numeric',
        'decimal': 'numeric',
        'float': 'float',
        'double precision': 'double',
        'json': 'json',
        'jsonb': 'json',
        'uuid': 'uuid'
    }
    
    return type_map.get(t, t)

def compare_schemas(postgres_columns: List[Dict], om_columns: List[Dict]) -> Dict:
    """Сравнивает схему из PostgreSQL и OpenMetadata"""
    
    def normalize_field(col):
        name = col.get('name', '').lower()
        raw_type = col.get('data_type') or col.get('dataType', '')
        normalized = normalize_sql_type(raw_type)
        
        return {
            'name': name,
            'data_type': normalized
        }
    
    pg_fields = {normalize_field(c)['name']: normalize_field(c) for c in postgres_columns}
    om_fields = {normalize_field(c)['name']: normalize_field(c) for c in om_columns}
    
    added = set(pg_fields.keys()) - set(om_fields.keys())
    removed = set(om_fields.keys()) - set(pg_fields.keys())
    
    changed = []
    for name in set(pg_fields.keys()) & set(om_fields.keys()):
        pg_type = pg_fields[name].get('data_type', '')
        om_type = om_fields[name].get('data_type', '')
        if pg_type != om_type:
            changed.append({
                'field': name,
                'old_type': om_type,
                'new_type': pg_type
            })
            logger.info(f"   Изменён тип {name}: {om_type} → {pg_type}")
    
    result = {
        'has_changes': bool(added or removed or changed),
        'added': list(added),
        'removed': list(removed),
        'changed': changed
    }
    
    logger.info(f"  Результат: has_changes={result['has_changes']}")
    return result

def check_all_contracts() -> List[Dict]:
    """Проверяет все контракты на наличие изменений"""
    logger.info(" Начинаем проверку контрактов...")
    
    client = OpenMetadataClient(
        base_url=OPENMETADATA_CONFIG["url"],
        token=OPENMETADATA_CONFIG["token"]
    )
    
    contracts_response = client.list_data_contracts()
    contracts = contracts_response.get('data', [])
    logger.info(f" Найдено контрактов: {len(contracts)}")
    
    contract_by_entity = {}
    for contract in contracts:
        entity = contract.get('entity', {})
        entity_id = entity.get('id')
        if entity_id:
            contract_by_entity[entity_id] = contract
            logger.info(f"  Контракт {contract.get('name')} → entity_id: {entity_id[:8]}...")
    
    scanner = Scanner()
    tables_metadata = scanner.scan_all_tables()
    logger.info(f" Найдено таблиц: {len(tables_metadata)}")
    
    results = []
    for table in tables_metadata:
        table_name = table['table_name']
        service = SOURCE_DB_CONFIG.get("service_name", "postgres_source")
        database = SOURCE_DB_CONFIG.get("database", "source_db")
        schema = SOURCE_DB_CONFIG.get("schema", "public")
        fqn = f"{service}.{database}.{schema}.{table_name}"
        
        logger.info(f" Проверяем таблицу: {table_name}")
        
        table_info = client.get_table_by_name(fqn)
        if table_info and table_info.get('id'):
            table_uuid = table_info.get('id')
            has_contract = table_uuid in contract_by_entity
            existing_contract = contract_by_entity.get(table_uuid)
            
            logger.info(f"  UUID: {table_uuid[:8]}..., контракт: {has_contract}")
            
            if has_contract and existing_contract:
                om_schema = existing_contract.get('schema', [])
                pg_schema = table['columns']
                logger.info(f"  Сравниваем схемы: PG={len(pg_schema)} полей, Contract={len(om_schema)} полей")
                diff = compare_schemas(pg_schema, om_schema)
                logger.info(f"  Результат сравнения: has_changes={diff.get('has_changes')}")
            else:
                diff = {'has_changes': False}
                logger.info(f"  Контракта нет или не найден entity_id")
        else:
            has_contract = False
            diff = {'has_changes': False}
            logger.info(f"  Таблица {table_name} не найдена в OpenMetadata")
        
        results.append({
            'table_name': table_name,
            'columns': table['columns'],
            'statistics': table['statistics'],
            'has_contract': has_contract,
            'contract_id': existing_contract.get('id') if has_contract else None,
            'contract_name': existing_contract.get('name') if has_contract else None,
            'diff': diff,
            'needs_update': has_contract and diff['has_changes']
        })
    
    return results

def update_contract_schema(contract_id: str) -> Dict:
    """Обновляет схему контракта по entity.id"""
    try:
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        transformer = ContractTransformer()
        
        contract = client.get_data_contract(contract_id)
        if not contract:
            return {'success': False, 'error': 'Контракт не найден'}
        
        entity = contract.get('entity', {})
        table_uuid = entity.get('id')
        
        if not table_uuid:
            logger.error(f" У контракта нет entity.id")
            return {'success': False, 'error': 'У контракта нет привязки к таблице'}
        
        logger.info(f" Ищем таблицу по UUID: {table_uuid}")
        
        table_info = client._request("GET", f"tables/{table_uuid}")
        
        if not table_info:
            logger.error(f" Таблица с UUID {table_uuid} не найдена")
            return {'success': False, 'error': 'Таблица не найдена в OpenMetadata'}
        
        table_name = table_info.get('name', '')
        logger.info(f" Таблица: {table_name}")
        
        scanner = Scanner()
        tables = scanner.scan_all_tables()
        table_meta = next((t for t in tables if t['table_name'] == table_name), None)
        
        if not table_meta:
            logger.error(f" Таблица {table_name} не найдена в PostgreSQL")
            return {'success': False, 'error': f'Таблица {table_name} не найдена'}
        
        new_schema = transformer._generate_schema(
            table_meta['columns'], 
            {}, 
            []
        )
        
        patch_data = [
            {
                "op": "replace",
                "path": "/schema",
                "value": new_schema
            }
        ]
        
        logger.info(f" Обновляем схему для {table_name} ({len(new_schema)} полей)")
        
        result = client._request(
            "PATCH", 
            f"dataContracts/{contract_id}", 
            patch_data,
            patch=True
        )
        
        if result:
            return {'success': True, 'message': f'Контракт для {table_name} обновлён'}
        else:
            return {'success': False, 'error': 'Ошибка обновления'}
            
    except Exception as e:
        logger.error(f" Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}