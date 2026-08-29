# Indicadores del Sistema de Gestion de Calidad

## Objetivo

Crear una unica seccion `Indicadores`, sin separar indicadores oficiales y
complementarios. La seccion debe reunir los indicadores que Calidad utiliza
actualmente y los analisis adicionales que mejoran el seguimiento del sistema.

La primera version sera visible para usuarios con nivel de acceso
`Administrador` o `Desarrollador`. Cada indicador tendra totalizadores,
graficos, listados auditables, exportacion CSV y generacion de un informe para
enviar por correo a usuarios habilitados.

## Estructura general

Dentro del Panel de gestion se incorporara la opcion `Indicadores`. Al abrirla
se mostraran nueve tarjetas con la misma importancia:

1. Anomalias generadas y tratadas.
2. Tratamientos.
3. Anomalias por proceso.
4. Clasificacion de hallazgos.
5. Repetitividad y Pareto.
6. Acciones.
7. Eficacia.
8. Ordenes afectadas.
9. Lecciones aprendidas.

## Logica de los indicadores

### 1. Anomalias generadas y tratadas

Las anomalias generadas se contabilizan por `detected_at`, la fecha de deteccion
registrada en la anomalia.

Se consideran tratadas:

- anomalias cerradas mediante un tratamiento;
- observaciones cerradas despues de registrar acciones y verificar su eficacia;
- observaciones TRT cerradas mediante tratamiento.

Las invalidas, anuladas, reabiertas y pendientes se muestran por separado. Las
invalidas y anuladas no deben mejorar artificialmente el porcentaje de
tratamiento.

Formula principal:

```text
Porcentaje tratado = Anomalias tratadas / Anomalias generadas * 100
```

Se ofrecen dos lecturas:

- Movimiento del periodo: tratadas durante el periodo frente a generadas en el
  mismo periodo. Puede superar el 100 % si se resolvieron pendientes anteriores.
- Seguimiento de cohorte: de las anomalias generadas en el periodo, cuantas ya
  fueron tratadas. Siempre se encuentra entre 0 % y 100 %.

Resultados: cantidades mensuales, acumulado anual, porcentajes, pendientes,
comparacion con el periodo anterior, tiempo promedio de resolucion y listado de
anomalias que compone cada resultado.

### 2. Tratamientos

Se muestran tratamientos creados, pendientes, programados, en curso,
completados, cancelados, pendientes de validacion, eficaces y no eficaces.

Formula confirmada:

```text
Porcentaje de tratamientos completados =
Tratamientos completados / Tratamientos creados * 100
```

Tambien se ofrecen dos lecturas:

- completados durante el periodo frente a creados durante el periodo;
- tratamientos creados en el periodo que ya fueron completados.

Se incluyen cantidades mensuales y anuales, anomalias vinculadas, antiguedad de
tratamientos abiertos, tiempo hasta finalizacion, tiempo hasta verificacion de
eficacia, responsable y comparacion con el periodo anterior.

### 3. Anomalias por proceso

El proceso se obtiene del campo estructurado `area` de la anomalia. Los roles y
alcances de usuario no intervienen en esta clasificacion.

```text
Porcentaje del proceso =
Anomalias del proceso / Total de anomalias del periodo * 100
```

Se muestran cantidad mensual, acumulado anual, participacion porcentual,
variacion, evolucion, Pareto y listado asociado. Cada anomalia se contabiliza
una sola vez.

### 4. Clasificacion de hallazgos

Utiliza el maestro de criterios de revision de hallazgos y no nombres rigidos en
el codigo. Incluye no conformidades, observaciones, observaciones TRT,
oportunidades de mejora, invalidas y casos sin clasificar.

Se presentan cantidades, porcentajes, evolucion mensual, distribucion por
proceso, comparacion anual y listado asociado.

### 5. Repetitividad y Pareto

Permite analizar repeticion por tipo de anomalia, proceso, origen,
clasificacion, orden afectada y combinacion proceso-tipo. Muestra cantidad,
porcentaje individual, porcentaje acumulado, referencia 80/20, variacion y los
casos que forman cada grupo.

