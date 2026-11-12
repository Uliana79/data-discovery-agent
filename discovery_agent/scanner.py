import logging
from connectors.postgres_connector import PostgresConnector
from config import SOURCE_DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Scanner:
    def __init__(self):
        self.connector = PostgresConnector(SOURCE_DB_CONFIG)
    
    def scan_all_tables(self, schema: str = "public"):
        if not self.connector.connect():
            logger.error("Не удалось подключиться")
            return []
        
        try:
            tables = self.connector.list_tables(schema)
            logger.info(f"Найдено таблиц: {len(tables)}")
            
            result = []
            for table_name in tables:
                logger.info(f"Сканируем: {table_name}")
                result.append({
                    "table_name": table_name,
                    "columns": self.connector.get_columns(table_name, schema),
                    "statistics": self.connector.get_statistics(table_name, schema),
                    "sample_data": self.connector.get_sample(table_name, schema, limit=3)
                })
            return result
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return []
        finally:
            self.connector.disconnect()

if __name__ == "__main__":
    scanner = Scanner()
    metadata = scanner.scan_all_tables()
    
    print("\n" + "="*50)
    for table in metadata:
        print(f"\n {table['table_name']}")
        print(f"  Колонок: {len(table['columns'])}")
        print(f"  Строк: {table['statistics']['row_count']}")
        print("  Колонки:", ", ".join([c['name'] for c in table['columns']]))