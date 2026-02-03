from flask import (
    Flask, render_template, request, redirect, url_for, 
    session, jsonify, abort
)
from core.case_manager import manager 
from core.models import (
    DatosProyeccion, ActivoFijo, InversionDiferidaItem, 
    CapitalTrabajoItem, ItemRolPagos, AnioRolPagos, RegistroConsumoDiario, RegistroConsumoMensual, DatosFinanciamiento, ItemWacc, DatosWacc, DatosAmortizacion
)
from core.calculations import (
    calcular_proyeccion, inversion_total_activos, 
    inversion_total_diferida, inversion_total_capital_trabajo, 
    inversion_total_general, sincronizar_total_capital_trabajo
)

import copy
import dataclasses

# -------------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui' 

app.jinja_env.globals.update(
    inversion_total_activos=inversion_total_activos,
    inversion_total_diferida=inversion_total_diferida,
    inversion_total_capital_trabajo=inversion_total_capital_trabajo,
    inversion_total_general=inversion_total_general
)

# -------------------------------------------------------------------
# RUTAS DE NAVEGACIÓN
# -------------------------------------------------------------------

@app.route('/')
def index():
    """Ruta del Dashboard/Página Inicial."""
    return render_template('main.html')

@app.route('/cerrar-caso')
def cerrar_caso():
    """Cierra el caso en memoria para permitir iniciar uno nuevo."""
    manager.cerrar_caso_actual()
    session.pop('needs_name', None)
    return redirect(url_for('index'))

@app.route('/reporte')
def reporte():
    """Lista los proyectos guardados."""
    casos = manager.listar_casos()
    return render_template('reporte.html', casos=casos)

@app.route('/nuevo-caso/<tab_name>', defaults={'sub_tab_name': None})
@app.route('/nuevo-caso', defaults={'tab_name': 'proyeccion', 'sub_tab_name': None})
@app.route('/nuevo-caso/<tab_name>/<sub_tab_name>')

# -------------------------------------------------------------------
# FUNCIONES
# -------------------------------------------------------------------

def nuevo_caso(tab_name: str, sub_tab_name: str):
    """Ruta contenedora para la gestión de pestañas del caso."""
    
    caso = manager.obtener_caso_actual()
    if not caso:
        session['needs_name'] = True
        return render_template('nuevo_caso.html', caso=None, tabs=[], active_tab=tab_name)
    
    # Si hay caso activo, aseguramos que no se pida nombre
    session.pop('needs_name', None)
    
    tabs = [
        ("Proyeccion", "proyeccion"), ("Inversion", "inversion"), ("Financiamiento", "financiamiento"), 
        ("Tasa de amortizacion", "tasa-amortizacion"), ("Depreciacion y Amortizacion", "depreciacion-amortizacion"), 
        ("Flujo Real", "flujo-real"), ("Flujo Pesimista", "flujo-pesimista"), ("Flujo Optimista", "flujo-optimista"), 
        ("Escenarios", "escenarios"), ("Resumen del escenario", "resumen-escenario"), ("Rol de pagos", "rol-pagos"), 
        ("WACC", "wacc"), ("PayBack Real", "pay-back-real"), ("PayBack Pesimista", "pay-back-pesimista"), 
        ("PayBack Optmista", "pay-back-optimista"), ("Cuadro Resumen", "cuadro-resumen"), 
        ("Respuestas Formulario", "respuestas-formulario"), ("Resumen General", "resumen-general")
    ]

    inversion_sub_tabs = [
        ("Maquinarias y equipos", "maquinarias"), 
        ("Inversion diferida", "diferida"), 
        ("Capital de trabajo", "capital"),
        ("Analisis energetico", "energetico")
    ]
    
    # -----------------------------------
    # Lógica de la Sub-Pestaña de Inversión
    # -----------------------------------
    if tab_name == 'inversion':
        if sub_tab_name is None:
            sub_tab_name = ''
    elif tab_name == 'rol-pagos':
            sub_tab_name = 'formulario' if sub_tab_name is None else sub_tab_name
    else:
        sub_tab_name = None 

    return render_template(
        'nuevo_caso.html', 
        tabs=tabs,
        active_tab=tab_name,
        sub_tab=sub_tab_name, 
        inversion_sub_tabs=inversion_sub_tabs,
        caso=caso
    )