### 6. Acciones

Se distinguen acciones directas y acciones surgidas de tratamientos. Se
muestran pendientes, en curso, completadas, canceladas, vencidas y proximas a
vencer, junto con cumplimiento por responsable, proceso y tipo.

```text
Cumplimiento en termino =
Acciones completadas dentro del plazo /
Acciones completadas con fecha comprometida * 100
```

Para medir correctamente las acciones de tratamiento se agregara una fecha real
de finalizacion. Los datos historicos sin fecha verificable no utilizaran
`updated_at` como sustituto.

### 7. Eficacia

Integra tratamientos y observaciones, permitiendo ver ambos caminos por
separado. Incluye verificaciones pendientes, vencidas, eficaces, no eficaces,
reaperturas y resultados por proceso y responsable.

```text
Porcentaje de eficacia =
Verificaciones eficaces / Verificaciones realizadas * 100
```

Las verificaciones pendientes no forman parte del denominador.

### 8. Ordenes afectadas

Reutiliza y amplia la logica existente. Muestra ordenes diferentes, registros,
total de piezas o productos, anomalias involucradas, distribucion por tipo,
proceso, evolucion mensual y Pareto.

Se mantiene la diferencia entre orden unica (tipo y numero), registro de
afectacion y cantidad total de piezas.

### 9. Lecciones aprendidas

Muestra tratamientos eficaces con leccion, tratamientos eficaces sin leccion,
casos sin aprendizaje, procedimientos modificados y procesos que generaron
aprendizajes.

```text
Cobertura de aprendizaje =
Tratamientos eficaces con leccion / Tratamientos eficaces * 100
```

```text
Modificacion documental =
Lecciones con procedimiento modificado / Lecciones registradas * 100
```

## Arquitectura de pantallas

```text
Panel de gestion
    `-- Indicadores
          |-- Anomalias generadas y tratadas
          |-- Tratamientos
          |-- Anomalias por proceso
          |-- Clasificacion de hallazgos
          |-- Repetitividad y Pareto
          |-- Acciones
          |-- Eficacia
          |-- Ordenes afectadas
          `-- Lecciones aprendidas
```

Cada dashboard tendra:

1. encabezado compacto;
2. selector de periodo;
3. filtros apilados compactos;
4. acciones `Exportar CSV` y `Enviar informe`;
5. tarjetas totalizadoras;
6. grafico de evolucion;
7. grafico comparativo o Pareto;
8. tabla paginada;
9. acceso al registro original.

Los graficos utilizaran barras, lineas, Pareto y barras apiladas. Deben ser
responsive, legibles en tablet y conservar los colores y tonos del sistema.

## Reglas comunes de calculo

- Periodos calculados con la zona horaria `America/Buenos_Aires`.
- Fechas desde/hasta inclusivas.
- Porcentajes con un decimal.
- Si el denominador es cero se muestra `Sin base de calculo`, no `0 %`.
- Totalizadores, graficos, tabla, CSV y PDF usan el mismo selector de datos.
- El periodo anterior tiene la misma duracion que el periodo seleccionado.
- Cada pantalla informa si utiliza fecha de deteccion, creacion, cierre,
  vencimiento o validacion.
- Se evitan dobles conteos en tratamientos con varias anomalias.
- Los registros reabiertos se identifican por separado.

## CSV

- Se genera en el backend.
- Incluye todos los registros filtrados, no solo la pagina visible.
- Utiliza UTF-8 con BOM y separador `;`.
- El nombre contiene indicador y periodo.
- Incluye fecha de generacion y filtros aplicados.

## Informe PDF

El informe contiene logo, indicador, periodo, filtros, fecha, usuario generador,
totalizadores, graficos, tabla resumida, formulas e identificador del informe.

## Envio por correo

El selector permite elegir varios usuarios mediante busqueda incremental. Solo
son elegibles usuarios activos, con correo valido y con `Notificacion por
correo` habilitada.

