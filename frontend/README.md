# Frontend Calidad Platform

Frontend liviano en React + TypeScript para consumir la API DRF del backend de Calidad Platform.

## Stack propuesto

- React + TypeScript
- Vite
- React Router
- JWT contra `/api/v1/accounts/`
- PWA liviana con `manifest.webmanifest` y `sw.js`

## Requisitos locales

- Node.js 20+
- npm 10+

## Scripts

- `npm install`
- `npm run dev`
- `npm run build`
- `npm run check`

## Variables de entorno recomendadas

Crear `frontend/.env` si queres personalizar:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_CATALOG_BOOTSTRAP_URL=/catalog.bootstrap.json
```

## Nota sobre catalogos

Hoy el backend expone `/api/v1/catalog/` desde el root general, pero no tiene endpoints DRF implementados para listar catalogos. Por eso el formulario de nueva anomalia usa un bootstrap estatico desde `public/catalog.bootstrap.json`.

Cuando exista una API real de catalogos, solo hay que reemplazar el servicio de `src/api/catalog.ts` o mantener ese archivo como respaldo offline.
