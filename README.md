# Publicador de AiPedidos

Publica en Instagram y Facebook, a su hora, lo que está en `cola/`. Corre gratis en GitHub Actions cada 15 minutos con la API oficial de Meta.

- `cola/`: una publicación por archivo `.json` (cuándo, tipo, archivos y texto).
- `media/`: imágenes en JPG y videos en MP4. Se sirven por GitHub Pages.
- `estado/publicados.json`: qué salió, con su id, y qué falló.
- Si algo no sale después de 3 intentos, se abre un issue y te llega un mail.

Tipos: `posteo`, `carrusel`, `reel`, `historia`.

```json
{
  "cuando": "2026-10-19T16:00:00-03:00",
  "tipo": "carrusel",
  "redes": ["instagram", "facebook"],
  "archivos": ["media/2026-10-19/1.jpg", "media/2026-10-19/2.jpg"],
  "texto": "…"
}
```

Configuración (una sola vez): secretos `META_PAGE_TOKEN`, `META_PAGE_ID` y `META_IG_USER_ID`; variable `MEDIA_BASE` con la URL de GitHub Pages del repositorio; Pages activado desde la rama principal.