- No hay destinatarios seleccionados por defecto.
- No se permiten correos escritos manualmente.
- Se confirma la cantidad y los nombres antes de encolar el envio.
- El usuario generador recibe una copia automatica si tiene el correo habilitado.
- El PDF se envia adjunto mediante la cola existente.
- Se informa si quedo encolado, entregado, omitido o fallido.
- No se agrega un enlace que pueda confundir sesiones abiertas.
- Al completarse todos los envios, el PDF se elimina del servidor.

## Arquitectura tecnica

Se crea un modulo independiente:

```text
backend/apps/indicators/
    |-- selectors/       Consultas y filtros
    |-- services/        Formulas y agregaciones
    |-- reports/         CSV y PDF
    |-- api/             Endpoints protegidos
    |-- models/          Informes generados
    `-- tests/           Formulas, permisos y exportaciones
```

```text
Dashboard React
      | filtros
      v
API de indicadores
      v
Selector unico de datos
      |-- Totalizadores
      |-- Graficos
      |-- Listado
      |-- CSV
      `-- PDF -> Cola de correo
```

Los calculos se realizan sobre PostgreSQL en tiempo real. No se duplican datos
operativos ni se incorporan servicios externos innecesarios. El PDF solo se
conserva transitoriamente mientras la cola necesita adjuntarlo.

## Auditoria y resguardo

Se registra indicador, periodo, filtros, usuario generador, destinatarios,
cantidad de registros, estado de entrega, fecha, identificador y checksum del
PDF.

El PDF se elimina despues de completar los envios. Si un envio falla, se
conserva transitoriamente para permitir los reintentos y se elimina al vencer
el plazo de contingencia de 30 dias. La metadata y la auditoria permanecen.

## Road map

Estado local al 28/08/2026: fases 1, 2, 3 y 4 implementadas. La fase 3 incorpora
los seis indicadores restantes y agrega `completed_at` nullable a las acciones
surgidas de tratamientos. Solo las finalizaciones registradas desde esta
version participan del calculo de cumplimiento en termino; no se inventan
fechas para datos historicos.

La fase 4 incorpora CSV completo en UTF-8 con BOM y separador punto y coma,
PDF auditado con checksum, destinatarios habilitados, copia al generador,
adjunto por la cola de correo y seguimiento individual de entrega. El PDF se
elimina al completar los envios; si queda fallido, el comando
`purge_expired_indicator_report_files` lo elimina al vencer la contingencia de
30 dias y conserva la metadata y auditoria.

### Fase 1 - Base comun

- Crear el modulo `indicators`.
- Definir permisos, rutas y contratos API.
- Crear la pantalla principal.
- Crear componentes reutilizables de filtros, totalizadores y graficos.
- Crear el modelo auditado de informes.

### Fase 2 - Indicadores minimos actuales

- Anomalias generadas y tratadas.
- Tratamientos creados y completados.
- Anomalias por proceso.
- Validar cantidades y porcentajes con casos controlados.

### Fase 3 - Indicadores restantes

- Clasificacion de hallazgos.
- Repetitividad y Pareto.
- Acciones.
- Eficacia.
- Ordenes afectadas.
- Lecciones aprendidas.

### Fase 4 - Exportacion e informes

- CSV para los nueve dashboards.
- Generacion de PDF.
- Selector multiple de usuarios.
- Integracion con la cola de correo.
- Auditoria y estados de entrega.

### Fase 5 - Validacion integral

- Probar formulas, periodos y zona horaria.
- Probar permisos, CSV, PDF y correo.
- Validar experiencia responsive en PC y tablet.
- Controlar rendimiento con datos reales.

### Fase 6 - Entrega

- Probar sobre la base local historica.
- Comparar resultados con calculos manuales de Calidad.
- Corregir diferencias.
- Commit, push y etiqueta de version.
- Backup y despliegue por hash en produccion.
- Verificar salud y resultados.
