from flask import Flask, render_template, request, redirect, url_for, jsonify
import sys
import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'discovery_agent')
sys.path.insert(0, AGENT_PATH)

from scanner import Scanner
from s3_scanner import S3Scanner
from clients.openmetadata_client import OpenMetadataClient
from config import OPENMETADATA_CONFIG, SOURCE_DB_CONFIG, S3_CONFIG
from contract_updater import check_all_contracts, update_contract_schema

app = Flask(__name__)
app.secret_key = 'secret-key-for-demo'


scan_results = {
    'status': 'idle',
    'message': 'Готов к работе',
    'tables': [],
    'contracts': [],
    'total_tables': 0,
    'total_contracts': 0,
    'source': 'postgres' 
}

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def run_scan():
    """Запускает сканирование PostgreSQL"""
    global scan_results
    logger.info("Запуск сканирования PostgreSQL...")
    
    try:
        scan_results = {
            'status': 'running',
            'message': 'Сканирование PostgreSQL запущено...',
            'tables': [],
            'contracts': [],
            'total_tables': 0,
            'total_contracts': 0,
            'source': 'postgres'
        }
        
        tables_with_info = check_all_contracts()
        
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        contracts_response = client.list_data_contracts()
        contracts = contracts_response.get('data', [])
        
        scan_results = {
            'status': 'completed',
            'message': f' Сканирование PostgreSQL завершено! Найдено таблиц: {len(tables_with_info)}',
            'tables': tables_with_info,
            'contracts': contracts,
            'total_tables': len(tables_with_info),
            'total_contracts': len(contracts),
            'source': 'postgres'
        }
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f" Ошибка: {e}")
        import traceback
        traceback.print_exc()
        scan_results = {
            'status': 'error',
            'message': f'Ошибка: {str(e)}',
            'tables': [],
            'contracts': [],
            'total_tables': 0,
            'total_contracts': 0,
            'source': 'postgres'
        }
        return redirect(url_for('results'))

@app.route('/scan_s3', methods=['POST'])
def scan_s3():
    """Запускает сканирование S3 (папки)"""
    global scan_results
    logger.info("Запуск сканирования S3...")
    
    try:
        scan_results = {
            'status': 'running',
            'message': 'Сканирование S3 запущено...',
            'tables': [],
            'contracts': [],
            'total_tables': 0,
            'total_contracts': 0,
            'source': 's3'
        }
        
        scanner = S3Scanner()
        folders = scanner.scan_folders()
        
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        contracts_response = client.list_data_contracts()
        contracts = contracts_response.get('data', [])
        
        tables_with_info = []
        for folder in folders:
            folder_name = folder['folder_name']
            contract_name = f"{folder_name}-contract"
            has_contract = any(c.get('name') == contract_name for c in contracts)
            
            tables_with_info.append({
                'table_name': folder_name,
                'columns': folder.get('columns', []),
                'statistics': {'row_count': folder.get('row_count', 0)},
                'has_contract': has_contract,
                'contract_id': None,
                'contract_name': contract_name if has_contract else None,
                'diff': {'has_changes': False},
                'needs_update': False,
                'source_type': 's3_folder',
                'format': folder.get('format', 'unknown'),
                'file_count': folder.get('file_count', 0)
            })
        
        scan_results = {
            'status': 'completed',
            'message': f' Сканирование S3 завершено! Найдено папок: {len(tables_with_info)}',
            'tables': tables_with_info,
            'contracts': contracts,
            'total_tables': len(tables_with_info),
            'total_contracts': len(contracts),
            'source': 's3'
        }
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f" Ошибка: {e}")
        import traceback
        traceback.print_exc()
        scan_results = {
            'status': 'error',
            'message': f'Ошибка: {str(e)}',
            'tables': [],
            'contracts': [],
            'total_tables': 0,
            'total_contracts': 0,
            'source': 's3'
        }
        return redirect(url_for('results'))

@app.route('/results')
def results():
    """Показывает результаты с актуальными данными из OpenMetadata"""
    global scan_results
    
    try:
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        
        contracts_response = client.list_data_contracts()
        contracts = contracts_response.get('data', [])
        
        if scan_results.get('source') == 'postgres':
            tables_with_info = check_all_contracts()
            scan_results['tables'] = tables_with_info
            scan_results['total_tables'] = len(tables_with_info)
        elif scan_results.get('source') == 's3':
            for table in scan_results.get('tables', []):
                folder_name = table['table_name']
                fqn = f"s3_source.data-contracts.{folder_name}"
                
                try:
                    result = client._request("GET", f"containers/name/{fqn}")
                    if result and result.get('id'):
                        container_uuid = result['id']
                        has_contract = False
                        for contract in contracts:
                            entity = contract.get('entity', {})
                            if entity.get('id') == container_uuid:
                                has_contract = True
                                break
                        table['has_contract'] = has_contract
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить UUID для {folder_name}: {e}")
                    table['has_contract'] = False
        
        scan_results['contracts'] = contracts
        scan_results['total_contracts'] = len(contracts)
        scan_results['status'] = 'completed'
        scan_results['message'] = f' Актуальные данные (контрактов: {len(contracts)})'
        
    except Exception as e:
        logger.error(f" Ошибка загрузки результатов: {e}")
        import traceback
        traceback.print_exc()
    
    return render_template('results.html', results=scan_results)

