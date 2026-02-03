from .models import (
    Caso, DatosProyeccion, DatosInversion, ActivoFijo, InversionDiferidaItem, 
    CapitalTrabajoItem, AnalisisEnergeticoItem, RegistroConsumoMensual, 
    RegistroConsumoDiario, DatosRolPagos, AnioRolPagos, ItemRolPagos,
    DatosFinanciamiento, DatosWacc, ItemWacc, DatosAmortizacion
)
from dataclasses import asdict
from datetime import datetime
from typing import Optional, List
import json
import os

# Define la ruta donde se guardarán los archivos JSON
CASES_DIR = os.path.join(os.path.dirname(__file__), '..', 'resources', 'reports')

class CaseManager:
    """
    Gestiona el estado del caso activo y la persistencia de archivos.
    """
    
    def __init__(self):
        self._caso_actual: Optional[Caso] = None

    def cerrar_caso_actual(self):
        """Cierra el caso activo actual, limpiando la memoria."""
        self._caso_actual = None

    def inicializar_nuevo_caso(self, nombre: str) -> Caso:
        """Crea un nuevo caso y lo establece como activo."""
        nuevo_caso = Caso(nombre=nombre, fecha_creacion=datetime.now().isoformat())
        
        # Generamos un nombre de archivo único UNA VEZ al inicio
        nombre_limpio = nombre.replace(" ", "_").lower()
        nuevo_caso.filename = f"{nombre_limpio}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        self._caso_actual = nuevo_caso
        return nuevo_caso

    def obtener_caso_actual(self) -> Optional[Caso]:
        """Devuelve el caso actualmente activo."""
        return self._caso_actual

    def listar_casos(self) -> List[str]:
        """Devuelve una lista de nombres de archivos de casos guardados."""
        if not os.path.exists(CASES_DIR):
            return []
        files = [f for f in os.listdir(CASES_DIR) if f.endswith('.json')]
        files.sort(reverse=True) # Mostrar más recientes primero (por fecha en nombre)
        return files

    def guardar_caso_actual(self):
        """Guarda el caso actual como archivo JSON en la carpeta resources/reports."""
        caso = self.obtener_caso_actual()
        if not caso:
            return False, "No hay caso activo para guardar."
        
    def guardar_caso_actual(self):
        """Guarda el caso actual como archivo JSON en la carpeta resources/reports."""
        caso = self.obtener_caso_actual()
        if not caso:
            return False, "No hay caso activo para guardar."
        
        # Si por alguna razón no tiene filename (casos viejos en memoria), generamos uno
        if not caso.filename:
             nombre_limpio = caso.nombre.replace(" ", "_").lower()
             caso.filename = f"{nombre_limpio}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"

        # Asegurarse de que el directorio de casos exista
        os.makedirs(CASES_DIR, exist_ok=True)
        filepath = os.path.join(CASES_DIR, caso.filename)

        # 2. Serializar usando asdict para recursividad
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(caso), f, indent=4)
            return True, caso.filename
        except Exception as e:
            return False, str(e)

    def cargar_caso_desde_archivo(self, filename: str) -> bool:
        """Carga un caso desde un archivo JSON y reconstruye los objetos dataclass."""
        filepath = os.path.join(CASES_DIR, filename)
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstrucción manual de la jerarquía (Hydration)
            caso = Caso(
                nombre=data.get('nombre', 'Sin Nombre'), 
                fecha_creacion=data.get('fecha_creacion', ''),
                filename=filename # Mantenemos el nombre del archivo original
            )
            
            # 1. Proyección
            p_data = data.get('proyeccion', {})
            caso.proyeccion = DatosProyeccion(
                demanda_inicial=p_data.get('demanda_inicial', 0),
                tasa_crecimiento=p_data.get('tasa_crecimiento', 0),
                num_proyeccion=p_data.get('num_proyeccion', 5),
                resultados_proyeccion=p_data.get('resultados_proyeccion', [])
            )
            
            # 2. Inversión
            inv_data = data.get('inversion', {})
            caso.inversion = DatosInversion(
                capital_trabajo=inv_data.get('capital_trabajo', 0)
            )
            # Reconstruir listas de inversión
            caso.inversion.activos_fijos = [ActivoFijo(**item) for item in inv_data.get('activos_fijos', [])]
            caso.inversion.inversion_diferida = [InversionDiferidaItem(**item) for item in inv_data.get('inversion_diferida', [])]
            caso.inversion.capital_trabajo_items = [CapitalTrabajoItem(**item) for item in inv_data.get('capital_trabajo_items', [])]
            caso.inversion.analisis_energetico = [AnalisisEnergeticoItem(**item) for item in inv_data.get('analisis_energetico', [])]
            caso.inversion.consumos_mensuales = [RegistroConsumoMensual(**item) for item in inv_data.get('consumos_mensuales', [])]
            caso.inversion.consumos_diarios = [RegistroConsumoDiario(**item) for item in inv_data.get('consumos_diarios', [])]
            
            # 3. Rol de Pagos
            rol_data = data.get('rol_pagos', {})
            caso.rol_pagos = DatosRolPagos(
                num_proyeccion=rol_data.get('num_proyeccion', 5),
                gran_total_general=rol_data.get('gran_total_general', 0)
            )
            caso.rol_pagos.proyeccion_anual = []
            for anio_data in rol_data.get('proyeccion_anual', []):
                anio = AnioRolPagos(total_anual=anio_data.get('total_anual', 0))
                anio.items = [ItemRolPagos(**item) for item in anio_data.get('items', [])]
                caso.rol_pagos.proyeccion_anual.append(anio)

            # 4. Financiamiento
            fin_data = data.get('financiamiento', {})
            caso.financiamiento = DatosFinanciamiento(**fin_data)
            
            # 5. WACC
            wacc_data = data.get('wacc', {})
            caso.wacc = DatosWacc(
                gran_total_general=wacc_data.get('gran_total_general', 0)
            )
            caso.wacc.tabla_utilidad = [ItemWacc(**item) for item in wacc_data.get('tabla_utilidad', [])]
            caso.wacc.tabla_patrimonio = [ItemWacc(**item) for item in wacc_data.get('tabla_patrimonio', [])]
            
            # 6. Amortización
            amort_data = data.get('amortizacion', {})
            caso.amortizacion = DatosAmortizacion(**amort_data)
            
            self._caso_actual = caso
            return True
        except Exception as e:
            print(f"Error cargando caso: {e}")
            return False

# Instancia única del CaseManager para usar en Flask
manager = CaseManager()