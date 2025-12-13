from .models import Caso, DatosProyeccion
from datetime import datetime
from typing import Optional, List
import json
import os


# Define la ruta donde se guardarán los archivos JSON
CASES_DIR = os.path.join(os.path.dirname(__file__), '..', 'resources', 'cases')

class CaseManager:
    """
    Gestiona el estado del caso activo y la persistencia de archivos.
    """
    
    def __init__(self):
        self._caso_actual: Optional[Caso] = None

    def inicializar_nuevo_caso(self, nombre: str) -> Caso:
        """Crea un nuevo caso y lo establece como activo."""
        nuevo_caso = Caso(nombre=nombre, fecha_creacion=datetime.now().isoformat())
        self._caso_actual = nuevo_caso
        return nuevo_caso

    def obtener_caso_actual(self) -> Optional[Caso]:
        """Devuelve el caso actualmente activo."""
        return self._caso_actual

    def guardar_caso_actual(self):
        """Guarda el caso actual como archivo JSON en la carpeta resources/cases."""
        caso = self.obtener_caso_actual()
        if not caso:
            return False, "No hay caso activo para guardar."
        
        # 1. Crear nombre de archivo seguro
        nombre_limpio = caso.nombre.replace(" ", "_").lower()
        filename = f"{nombre_limpio}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        # Asegurarse de que el directorio de casos exista
        os.makedirs(CASES_DIR, exist_ok=True)
        filepath = os.path.join(CASES_DIR, filename)

        # 2. Serializar el objeto Caso a JSON (usando el diccionario interno de dataclass)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(caso.__dict__, f, indent=4)
            return True, f"Caso '{caso.nombre}' guardado en {filepath}"
        except Exception as e:
            return False, f"Error al guardar el archivo: {e}"

# Instancia única del CaseManager para usar en Flask
manager = CaseManager()