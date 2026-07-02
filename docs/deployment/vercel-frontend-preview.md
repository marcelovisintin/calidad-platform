# Preview de frontend en Vercel

## Objetivo

Probar el frontend React en Vercel como entorno de preview externo.

Esta opcion no reemplaza el despliegue productivo local completo, porque el sistema necesita:

- backend Django
- PostgreSQL
- archivos media persistentes
- logs y backups operativos

Vercel es adecuado para servir el frontend estatico. El backend debe quedar desplegado aparte y accesible por HTTPS.

## Arquitectura de prueba

```text
Vercel
  |
  |- React frontend
  |
  v
Backend Django publico o expuesto por tunel HTTPS
  |
  v
PostgreSQL + media
```

## Configuracion agregada

Se agrego:

```text
frontend/vercel.json
```

Con:

- `npm ci` como install command
- `npm run build` como build command
- `dist` como output directory
- rewrite a `index.html` para rutas SPA

## Crear proyecto en Vercel

Al importar el repositorio:

- Framework Preset: `Vite`
- Root Directory: `frontend`
- Install Command: `npm ci`
- Build Command: `npm run build`
- Output Directory: `dist`

## Variable de entorno obligatoria

Si el backend no esta en la misma origin que Vercel, configurar en Vercel:

```env
VITE_API_BASE_URL=https://URL_PUBLICA_DEL_BACKEND/api/v1
```

Ejemplos:

```env
VITE_API_BASE_URL=https://calidad-api.midominio.com/api/v1
```

o para una prueba con tunel:

```env
VITE_API_BASE_URL=https://xxxx.trycloudflare.com/api/v1
```

Importante: en Vite, las variables visibles para el frontend deben empezar con `VITE_`.

## Ajustes necesarios en Django

El backend debe aceptar el dominio de Vercel:

```env
DJANGO_ALLOWED_HOSTS=calidad-srv,localhost,127.0.0.1,URL_PUBLICA_DEL_BACKEND
DJANGO_CSRF_TRUSTED_ORIGINS=https://URL_PUBLICA_DEL_BACKEND,https://TU_APP.vercel.app
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://TU_APP.vercel.app
```

Para preview temporales de Vercel se puede usar una regex controlada:

```env
CORS_ALLOWED_ORIGIN_REGEXES=https://.*\.vercel\.app
```

Usar esto solo para pruebas, no como regla final productiva.

## Limitacion principal

Si se despliega solo Vercel sin backend publico:

- carga la pantalla
- abre rutas del frontend
- falla login
- fallan catalogos, dashboard, anomalías, acciones y adjuntos

Esto ocurre porque `/api/v1` quedaria apuntando al dominio de Vercel y no al backend Django.

## Camino recomendado para prueba rapida

1. Levantar backend en la Raspberry o PC local.
2. Exponerlo temporalmente por HTTPS con un tunel.
3. Configurar `VITE_API_BASE_URL` en Vercel apuntando al tunel.
4. Agregar el dominio de Vercel en `CORS_ALLOWED_ORIGINS`.
5. Probar login y flujos principales.

## Camino recomendado para piloto real

Para piloto productivo:

- frontend y backend juntos en Raspberry con Nginx, o
- frontend en Vercel y backend en VPS/servidor publicado con HTTPS

Para entorno industrial local-first, sigue siendo preferible Raspberry/servidor local con Nginx si el uso sera dentro de planta.