@app.route('/create', methods=['POST'])
def create_contracts():
    """Создаёт контракты для всех таблиц PostgreSQL"""
    global scan_results
    logger.info(" Запуск создания контрактов...")
    
    try:
        from create_contracts_with_ai import main as create_main
        create_main()
        
        tables_with_info = check_all_contracts()
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        contracts_response = client.list_data_contracts()
        contracts = contracts_response.get('data', [])
        
        scan_results = {
            'status': 'completed',
            'message': ' Контракты созданы успешно!',
            'tables': tables_with_info,
            'contracts': contracts,
            'total_tables': len(tables_with_info),
            'total_contracts': len(contracts),
            'source': 'postgres'
        }
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f" Ошибка: {e}")
        import traceback
        traceback.print_exc()
        scan_results = {
            'status': 'error',
            'message': f'Ошибка: {str(e)}',
            'tables': [],
            'contracts': [],
            'total_tables': 0,
            'total_contracts': 0,
            'source': 'postgres'
        }
        return redirect(url_for('results'))

@app.route('/create_s3_contracts', methods=['POST'])
def create_s3_contracts():
    """Создаёт контракты для папок из S3"""
    global scan_results
    logger.info(" Запуск создания контрактов для S3...")
    
    try:
        from create_s3_contracts import main as create_s3_main
        create_s3_main()
        
        scanner = S3Scanner()
        folders = scanner.scan_folders()
        
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        contracts_response = client.list_data_contracts()
        contracts = contracts_response.get('data', [])
        
        tables_with_info = []
        for folder in folders:
            folder_name = folder['folder_name']
            contract_name = f"{folder_name}-contract"
            has_contract = any(c.get('name') == contract_name for c in contracts)
            
            tables_with_info.append({
                'table_name': folder_name,
                'columns': folder.get('columns', []),
                'statistics': {'row_count': folder.get('row_count', 0)},
                'has_contract': has_contract,
                'contract_id': None,
                'contract_name': contract_name if has_contract else None,
                'diff': {'has_changes': False},
                'needs_update': False,
                'source_type': 's3_folder',
                'format': folder.get('format', 'unknown'),
                'file_count': folder.get('file_count', 0)
            })
        
        scan_results = {
            'status': 'completed',
            'message': ' Контракты для S3 созданы успешно!',
            'tables': tables_with_info,
            'contracts': contracts,
            'total_tables': len(tables_with_info),
            'total_contracts': len(contracts),
            'source': 's3'
        }
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f" Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('results'))

@app.route('/update_contract/<contract_id>', methods=['POST'])
def update_contract(contract_id):
    """Обновляет схему контракта и возвращается на страницу результатов"""
    global scan_results
    
    result = update_contract_schema(contract_id)
    
    if result.get('success'):
        try:
            tables_with_info = check_all_contracts()
            client = OpenMetadataClient(
                base_url=OPENMETADATA_CONFIG["url"],
                token=OPENMETADATA_CONFIG["token"]
            )
            contracts_response = client.list_data_contracts()
            contracts = contracts_response.get('data', [])
            
            scan_results = {
                'status': 'completed',
                'message': ' Контракт обновлён!',
                'tables': tables_with_info,
                'contracts': contracts,
                'total_tables': len(tables_with_info),
                'total_contracts': len(contracts),
                'source': 'postgres'
            }
            logger.info(" Результаты обновлены после обновления контракта")
        except Exception as e:
            logger.error(f" Ошибка обновления результатов: {e}")
        
        return redirect(url_for('results'))
    else:
        return jsonify(result), 400

@app.route('/contracts')
def contracts():
    """Показывает список контрактов"""
    try:
        client = OpenMetadataClient(
            base_url=OPENMETADATA_CONFIG["url"],
            token=OPENMETADATA_CONFIG["token"]
        )
        contracts = client.list_data_contracts()
        return render_template('contracts.html', contracts=contracts.get('data', []))
    except Exception as e:
        logger.error(f" Ошибка получения контрактов: {e}")
        return render_template('contracts.html', contracts=[], error=str(e))

@app.route('/refresh_results', methods=['POST'])
def refresh_results():
    """Принудительно обновляет результаты"""
    global scan_results
    
    scan_results = {
        'status': 'idle',
        'message': 'Готов к работе',
        'tables': [],
        'contracts': [],
        'total_tables': 0,
        'total_contracts': 0,
        'source': scan_results.get('source', 'postgres')
    }
    
    return redirect(url_for('results'))

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)