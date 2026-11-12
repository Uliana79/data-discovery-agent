import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class YandexGPTClient:
    """Клиент для работы с YandexGPT API"""
    
    def __init__(self, folder_id: str, iam_token: str, model: str = "yandexgpt-lite"):
        self.folder_id = folder_id
        self.iam_token = iam_token
        self.model = model
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        logger.info("Инициализация YandexGPT")
    
    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.iam_token}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json"
        }
    
    def _capitalize_first_letter(self, text: str) -> str:
        """Делает первую букву заглавной"""
        if not text or not text[0].isalpha():
            return text
        return text[0].upper() + text[1:]
    
    def generate_table_description(self, table_name: str, columns: List[Dict], source_type: str = "postgres") -> str:
        """Генерирует описание таблицы"""
        
        columns_desc = "\n".join([
            f"  - {col.get('name', '')} ({col.get('data_type', col.get('dataType', 'unknown'))})"
            for col in columns
        ])
        
        if source_type == "s3":
            entity_type = "хранилище (папка) в S3"
            prompt_intro = f"Опиши хранилище (папку) '{table_name}' в S3."
        else:
            entity_type = "таблица"
            prompt_intro = f"Опиши таблицу '{table_name}' в базе данных."
        
        prompt = f"""
                    Ты — Data Steward. {prompt_intro}

                    Колонки:
                    {columns_desc}

                    Напиши краткое описание (1-2 предложения):
                    - Что за данные хранятся?

                    Ответ дай строго в формате:
                    Описание: <текст>
                """
        
        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 300
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты — эксперт по данным. Отвечай кратко и по делу. Начинай каждое предложение с заглавной буквы."
                },
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }
        
        try:
            logger.info(f"Запрос к YandexGPT для {table_name}")
            response = requests.post(self.url, headers=self._get_headers(), json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            text = result.get("result", {}).get("alternatives", [{}])[0].get("message", {}).get("text", "")
    
            description = self._parse_response(text)
            description = self._capitalize_first_letter(description)
            
            logger.info(f"AI-описание получено для {table_name}")
            return description
            
        except Exception as e:
            logger.error(f"Ошибка YandexGPT: {e}")
            return None
    
    def _parse_response(self, response: str) -> str:
        """Парсит ответ AI, извлекая описание"""
        if not response:
            return None
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith("Описание:"):
                return line.replace("Описание:", "").strip()
        
        return response