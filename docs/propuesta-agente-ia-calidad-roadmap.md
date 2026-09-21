# Propuesta: Analista de Calidad Schneider con IA

Mi recomendación es crear un **“Analista de Calidad Schneider”**, empezando con un Gem empresarial para probar su utilidad y preparando una conexión al sistema para los análisis recurrentes.

La mejora principal sería combinar **cálculos verificables sobre toda la base** con **IA para interpretar descripciones, comparar antecedentes y explicar resultados**. Así evitamos que un informe de repitencia dependa solamente de lo que el modelo alcance a leer.

## 1. Cómo aprovecharíamos un Gem

Los Gems permiten definir instrucciones permanentes y agregar archivos de conocimiento, incluidos archivos de Drive. Google indica que, cuando se vincula un archivo de Drive, Gemini utiliza su versión más reciente. Esto permite preparar un piloto con exportaciones actualizadas del sistema. [Documentación de Gems](https://support.google.com/gemini/answer/15146780?hl=en-IN)

Para ese piloto, le daríamos:

- **Expedientes completos:** anomalía, contexto, clasificación, causas, tratamientos, acciones, verificaciones, reaperturas y lecciones aprendidas.
- **Políticas documentadas:** responsables elegibles, plazos, criterios de eficacia y reglas de cada etapa.
- **Diccionario de datos:** qué significa cada campo y cómo se relacionan los registros.
- **Indicadores calculados por el sistema:** cantidades, porcentajes, tiempos y vencimientos, con fecha de corte.

**No asumiría que un Gem convencional puede consultar directamente nuestra base local.** Para una conexión operativa evaluaría Gemini mediante API o, si la empresa ya cuenta con ese producto, Gemini Enterprise y sus conectores. Google documenta conectores personalizados para este último; primero hay que confirmar qué licencia tiene Schneider. [Conectores de Gemini Enterprise](https://cloud.google.com/gemini-enterprise/connectors)

## 2. La solución que recomiendo para uso habitual

Agregar un botón **“Consultar al analista de calidad”** dentro del sistema:

```text
Pregunta + parámetros del usuario
                ↓
Servicio de análisis del sistema
     ├─ Comprueba permisos
     ├─ Calcula indicadores en la base local
     ├─ Busca antecedentes relacionados
     └─ Recupera políticas aplicables
                ↓
Gemini interpreta los resultados
                ↓
Informe con fuentes y enlaces a cada caso
```

La API de Gemini permite solicitar la ejecución de funciones definidas por nuestra aplicación. Nosotros controlaríamos qué consultas puede realizar y qué información recibe. [Documentación de llamadas a funciones](https://ai.google.dev/gemini-api/docs/function-calling)

La base seguiría en el servidor local. La consulta a Gemini necesitaría internet y enviaría únicamente los datos seleccionados para ese análisis. Los permisos se aplicarían en el backend: **escribir una política en las instrucciones del agente no reemplaza el control de acceso del sistema**.

## 3. Qué debería analizar

La repitencia tendría tres niveles:

| Nivel | Qué detecta |
|---|---|
| Coincidencia directa | Mismo desvío, producto, proceso, sector o causa registrada. |
| Similitud de significado | Descripciones distintas que posiblemente representan el mismo problema. |
| Reaparición después del tratamiento | Casos similares que aparecen después de ejecutar acciones o validar su eficacia. |

El tercer nivel sería especialmente útil: permitiría encontrar **problemas que se consideraban resueltos y vuelven a aparecer**.

La IA debería distinguir entre “descripción similar”, “misma causa documentada” y “posible relación pendiente de confirmar”. Una similitud textual no demuestra una causa común.

Podrías cambiar los parámetros en cada consulta:

> “Analizá los últimos 12 meses en revestimiento. Agrupá problemas similares aunque estén redactados distinto. Priorizá los que reaparecieron después de una validación eficaz y mostrame qué acciones se habían tomado.”

Cada respuesta incluiría:

- Período, filtros y cantidad de registros analizados.
- Patrones encontrados y criterio utilizado para agruparlos.
- Antecedentes con código y enlace al detalle.
- Causas documentadas, acciones y resultados de sus validaciones.
- Información faltante e hipótesis que necesitan revisión.
- Recomendaciones sustentadas en esos antecedentes.

## 4. Mejoras que incorporaría

**Consultar antecedentes al registrar una anomalía.** Antes de iniciar otro tratamiento, mostrar casos relacionados, lo que se hizo y el resultado obtenido.

**Guardar análisis reutilizables.** Por ejemplo, “repitencia mensual de revestimiento”, conservando parámetros, fecha de corte y versión de las políticas. Esto permite comparar períodos con el mismo criterio.

**Medir recurrencia después de las acciones.** Examinar ventanas de 30, 60 y 90 días, considerando cuánto tiempo de seguimiento tiene cada caso. Si incorporamos volumen producido o inspeccionado, podremos comparar tasas; con cantidades de anomalías solamente no podemos afirmar que un proceso empeoró.

**Mantener trazabilidad de los ciclos.** Una validación ineficaz y su nuevo tratamiento deben quedar relacionados. De lo contrario, el agente podría presentar el primer intento como la solución definitiva.

## 5. Roadmap propuesto

| Fase | Trabajo | Condición para avanzar |
|---|---|---|
| **1. Definir alcance y datos** | Confirmar licencia, usuarios habilitados, significado de repitencia y relación entre anomalías y ciclos de tratamiento. | Contar con preguntas de referencia y respuestas verificadas por Calidad. |
| **2. Piloto con Gem** | Crear instrucciones, exportación de expedientes y políticas, con fecha de corte. | Que encuentre antecedentes conocidos y cite correctamente sus fuentes. |
| **3. Motor de análisis local** | Implementar filtros, estadísticas, búsqueda de casos similares y detección de recurrencia posterior a acciones. | Que los totales coincidan con la base y se respeten los permisos. |
| **4. Integración en el sistema** | Incorporar el chat, consultas controladas, enlaces a expedientes y registro de análisis. | Poder reproducir un informe con los mismos datos y parámetros. |
| **5. Uso preventivo** | Sugerir antecedentes al registrar casos y generar análisis periódicos. | Validar su utilidad con el equipo antes de ampliar automatizaciones. |

**Empezaría por las fases 1 y 2, dejando preparada la exportación para reutilizarla en la integración.** Las 600 anomalías sintéticas sirven para comprobar funcionamiento; para evaluar si el análisis aporta valor industrial necesitaremos también casos reales revisados por Calidad.

El primer dato a confirmar es **qué edición de Google Workspace/Gemini tiene contratada la empresa**, porque determina cuánto del piloto podemos aprovechar con la cuenta actual y qué integración requeriría contratación adicional.
