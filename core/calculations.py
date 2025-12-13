from typing import List
from .models import DatosProyeccion, DatosInversion

def calcular_proyeccion(datos: DatosProyeccion) -> List[int]:
    demanda_inicial = datos.demanda_inicial
    tasa_crecimiento_decimal = datos.tasa_crecimiento / 100.0
    num_proyeccion = datos.num_proyeccion
    
    resultados: List[float] = []
    demanda_anterior = demanda_inicial
    
    if num_proyeccion <= 0:
        return []

    for i in range(num_proyeccion):
        demanda_actual: float
        
        if i == 0:
            demanda_actual = demanda_inicial
        else:
            demanda_actual = demanda_anterior * (1 + tasa_crecimiento_decimal)
        
        resultados.append(round(demanda_actual))
        demanda_anterior = demanda_actual
        
    return resultados

def inversion_total_activos(datos_inversion: DatosInversion) -> float:
    """Calcula el costo total de los activos fijos."""
    return sum(activo.valor_total for activo in datos_inversion.activos_fijos)

def inversion_total_diferida(datos_inversion: DatosInversion) -> float:
    """Calcula el costo total de la inversión diferida (sumando total)."""
    return sum(item.total for item in datos_inversion.inversion_diferida)

def inversion_total_capital_trabajo(datos_inversion: DatosInversion) -> float:
    """Calcula el total del Capital de Trabajo sumando los totales de los ítems."""
    return sum(item.total for item in datos_inversion.capital_trabajo_items)

def inversion_total_general(datos_inversion: DatosInversion) -> float:
    """Calcula la inversión inicial total (Fijos + Diferida + Capital)."""
    total_fijos = inversion_total_activos(datos_inversion)
    total_diferida = inversion_total_diferida(datos_inversion)
    total_capital = inversion_total_capital_trabajo(datos_inversion) 
    return total_fijos + total_diferida + total_capital

def sincronizar_total_capital_trabajo(datos_inversion: DatosInversion):
    """Sincroniza el campo antiguo 'capital_trabajo' con el total calculado de ítems."""
    datos_inversion.capital_trabajo = inversion_total_capital_trabajo(datos_inversion)