import json
import os
import platform
from datetime import datetime   


class SessionManager:
    def __init__(self, config_path="config/current_config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def _get_wireless_interface(self):
    
        interfaces = os.listdir('/sys/class/net')
        for iface in interfaces:
            if iface.startswith('wl'):
                return iface        
        return "desconocida"   

    def load_config(self):
        default_structure = {
            "project_name": "mediciones_FIC",
            "device_metadata": {
                "hostname": platform.node(),
                "os": f"{platform.system()} {platform.release()}",
                "architecture": platform.machine(),
                "wireless_interface": self._get_wireless_interface()
            },
            "building": "FIC",
            "floor": "2",
            "room": "Aula 2.5",
            "corridor": "Pasillo central",
            "point_id": "Puesto_02_05_MesCentral",
            "coordinate_system": "Pixeles(Plano)",
            "coordinates": {"x": 0, "y": 0},
            "orientation": "Norte (0 grados)"
        }
        """Aquí se transforma la current_config.json en un diccionario y se añaden las claves faltantes, en caso de añadir nuevas """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    for key, value in default_structure.items():
                        if key not in user_config:
                            user_config[key] = value
                    return user_config
            except Exception:
                pass 
            """Si el json no existe o estaba corrupto se devuelve la config por defecto"""
        else:
            return default_structure
        
    
        
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def update_tags(self, new_tags):
        for key, value in new_tags.items():
            if value is not None and value != "":
                self.config[key] = value
        self.save_config()

    def create_measurement_record(self, scan_result):
        return {
            "timestamp": datetime.now().isoformat(),
            "project_name": self.config.get("project_name"),
            "conditions": {
                "device": self.config.get("device_metadata"),
                "building": self.config.get("building"),
                "floor": self.config.get("floor"),
                "room": self.config.get("room"),
                "corridor": self.config.get("corridor"),
                "point_id": self.config.get("point_id"),
                "coordinate_system": self.config.get("coordinate_system"),
                "coordinates": self.config.get("coordinates"),
                "orientation": self.config.get("orientation")
            },
            "measurement_data": scan_result
        }   
