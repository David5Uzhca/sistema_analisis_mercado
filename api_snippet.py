
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
            return jsonify({'success': True})
            
    except ValueError:
        pass
        
    return jsonify({'success': False}), 400
