# Publicar la aplicación

La interfaz React se publica en Netlify. La API FastAPI y el procesamiento de
PDF se ejecutan en Render, con un disco persistente para documentos y sesiones.
Netlify no ejecuta este backend Python ni puede acceder a carpetas de tu PC.

## 1. Publicar el backend en Render

1. Sube este repositorio a un repositorio Git privado en GitHub.
2. En Render, crea un servicio desde el Blueprint del repositorio. Render leerá
   `render.yaml`, instalará `requirements.txt` y arrancará FastAPI.
3. Guarda la URL asignada, por ejemplo `https://mineria-academica-api.onrender.com`.
4. En el servicio Render, define `FRONTEND_ORIGINS` con el origen del sitio
   Netlify, sin ruta final, por ejemplo `https://mineria-academica.netlify.app`.
   Puedes separar varios orígenes con comas.

El disco se monta en `/var/data`. En el primer inicio se copian allí las carpetas
incluidas en `backend/documentos`; las cargas posteriores y las sesiones se
guardan en ese disco.

## 2. Publicar el frontend en Netlify

1. En Netlify, importa el mismo repositorio.
2. Netlify detectará `netlify.toml`: base `web`, comando `npm run build` y
   directorio publicado `dist`.
3. En **Site configuration > Environment variables**, crea
   `VITE_API_URL` con la URL pública del backend Render, sin `/` final.
4. Despliega el sitio y copia su dominio `https://...netlify.app`.
5. Añade ese dominio en la variable `FRONTEND_ORIGINS` de Render y reinicia el
   servicio.

Comprueba `https://TU-API.onrender.com/api/health`; debe responder con
`{"status":"ok","service":"mineria-academica"}`. Luego abre el dominio
Netlify, elige un tema y analiza su carpeta.

## Seguridad y persistencia

El backend actual no tiene autenticación. Aunque CORS se limite al dominio
Netlify, la API puede ser llamada por otros clientes directamente. No publiques
documentos sensibles ni uses esta configuración para usuarios públicos sin
añadir autenticación y límites de abuso. Conserva el repositorio privado si
contiene documentos que no deben distribuirse: los archivos de
`backend/documentos` se copian al backend al inicializar el disco.

El disco persistente requiere un plan de Render que lo admita y puede tener un
costo. No elimines ese disco al reiniciar o redeplegar: contiene los documentos
cargados y los resultados guardados.