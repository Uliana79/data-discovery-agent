import requests
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class OpenMetadataClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, patch: bool = False) -> Dict:
        url = f"{self.base_url}/api/v1/{endpoint}"
        try:
            headers = self.headers.copy()
            
            if patch:
                headers["Content-Type"] = "application/json-patch+json"
            else:
                headers["Content-Type"] = "application/json"
            
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка API: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Статус: {e.response.status_code}")
                logger.error(f"Ответ: {e.response.text[:500]}")
            return {}
    
    def get_current_user(self) -> str:
        try:
            result = self._request("GET", "users/me")
            if result and result.get("name"):
                return result["name"]
            return "admin"
        except Exception as e:
            logger.warning(f"Не удалось получить текущего пользователя: {e}")
            return "admin"
    
    def get_table_by_name(self, fqn: str) -> Dict:
        return self._request("GET", f"tables/name/{fqn}")
    
    def create_data_contract(self, contract_data: Dict[str, Any]) -> Dict:
        return self._request("POST", "dataContracts", contract_data)
    
    def get_data_contract(self, contract_id: str) -> Dict:
        return self._request("GET", f"dataContracts/{contract_id}")
    
    def update_data_contract_status(self, contract_id: str, status: str) -> Dict:
        return self._request("PUT", f"dataContracts/{contract_id}", {"status": status})
    
    def validate_data_contract(self, contract_id: str) -> Dict:
        return self._request("POST", f"dataContracts/{contract_id}/validate")
    
    def list_data_contracts(self) -> Dict:
        return self._request("GET", "dataContracts")
    
    def get_container_by_name(self, fqn: str) -> Dict:
        return self._request("GET", f"containers/name/{fqn}")
    
    def get_logged_in_user(self) -> Dict:
        return self._request("GET", "users/loggedInUser")