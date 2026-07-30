from core.datos.repositorio import RepositorioDatos
from core.modelos.metodologias import resolver_motor_fila
from core.modelos.catalogo_impactos import titulo_desde_modo
from core.modelos.impacto.calculo_activo import calcular_impactos_puerto
from core.impact_models import iteraciones_desde_calculo_activo
from core.modelos.impacto.validacion_puerto import validar_puerto_antes_calculo

d = RepositorioDatos.cargar()
df = d.relacion_impactos
print('=== MAPEO ===')
for _, row in df.iterrows():
    modo = str(row.get('Modos de fallo / Modos de parada',''))
    if 'calado' not in modo.lower():
        continue
    motor, entrada = resolver_motor_fila(row)
    tipo = str(row.get('Tipo de impacto','')).strip()
    act = str(row.get('Activo físico u Operacional','')).strip()
    tit = titulo_desde_modo(modo, variable=str(row.get('Variable','')), tipo_impacto=tipo or None)
    print(f'{act[:35]:35} | {tipo:3} | {motor} | {tit} | fam={entrada.familia if entrada else None}')

print('=== VALIDACION Muelle/calado ===')
v = validar_puerto_antes_calculo(d)
for a in v.avisos:
    s = str(getattr(a,'mensaje',a))
    if 'calado' in s.lower() or 'Muelle' in s or 'PI Falta' in s or 'OPEX Falta' in s:
        print(getattr(a,'nivel','?'), s[:220])

print('=== CALCULO activos con calado ===')
r = calcular_impactos_puerto(d)
for res in r.resultados_por_activo:
    has = res.resultado_calado_pi or res.resultado_calado_opex or res.resultado_calado_capex
    iters = [it.modo_fallo for it in iteraciones_desde_calculo_activo(res)]
    cal = [m for m in iters if 'Calado' in m or 'calado' in m]
    if has or cal:
        print(res.activo, 'PI', bool(res.resultado_calado_pi), 'OPEX', bool(res.resultado_calado_opex), 'CAPEX', bool(res.resultado_calado_capex), cal)
