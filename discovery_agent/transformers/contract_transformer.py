from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

def normalize_sql_type(sql_type: str) -> str:
    """Приводит тип к единому формату для сравнения"""
    if not sql_type:
        return "STRING"
    
    clean_type = sql_type.lower().split('(')[0]
    
    if clean_type.upper() in ["INT", "BIGINT", "SMALLINT", "VARCHAR", "TEXT", "CHAR", 
                              "BOOLEAN", "DATE", "TIMESTAMP", "DECIMAL", "NUMERIC", 
                              "FLOAT", "DOUBLE", "JSON", "UUID"]:
        return clean_type.upper()
    
    return TYPE_MAP.get(clean_type, "STRING")
  
TYPE_MAP = {
    "integer": "INT",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "serial": "INT",
    "bigserial": "BIGINT",
    "varchar": "VARCHAR",
    "character varying": "VARCHAR",
    "text": "TEXT",
    "char": "CHAR",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMP",
    "timestamptz": "TIMESTAMP",
    "decimal": "DECIMAL",
    "numeric": "NUMERIC",
    "real": "FLOAT",
    "double precision": "DOUBLE",
    "json": "JSON",
    "jsonb": "JSON",
    "uuid": "UUID"
}

class ContractTransformer:
    def __init__(self, ai_client=None, owner_id: str = None, owner_name: str = "admin"):
        self.ai_client = ai_client
        self.owner_id = owner_id
        self.owner_name = owner_name
    
    def table_to_contract(self, table_metadata: Dict[str, Any], table_uuid: str, source_type: str = "postgres") -> Dict[str, Any]:
        table_name = table_metadata["table_name"]
        columns = table_metadata.get("columns", [])
        
        description = self._generate_ai_description(table_name, columns, source_type)
        
        if not description:
            description = self._generate_description_from_structure(table_name, columns, source_type)
        
        contract = {
            "name": f"{table_name}-contract",
            "description": description,
            "entity": {
                "id": table_uuid,
                "type": "table"
            },
            "entityStatus": "Draft",
            "schema": self._generate_schema(columns, {}, [])
        }
        
        contract = self._add_owners(contract)
        contract = self._add_sla(contract, table_name)
        
        return contract
    
    def _generate_ai_description(self, table_name: str, columns: List[Dict], source_type: str = "postgres") -> str:
        """Генерирует AI-описание"""    
        if self.ai_client:
            try:
                logger.info(f"Вызываем AI для {table_name}...")
                description = self.ai_client.generate_table_description(table_name, columns, source_type)
                if description:
                    logger.info(f"AI-описание получено: {description[:100]}...")
                    return description
                else:
                    logger.warning(f"AI вернул пустое описание для {table_name}")
            except Exception as e:
                logger.error(f"Ошибка AI: {e}")
        else:
            logger.warning(f"ai_client отсутствует для {table_name}")
        
        return None
    
      
    def _generate_schema(self, columns: List[Dict], field_semantics: Dict = None, pii_columns: List = None) -> List[Dict]:
        """Генерирует структуру полей для контракта"""
        if field_semantics is None:
            field_semantics = {}
        if pii_columns is None:
            pii_columns = []
        
        schema = []
        for col in columns:
            field = {
                "name": col.get("name", ""),
                "dataType": normalize_sql_type(col.get("data_type") or col.get("dataType", ""))
            }
            
            if col.get("is_primary_key") or col.get("constraint") == "PRIMARY_KEY":
                field["constraint"] = "PRIMARY_KEY"
            elif not col.get("is_nullable", True):
                field["constraint"] = "NOT_NULL"
            
            schema.append(field)
        return schema
    
    def _add_owners(self, contract: Dict) -> Dict:
        """Добавляет владельца контракта"""
        try:
            if self.owner_id and self.owner_name:
                contract["owners"] = [{
                    "id": self.owner_id,
                    "type": "user",
                    "name": self.owner_name,
                    "displayName": self.owner_name
                }]
                logger.debug(f"Добавлены owners: {self.owner_name}")
        except Exception as e:
            logger.warning(f"Не удалось добавить owners: {e}")
        return contract
    
    def _add_tags(self, contract: Dict, domain: Optional[str]) -> Dict:
        """Добавляет теги"""
        try:
            if domain and domain not in ["Other", "Не определен", "", None]:
                contract["tags"] = [{"name": domain}]
                logger.debug(f" Добавлен тег: {domain}")
        except Exception as e:
            logger.warning(f" Не удалось добавить tags: {e}")
        return contract
    
    def _add_semantics(self, contract: Dict, columns: List[Dict], field_semantics: Dict, domain: Optional[str]) -> Dict:
        try:
            semantics = self._generate_semantics(columns, field_semantics, domain)
            if semantics:
                for s in semantics:
                    if "rule" not in s or s["rule"] is None:
                        s["rule"] = ""
                contract["semantics"] = semantics
                logger.info(f" Добавлена семантика: {len(semantics)} полей")
        except Exception as e:
            logger.warning(f" Не удалось добавить semantics: {e}")
        return contract
    
        
    def _add_sla(self, contract: Dict, table_name: str) -> Dict:
        try:
            sla = self._generate_sla(table_name)
            if sla:
                contract["sla"] = sla
                logger.info(f"Добавлено SLA")
        except Exception as e:
            logger.warning(f"Не удалось добавить sla: {e}")
        return contract
    
    
    def _generate_semantics(self, columns: List[Dict], field_semantics: Dict, domain: Optional[str]) -> List[Dict]:
        """Генерирует семантику для полей контракта"""
        semantics = []
        
        for col in columns:
            field_name = col["name"]
            
            if field_name in field_semantics:
                description = field_semantics[field_name].get("description", f"Поле {field_name}")
                rule = field_semantics[field_name].get("rule", "")
            else:
                description = self._guess_field_description(field_name)
                rule = self._guess_field_rule(field_name, col)
            
            semantics.append({
                "name": field_name,
                "description": description,
                "rule": rule or ""
            })
        
        return semantics
        
    def _generate_sla(self, table_name: str) -> Dict:
        """Генерирует SLA для контракта"""
        return {
            "refreshFrequency": {
                "interval": 1,
                "unit": "day"
            },
            "availabilityTime": "06:00 UTC",
            "retention": {
                "period": 365,
                "unit": "day"
            }
        }
    
    def _generate_description_from_structure(self, table_name: str, columns: List[Dict]) -> str:
        """Генерирует описание из структуры (без AI)"""
        col_names = [c["name"] for c in columns]
        entity_type = self._guess_entity_type(table_name)
        
        parts = []
        parts.append(f"Таблица '{table_name}'")
        if entity_type:
            parts.append(f"содержит данные о {entity_type}")
        parts.append(f"({len(columns)} колонок)")
        
        key_columns = [c["name"] for c in columns if c.get("is_primary_key")]
        if key_columns:
            parts.append(f"Ключевые поля: {', '.join(key_columns)}")
        
        col_types = [c["data_type"] for c in columns]
        type_summary = {}
        for t in col_types:
            clean_type = t.lower().split('(')[0]
            type_summary[clean_type] = type_summary.get(clean_type, 0) + 1
        
        type_desc = ", ".join([f"{v} {k}" for k, v in type_summary.items()])
        parts.append(f"Типы данных: {type_desc}")
        
        return ". ".join(parts)
    
    
    def get_contract_data_type(col: Dict) -> str:
        """Получает dataType из колонки (для контракта)"""
        raw_type = col.get('dataType') or col.get('data_type', '')
        return normalize_sql_type(raw_type)
    
    
    def _map_sql_type(self, sql_type: str) -> str:
        return normalize_sql_type(sql_type)
    
    
    
    # ----------------
    def _guess_field_description(self, field_name: str) -> str:
        descriptions = {
            "id": "Уникальный идентификатор записи",
            "email": "Адрес электронной почты",
            "phone": "Номер телефона",
            "full_name": "Полное имя",
            "first_name": "Имя",
            "last_name": "Фамилия",
            "age": "Возраст",
            "created_at": "Дата и время создания",
            "updated_at": "Дата и время последнего обновления",
            "status": "Статус записи",
            "amount": "Сумма",
            "price": "Цена",
            "quantity": "Количество",
            "description": "Описание",
            "category": "Категория",
            "is_active": "Флаг активности",
            "is_deleted": "Флаг удаления",
            "address": "Адрес",
            "city": "Город",
            "country": "Страна",
            "zip_code": "Почтовый индекс"
        }
        return descriptions.get(field_name, f"Поле {field_name}")
    
    def _guess_field_rule(self, field_name: str, col: Dict) -> str:
        rules = []
        
        if col.get("is_primary_key"):
            rules.append("Уникальный идентификатор, не может быть null")
        elif not col.get("is_nullable", True):
            rules.append("Обязательное поле, не может быть null")
        
        if "email" in field_name.lower():
            rules.append("Должен соответствовать формату email")
        if "phone" in field_name.lower():
            rules.append("Должен соответствовать формату телефонного номера")
        if "price" in field_name.lower() or "amount" in field_name.lower():
            rules.append("Должен быть положительным числом")
        if "status" in field_name.lower():
            rules.append("Допустимые значения: active, pending, completed, cancelled")
        
        return "; ".join(rules) if rules else "Без ограничений"
    
    def _guess_entity_type(self, table_name: str) -> Optional[str]:
        table_lower = table_name.lower()
        
        keywords = {
            "users": "пользователях", "user": "пользователях",
            "customer": "клиентах", "client": "клиентах",
            "person": "людях", "employee": "сотрудниках",
            "order": "заказах", "orders": "заказах",
            "transaction": "транзакциях", "payment": "платежах",
            "product": "продуктах", "products": "продуктах",
            "item": "товарах", "category": "категориях",
            "sales": "продажах", "revenue": "доходах",
            "finance": "финансах", "invoice": "счетах",
            "log": "логах", "event": "событиях",
            "audit": "аудиторских записях", "config": "конфигурациях",
            "setting": "настройках", "profile": "профилях",
            "account": "аккаунтах", "role": "ролях",
            "permission": "разрешениях", "address": "адресах",
            "contact": "контактах", "email": "email-адресах",
            "phone": "телефонах", "message": "сообщениях",
            "notification": "уведомлениях"
        }
        
        for key, value in keywords.items():
            if key in table_lower:
                return value
        return None
