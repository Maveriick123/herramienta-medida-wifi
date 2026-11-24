import json
import os

class StorageManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
    
    def save_measurement(self, project_name, record):
        file_path = os.path.join(self.data_dir, f"{project_name}.json")

        data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if not isinstance(data, list):
                            data = [data]
            except Exception:
                print(f"storage_manager.py: No se pudo leer {file_path}. Se creará uno nuevo.")  
        data.append(record)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return {"success": True, "path": file_path, "error": None}
        except Exception as e:
            return {"success": False, "path": file_path, "error": str(e)}   