@app.route('/iniciar-caso', methods=['POST'])
def iniciar_caso():
    """Inicializa un nuevo caso con el nombre proporcionado por el usuario."""
    nombre = request.form.get('nombre_caso')
    if nombre:
        manager.inicializar_nuevo_caso(nombre)
        session.pop('needs_name', None)
        return redirect(url_for('nuevo_caso', tab_name='proyeccion')) 
    return redirect(url_for('nuevo_caso'))


def validar_caso_activo():
    """Función de ayuda para verificar el caso y devolver un error si no existe."""
    caso = manager.obtener_caso_actual()
    if not caso:
        abort(400, description="No hay caso activo. Por favor, inicie uno.")
    return caso


@app.route('/guardar-caso', methods=['POST', 'GET'])
def guardar_caso():
    """Guarda el estado actual del caso en disco."""
    success, result = manager.guardar_caso_actual()
    if success:
        return redirect(url_for('nuevo_caso', tab_name='proyeccion'))
    return f"Error al guardar: {result}", 500


@app.route('/cargar-caso/<filename>')
def cargar_caso(filename):
    """Carga un caso desde el disco y lo establece como activo."""
    if manager.cargar_caso_desde_archivo(filename):
        return redirect(url_for('nuevo_caso', tab_name='proyeccion'))
    return "Error al cargar el archivo. Puede estar corrupto o no existir.", 400


def regenerar_proyeccion_rol(caso):
    """
    Reconstruye la proyección anual del Rol de Pagos, aplicando el incremento salarial (1.03) 
    a partir del Año 2, y asegura que existan N años de proyección.
    """
    
    num_proyeccion_anos = caso.proyeccion.num_proyeccion
    
    # Si no hay cargos en el rol (es la primera vez), solo inicializa la lista de años
    if not caso.rol_pagos.proyeccion_anual or not caso.rol_pagos.proyeccion_anual[0].items:
        # Crea una lista de N AnioRolPagos vacíos
        caso.rol_pagos.proyeccion_anual = [AnioRolPagos() for _ in range(num_proyeccion_anos)]
        return

    # Cargos base (se obtienen del primer año, que siempre debe ser la fuente de verdad)
    cargos_base = caso.rol_pagos.proyeccion_anual[0].items

    # 1. Reiniciar la proyección anual
    caso.rol_pagos.proyeccion_anual = []
    
    # 2. Iterar y proyectar para cada año
    for anio in range(num_proyeccion_anos):
        anio_rol = AnioRolPagos()
        
        for cargo_item in cargos_base:
            # Clonar el cargo del AÑO BASE (cargo_item) para empezar el cálculo
            clon_cargo = copy.deepcopy(cargo_item) 
            
            # --- LÓGICA DE INCREMENTO SALARIAL (1.03) ---
            if anio > 0: 
                # Sueldo del año anterior (base para el incremento)
                
                # Para simplificar y evitar buscar en el año anterior que acabamos de crear,
                # aplicamos el factor de incremento de forma acumulada sobre el sueldo base (Año 1)
                
                # Se calcula el factor de incremento: 1.03 elevado al número del año proyectado (anio)
                factor_incremento = 1.03 ** anio
                
                # El nuevo sueldo nominal es el original * factor_incremento
                clon_cargo.sueldo_nominal = cargo_item.sueldo_nominal * factor_incremento
            # --- FIN INCREMENTO SALARIAL ---
            
            clon_cargo.calcular_rol() 
            anio_rol.items.append(clon_cargo)
            
        caso.rol_pagos.proyeccion_anual.append(anio_rol)

# -------------------------------------------------------------------
# RUTAS DE GUARDADO DE DATOS (API POST)
# -------------------------------------------------------------------

@app.route('/api/guardar-maquinarias', methods=['POST'])
def guardar_maquinarias():
    """Guarda un nuevo registro de Activo Fijo (Anexo 1)."""
    caso = validar_caso_activo()
    try:
        nuevo_activo = ActivoFijo(
            descripcion=request.form.get('descripcion', ''),
            medidas=request.form.get('medidas', ''),
            valor_unitario=float(request.form.get('valor_unitario', 0)),
            cantidad=int(request.form.get('cantidad', 0)),
            comentario=request.form.get('comentario', '')
        )
        nuevo_activo.calcular_total() 
    except ValueError:
        abort(400, description="Datos numéricos inválidos en el formulario de maquinarias.")
    
    if nuevo_activo.descripcion:
        caso.inversion.activos_fijos.append(nuevo_activo)
    
    manager.guardar_caso_actual() # Autosave
    return redirect(url_for('nuevo_caso', tab_name='inversion', sub_tab_name='maquinarias'))


