# Publicador de AiPedidos

Publica en Instagram (@ai_pedidos) y en la página de Facebook AiPedidos, a su hora, lo que está en `cola/`. Corre gratis en GitHub Actions cada 15 minutos con la API oficial de Meta (app «AiPedidos Publicador», separada de la app de WhatsApp).

- `cola/`: una publicación por archivo `.json` (cuándo, tipo, archivos y texto).
- `media/`: imágenes en JPG (las historias en 1080×1920, el feed en 1080×1350) y videos en MP4 H.264 + AAC. Se sirven por GitHub Pages.
- `estado/publicados.json`: qué salió, con su id, y qué falló. Nunca guarda claves.
- Si algo no sale después de 3 intentos, se abre un issue y te llega un mail.

Tipos: `posteo`, `carrusel`, `reel` (acepta `portada_ms`), `historia`.

```json
{
  "cuando": "2026-10-19T16:00:00-03:00",
  "tipo": "carrusel",
  "redes": ["instagram", "facebook"],
  "archivos": ["media/2026-10-19-carrusel-1.jpg", "media/2026-10-19-carrusel-2.jpg"],
  "texto": "…"
}
```

## Probar a mano

En Actions → «Publicar en Instagram y Facebook» → Run workflow, con `modo`:

- `probar`: verifica las claves y lista la cola, sin publicar.
- `simular`: muestra qué publicaría ahora.
- `publicar`: publica lo vencido (lo mismo que hace cada 15 minutos).

## Configuración

- Secretos: `META_PAGE_TOKEN` (clave de la página, no vence), `META_PAGE_ID`, `META_IG_USER_ID`.
- Variable: `MEDIA_BASE` = `https://jorgeayague-hub.github.io/aipedidos-redes`.
- Pages activado desde `main`, carpeta raíz.

## Mantenimiento

Meta corta el acceso a datos si pasan 90 días sin que el administrador vuelva a autorizar la app. Cada ~80 días: Explorador de la API Graph → app «AiPedidos Publicador» → «Generate Access Token» con los mismos permisos (pages_show_list, pages_read_engagement, pages_manage_posts, instagram_basic, instagram_content_publish, business_management). No hace falta cambiar el secreto. Si alguna vez cambia la contraseña de Facebook, hay que generar una clave de página nueva y reemplazar `META_PAGE_TOKEN`.
