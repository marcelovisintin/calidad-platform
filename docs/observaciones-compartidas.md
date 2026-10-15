# Observaciones compartidas

## Asociación desde Seguimiento de anomalías

ADMIN puede elegir **Asociar anomalías → Observación existente**.
La confirmación clasifica el hallazgo como OBS y adopta el responsable y el
avance de la observación seleccionada. Se exige un motivo que explique por qué
las acciones cubren el nuevo hallazgo.

- El destino debe estar abierto, con gestión inicial o acciones pendientes.
- No se admiten destinos cerrados, anulados, eficaces, derivados a tratamiento
  o pendientes de verificación con todas las acciones finalizadas.
- Una NC requiere revisión administrativa previa; la asociación no la degrada
  automáticamente a OBS.
- No se fusionan anomalías con acciones, evidencias de ejecución, tratamientos
  ni gestión propia iniciada. Tampoco se admiten grupos anidados.

## Gestión y trazabilidad

Cada anomalía conserva su identidad, registrador, datos originales e historial.
Una referencia a la observación principal comparte las acciones sin duplicarlas.
Las acciones y notas de ejecución se registran una sola vez; el avance queda
documentado en cada hallazgo. Las evidencias compartidas de acciones pueden
consultarse desde los hallazgos asociados. Los archivos originales del registro
de otro hallazgo mantienen sus permisos.

Los plazos no se reinician al asociar. Se informa la fecha vigente y se advierte
si está vencida. La fecha anterior queda registrada en el historial.

La asociación avisa al responsable de la observación y retira las tareas
independientes sustituidas. Los avisos de vencimiento se calculan sobre las
obligaciones originales, sin multiplicarse por la cantidad de hallazgos.

## Eficacia, separación y tratamiento

La verificación eficaz exige confirmar la cobertura de todos los hallazgos
actualmente asociados. El servidor valida esa lista antes de cerrar el conjunto.
Un resultado no eficaz mantiene el conjunto abierto para nuevas acciones.

ADMIN puede separar un hallazgo abierto desde su detalle, indicando motivo y
fecha límite de la gestión independiente. El vínculo anterior queda en ambos
historiales; las acciones y evidencias permanecen en la observación original.
Para derivar una observación compartida a tratamiento se deben separar primero
sus hallazgos y definir su gestión administrativa.

## Compatibilidad

La migración 0024 agrega una referencia opcional; las observaciones existentes
siguen funcionando individualmente. Las listas de operación muestran una gestión
por observación; Seguimiento conserva cada hallazgo. Se mantiene la nota de lo
realizado obligatoria al finalizar acciones y los archivos opcionales.
