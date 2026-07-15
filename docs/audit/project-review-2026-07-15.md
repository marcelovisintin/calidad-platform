# Revision integral del proyecto - 2026-07-15

## Alcance

Revision estatica y funcional de backend Django/DRF, frontend React/Vite, autenticacion, permisos, cargas de archivos, PWA, Nginx, Docker Compose y dependencias. La version previa a las correcciones quedo respaldada en GitHub con el commit `878e6a4`.

## Correcciones aplicadas

- Se impide usar las API de negocio mientras el usuario conserve una contrasena temporal; solo quedan habilitados sesion, cierre de sesion y cambio de contrasena.
- Se reemplazo la contrasena inicial compartida por claves temporales aleatorias de 16 caracteres. Se muestran una sola vez al administrador y se incluyen en el reporte de usuarios nuevos importados.
- Los niveles `administrador` y `desarrollador` recuperan el acceso global esperado aun sin alcances sectoriales cargados.
- Se centralizo la validacion de evidencias y fotos: extension, MIME, tamano configurable y MIME almacenado derivado del archivo, no del cliente.
- Los filtros de fecha invalidos ahora responden `400` con el campo afectado, en lugar de ignorarse silenciosamente.
- El service worker dejo de cachear `/api/` y `/media/`, evitando datos autenticados obsoletos o expuestos sin conexion.
- La descarga autenticada rechaza origenes externos no configurados y ya no previsualiza texto activo en el navegador.
- Nginx conserva el puerto del host al generar enlaces, no expone `/media/`, no cachea `sw.js` y tiene healthcheck real en Compose.
- Se deshabilitaron source maps de produccion.
- El script de arranque aborta si falla Docker y permite inyectar una CA corporativa como secreto BuildKit sin copiarla a las imagenes.
- Django se actualizo a `5.2.16`; Vite, React Router y dependencias transitivas npm se actualizaron dentro de sus rangos compatibles.
- Se eliminaron validadores duplicados, imports y variables sin uso, y una captura de excepcion demasiado amplia.

## Verificacion final

- Backend: `88/88` pruebas aprobadas con PostgreSQL real en Docker.
- Django: system check sin errores y sin migraciones pendientes.
- Python: Ruff sin errores.
- Frontend: TypeScript, sintaxis del service worker y build de produccion aprobados con Vite `6.4.3`.
- Dependencias: `npm audit` sin vulnerabilidades; las 13 versiones Python instaladas consultadas en [OSV](https://osv.dev/) sin vulnerabilidades reportadas.
- Despliegue: `db`, `backend` y `frontend` saludables; HTTP y HTTPS responden `200`; API health `200`; endpoint autenticado sin token `401`.
- Nginx: configuracion valida, healthcheck `text/plain` y sin source maps publicados.
- Navegador: Edge headless confirma que `/dashboard` sin sesion redirige al login.

## Riesgos residuales conscientes

- El backend aun ejecuta el proceso como `root` dentro del contenedor. Cambiarlo requiere definir ownership estable para los volumenes montados en Windows antes de activarlo.
- HTTP sigue habilitado para operacion local. En una LAN no confiable se debe usar HTTPS con certificados confiables y luego evaluar `SECURE_SSL_REDIRECT`.
- El frontend no tiene todavia una suite E2E completa; la cobertura actual combina pruebas API/de dominio, build estricto y smoke test real de navegador.
- La CA de inspeccion TLS de Avast no cumple la restriccion `Basic Constraints` de Python 3.14. No se desactivo TLS: la auditoria se completo contra OSV usando el almacen confiable de Windows.