@app.route('/api/guardar-diferida', methods=['POST'])
def guardar_diferida():
    """Guarda un registro de Inversión Diferida (Anexo 2)."""
    caso = validar_caso_activo()
    
    try:
        nuevo_item_diferido = InversionDiferidaItem(
            descripcion=request.form.get('descripcion', ''),
            valor_unitario=float(request.form.get('valor_unitario', 0)),
            cantidad=int(request.form.get('cantidad', 0)),
            comentario=request.form.get('comentario', '')
        )
        nuevo_item_diferido.calcular_total()

    except ValueError:
        abort(400, description="Datos numéricos inválidos en el formulario de Inversión Diferida.")

    if nuevo_item_diferido.descripcion:
        caso.inversion.inversion_diferida.append(nuevo_item_diferido)
    
    manager.guardar_caso_actual() # Autosave
    return redirect(url_for('nuevo_caso', tab_name='inversion', sub_tab_name='diferida'))


@app.route('/api/guardar-capital', methods=['POST'])
def guardar_capital():
    """Guarda un registro de Capital de Trabajo (Anexo 3)."""
    caso = validar_caso_activo()
    
    try:
        nuevo_item_capital = CapitalTrabajoItem(
            descripcion=request.form.get('descripcion', ''),
            valor_unitario=float(request.form.get('valor_unitario', 0)),
            cantidad=int(request.form.get('cantidad', 0))
        )
        nuevo_item_capital.calcular_total()

    except ValueError:
        abort(400, description="Datos numéricos inválidos en el formulario de Capital de Trabajo.")

    if nuevo_item_capital.descripcion:
        caso.inversion.capital_trabajo_items.append(nuevo_item_capital)

    manager.guardar_caso_actual() # Autosave
    return redirect(url_for('nuevo_caso', tab_name='inversion', sub_tab_name='capital'))


@app.route('/api/guardar-proyeccion', methods=['POST'])
def guardar_proyeccion():
    """Guarda los datos de la Proyección (usa JSON para el recálculo AJAX)."""
    caso = validar_caso_activo()
    try:
        demanda_inicial = float(request.form.get('demanda_inicial', 0))
        tasa_crecimiento = float(request.form.get('tasa_crecimiento', 0))
        num_proyeccion = int(request.form.get('num_proyeccion', 5))
        
        if num_proyeccion < 1 or num_proyeccion > 20: 
             return jsonify({'success': False, 'message': 'El número de años debe estar entre 1 y 20.'}), 400

    except ValueError:
        return jsonify({'success': False, 'message': 'Datos de entrada inválidos.'}), 400

    datos_proyeccion = DatosProyeccion(
        demanda_inicial=demanda_inicial,
        tasa_crecimiento=tasa_crecimiento,
        num_proyeccion=num_proyeccion
    )

    resultados = calcular_proyeccion(datos_proyeccion)
    datos_proyeccion.resultados_proyeccion = resultados
    caso.proyeccion = datos_proyeccion
    
    manager.guardar_caso_actual() # Autosave
    return jsonify({
        'success': True, 
        'resultados': resultados,
        'num_proyeccion': num_proyeccion
    })


@app.route('/api/guardar-rol-config', methods=['POST'])
def guardar_rol_config():
    """Actualiza el número de años de proyección y reconstruye las tablas del Rol de Pagos."""
    caso = validar_caso_activo()
    try:
        num_proyeccion_rol = int(request.form.get('num_proyeccion_rol', 5))
        if num_proyeccion_rol < 1 or num_proyeccion_rol > 20: 
             abort(400, description="El número de años debe estar entre 1 y 20.")
        caso.proyeccion.num_proyeccion = num_proyeccion_rol
        
    except ValueError:
        abort(400, description="Dato de años inválido.")
    regenerar_proyeccion_rol(caso)
    
    return redirect(url_for('nuevo_caso', tab_name='rol-pagos'))


