from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

#-----------------------
#CONSTANTES
#-----------------------

SUELDO_BASE_REFERENCIA = 470 # Referencia para Décimo Cuarto Sueldo
DIAS_ANIO_REFERENCIA = 360 # Días laborales del año (para décimo cuarto)
IESS_PERSONAL = 0.0945 # 9.45%
IESS_PATRONAL = 0.1215 # 12.15%


@dataclass
class DatosProyeccion:
    demanda_inicial: float = 0.0
    tasa_crecimiento: float = 0.0
    num_proyeccion: int = 5
    resultados_proyeccion: List[float] = field(default_factory=list) 


@dataclass
class ActivoFijo:
    descripcion: str = ""
    medidas: str = ""           
    valor_unitario: float = 0.0 
    cantidad: int = 0           
    valor_total: float = 0.0    
    comentario: str = ""    
    costo: float = 0.0    
    
    def calcular_total(self):
        self.valor_total = self.valor_unitario * self.cantidad
        self.costo = self.valor_total
        return self.valor_total


@dataclass
class InversionDiferidaItem:
    descripcion: str = ""
    costo: float = 0.0
    valor_unitario: float = 0.0
    cantidad: int = 0
    total: float = 0.0         
    comentario: str = ""
    
    def calcular_total(self):
        self.total = self.valor_unitario * self.cantidad
        self.costo = self.total
        return self.total


@dataclass
class AnalisisEnergeticoItem:
    descripcion: str = "" 
    valor: float = 0.0 


@dataclass
class CapitalTrabajoItem:
    descripcion: str = ""
    valor_unitario: float = 0.0
    cantidad: int = 0
    total: float = 0.0
    
    def calcular_total(self):
        self.total = self.valor_unitario * self.cantidad
        return self.total


@dataclass
class DatosInversion:
    activos_fijos: List[ActivoFijo] = field(default_factory=list) 
    inversion_diferida: List[InversionDiferidaItem] = field(default_factory=list)
    capital_trabajo_items: List[CapitalTrabajoItem] = field(default_factory=list) 
    analisis_energetico: List[AnalisisEnergeticoItem] = field(default_factory=list)
    capital_trabajo: float = 0.0
    capital_trabajo_items: List[CapitalTrabajoItem] = field(default_factory=list)


@dataclass
class Caso:
    nombre: str
    fecha_creacion: str = datetime.now().isoformat() 
    proyeccion: DatosProyeccion = field(default_factory=DatosProyeccion)
    inversion: DatosInversion = field(default_factory=DatosInversion)
    rol_pagos: 'DatosRolPagos' = field(default_factory=lambda: DatosRolPagos())


@dataclass
class ItemRolPagos:
    cargo: str = ""
    sueldo_nominal: float = 0.0
    dias_trabajados: int = 30 # Por defecto, mes completo
    no_he: int = 0 # Horas Extraordinarias
    no_hs: int = 0 # Horas Suplementarias
    no_jn: int = 0 # Jornada Nocturna
    comisiones: float = 0.0
    anticipos: float = 0.0
    descuentos: float = 0.0
    quincenas: float = 0.0
    
    sueldo: float = 0.0
    remuneracion: float = 0.0
    decimo_tercer_sueldo: float = 0.0
    decimo_cuarto_sueldo: float = 0.0
    fondos_reserva: float = 0.0 # Simplificado a 0 por ahora (se calcula en Financiamiento)
    total_ingresos: float = 0.0
    ap_personal: float = 0.0
    l_recibir: float = 0.0
    ap_patronal: float = 0.0
    vacaciones: float = 0.0
    pago_empleador: float = 0.0
    
    def calcular_rol(self):
        # 1. Sueldo
        self.sueldo = (self.sueldo_nominal / 30) * self.dias_trabajados
        
        # 2. Remuneración
        # NOTA: Horas Extraordinarias/Suplementarias/Nocturnas son valores Fijos de entrada aquí.
        self.remuneracion = self.sueldo + self.no_he + self.no_hs + self.no_jn + self.comisiones 
        
        # 3. Décimo Tercer Sueldo
        self.decimo_tercer_sueldo = self.remuneracion / 12
        
        # 4. Décimo Cuarto Sueldo (USD 470.00 / 360 * Días Trabajados)
        self.decimo_cuarto_sueldo = (SUELDO_BASE_REFERENCIA / DIAS_ANIO_REFERENCIA) * self.dias_trabajados
        
        # 5. AP. Personal (9.45%)
        self.ap_personal = self.remuneracion * IESS_PERSONAL
        
        # 6. Total de Ingresos (simplificado: sin comisiones, anticipos, fondos)
        self.total_ingresos = self.remuneracion + self.decimo_tercer_sueldo + self.decimo_cuarto_sueldo + self.fondos_reserva 
        
        # 7. L. Recibir
        self.l_recibir = self.total_ingresos - self.ap_personal - self.descuentos - self.quincenas
        
        # 8. AP. Patronal (12.15%)
        self.ap_patronal = self.remuneracion * IESS_PATRONAL
        
        # 9. Vacaciones
        self.vacaciones = self.remuneracion / 24
        
        # 10. Pago Empleador
        self.pago_empleador = self.sueldo + self.decimo_tercer_sueldo + self.decimo_cuarto_sueldo + self.fondos_reserva + self.ap_patronal + self.vacaciones


@dataclass
class AnioRolPagos:
    items: List[ItemRolPagos] = field(default_factory=list)
    total_anual: float = 0.0

@dataclass
class DatosRolPagos:
    num_proyeccion: int = 5 
    proyeccion_anual: List[AnioRolPagos] = field(default_factory=list)
    gran_total_general: float = 0.0