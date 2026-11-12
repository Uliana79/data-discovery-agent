import psycopg2
from psycopg2 import sql
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PostgresConnector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._connection = None
    
    def connect(self):
        try:
            self._connection = psycopg2.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"]
            )
            logger.info(f"Подключено к PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return False
    
    def disconnect(self):
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def list_tables(self, schema: str = "public") -> List[str]:
        cursor = self._connection.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema,))
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables
    
    def get_columns(self, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        cursor = self._connection.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, table_name))
            
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[0],
                    "data_type": row[1],
                    "is_nullable": row[2] == "YES",
                    "is_primary_key": False
                })
            
            cursor.close()
            return columns
            
        except Exception as e:
            logger.error(f"Ошибка получения колонок для {table_name}: {e}")
            cursor.close()
            return []
    
    def get_statistics(self, table_name: str, schema: str = "public") -> Dict[str, Any]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(schema),
                sql.Identifier(table_name)
            ))
            row_count = cursor.fetchone()[0]
            cursor.close()
            return {"row_count": row_count}
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            cursor.close()
            return {"row_count": 0}
    
    def get_sample(self, table_name: str, schema: str = "public", limit: int = 5) -> List[Dict[str, Any]]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
                sql.Identifier(schema),
                sql.Identifier(table_name)
            ), (limit,))
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()
            return rows
        except Exception as e:
            logger.error(f"Ошибка выборки: {e}")
            cursor.close()
            return []