@app.route('/api/guardar-rol-cargo', methods=['POST'])
def guardar_rol_cargo():
    """Guarda un nuevo cargo en la lista base y reconstruye la proyección."""
    caso = validar_caso_activo()
    try:
        nuevo_cargo = ItemRolPagos(
            cargo=request.form.get('cargo', ''),
            sueldo_nominal=float(request.form.get('sueldo_nominal', 0)),
            dias_trabajados=int(request.form.get('dias_trabajados', 30)),
            no_he=float(request.form.get('no_he', 0)),
            no_hs=float(request.form.get('no_hs', 0)),
            no_jn=float(request.form.get('no_jn', 0)),
            comisiones=float(request.form.get('comisiones', 0)),
            anticipos=float(request.form.get('anticipos', 0)),
            descuentos=float(request.form.get('descuentos', 0)),
            quincenas=float(request.form.get('quincenas', 0))
        )
        nuevo_cargo.calcular_rol() 

    except ValueError:
        abort(400, description="Datos numéricos inválidos en el formulario de Rol de Pagos.")
    caso.rol_pagos.proyeccion_anual[0].items.append(nuevo_cargo)
    regenerar_proyeccion_rol(caso)
    
    manager.guardar_caso_actual() # Autosave
    return redirect(url_for('nuevo_caso', tab_name='rol-pagos'))


@app.route('/api/guardar-consumo-mensual', methods=['POST'])
def guardar_consumo_mensual():
    caso = validar_caso_activo()
    try:
        consumo = float(request.form.get('consumo_kwh', 0))
        nuevo_registro = RegistroConsumoMensual(
            consumo_kwh=consumo,
            costo_usd=consumo * 100
        )
        caso.inversion.consumos_mensuales.append(nuevo_registro)
        
        # Sincronización automática con Capital de Trabajo (Anexo 3)
        if len(caso.inversion.consumos_mensuales) == 1:
            item_electrico = CapitalTrabajoItem(
                descripcion="Consumo electrico",
                valor_unitario=nuevo_registro.costo_usd,
                cantidad=1
            )
            item_electrico.calcular_total()
            caso.inversion.capital_trabajo_items.append(item_electrico)
            sincronizar_total_capital_trabajo(caso.inversion)

    except ValueError:
        abort(400, description="Valores numéricos inválidos")
    return redirect(url_for('nuevo_caso', tab_name='inversion', sub_tab_name='energetico'))


@app.route('/api/guardar-consumo-diario', methods=['POST'])
def guardar_consumo_diario():
    caso = validar_caso_activo()
    try:
        diario = float(request.form.get('consumo_diario', 0))
        costo_unitario = float(request.form.get('costo_kwh', 0))
        anual = diario * 365
        
        nuevo_registro = RegistroConsumoDiario(
            consumo_diario=diario,
            anual=anual,
            costo_kwh=costo_unitario,
            total=anual * costo_unitario
        )
        caso.inversion.consumos_diarios.append(nuevo_registro)
    except ValueError:
        abort(400, description="Valores numéricos inválidos")
    return redirect(url_for('nuevo_caso', tab_name='inversion', sub_tab_name='energetico'))


@app.route('/api/actualizar-financiamiento', methods=['POST'])
def actualizar_financiamiento():
    caso = validar_caso_activo()
    data = request.get_json()
    caso.financiamiento.porcentaje_propio = float(data.get('propio', 75))
    caso.financiamiento.porcentaje_externo = 100 - caso.financiamiento.porcentaje_propio
    manager.guardar_caso_actual() # Autosave
    return jsonify({
        'propio': caso.financiamiento.porcentaje_propio,
        'externo': caso.financiamiento.porcentaje_externo
    })


@app.route('/api/guardar-porcentaje-financiamiento', methods=['POST'])
def guardar_porcentaje():
    caso = validar_caso_activo()
    data = request.get_json()
    
    try:
        propio = float(data.get('propio', 75))
        caso.financiamiento.porcentaje_propio = propio
        caso.financiamiento.porcentaje_externo = 100 - propio
        manager.guardar_caso_actual() # Autosave
        return jsonify({'success': True})
    except ValueError:
        return jsonify({'success': False}), 400


@app.route('/api/wacc/anhadir-fila', methods=['POST'])
def wacc_anhadir_fila():
    caso = validar_caso_activo()
    num_anos = caso.proyeccion.num_proyeccion
    nombre_defecto = "Nueva Empresa"
    
    caso.wacc.tabla_utilidad.append(ItemWacc(nombre=nombre_defecto, valores_anuales=[0.0] * num_anos))
    caso.wacc.tabla_patrimonio.append(ItemWacc(nombre=nombre_defecto, valores_anuales=[0.0] * num_anos))
    
    manager.guardar_caso_actual() # Autosave
    return jsonify({'success': True})


@app.route('/api/wacc/guardar-nombre', methods=['POST'])
def wacc_guardar_nombre():
    caso = validar_caso_activo()
    data = request.json
    idx, nuevo_nombre = data['fila'], data['valor']
    
    caso.wacc.tabla_utilidad[idx].nombre = nuevo_nombre
    caso.wacc.tabla_patrimonio[idx].nombre = nuevo_nombre
    manager.guardar_caso_actual() # Autosave
    return jsonify({'success': True})


@app.route('/api/wacc/guardar-celda', methods=['POST'])
def wacc_guardar_celda():
    caso = validar_caso_activo()
    data = request.json
    tipo, fila_idx, col_idx = data['tipo'], data['fila'], data['col']
    valor = str(data['valor'])
    
    # Sincronización de nombres (columna 0)
    if col_idx == 0:
        if fila_idx < len(caso.wacc.tabla_utilidad):
            caso.wacc.tabla_utilidad[fila_idx].nombre = valor
        if fila_idx < len(caso.wacc.tabla_patrimonio):
            caso.wacc.tabla_patrimonio[fila_idx].nombre = valor
    else:
        # Guardado de valores numéricos
        target_table = caso.wacc.tabla_utilidad if tipo == 'utilidad' else caso.wacc.tabla_patrimonio
        try:
            val_float = float(valor.replace(',', ''))
            target_table[fila_idx].valores_anuales[col_idx - 1] = val_float
        except ValueError:
            pass
    return jsonify({'success': True})



@app.route('/api/guardar-depreciacion-activo', methods=['POST'])
def guardar_depreciacion_activo():
    caso = validar_caso_activo()
    try:
        data = request.get_json()
        idx = int(data.get('index', -1))
        
        if 0 <= idx < len(caso.inversion.activos_fijos):
            activo = caso.inversion.activos_fijos[idx]
            activo.dep_tipo = data.get('tipo', '')
            activo.dep_porcentaje_residual = float(data.get('porcentaje_residual', 10.0))
            activo.dep_monto_valor_residual_pct = float(data.get('monto_residual_pct', 100.0))
            manager.guardar_caso_actual() # Autosave
            return jsonify({'success': True})
            
    except ValueError:
        pass
        
    return jsonify({'success': False}), 400


@app.route('/api/guardar-amortizacion-diferida', methods=['POST'])
def guardar_amortizacion_diferida():
    caso = validar_caso_activo()
    try:
        data = request.get_json()
        idx = int(data.get('index', -1))
        anios = int(data.get('anios', 5))
        
        if 0 <= idx < len(caso.inversion.inversion_diferida):
            item = caso.inversion.inversion_diferida[idx]
            item.amort_anios = anios
            manager.guardar_caso_actual() # Autosave
            return jsonify({'success': True})
            
    except ValueError:
        pass
        
    return jsonify({'success': False}), 400


@app.route('/api/guardar-amortizacion', methods=['POST'])
def guardar_amortizacion():
    caso = manager.obtener_caso_actual()
    data = request.get_json()
    
    caso.amortizacion.interes_anual = float(data.get('interes_anual', 0))
    caso.amortizacion.institucion = data.get('institucion', "")
    caso.amortizacion.anios = int(data.get('anios', 5))
    
    manager.guardar_caso_actual() # Autosave
    return jsonify({'success': True})

        
# -------------------------------------------------------------------
# FIN DEL ARCHIVO
# -------------------------------------------------------------------
if __name__ == '__main__':
    print("Iniciando servidor Flask en http://127.0.0.1:5000/")
    app.run(debug=True)