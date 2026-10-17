"""Publicador de AiPedidos: publica en Instagram y Facebook lo que está en la cola, a su hora.

Lee cada archivo de cola/*.json, publica lo que ya venció y anota el resultado en estado/publicados.json.
Corre en GitHub Actions cada 15 minutos. Usa la API oficial de Meta (Graph API).

Variables de entorno:
  META_PAGE_TOKEN   token de la página (no vence si sale de un token largo de usuario)
  META_PAGE_ID      id de la página de Facebook
  META_IG_USER_ID   id de la cuenta de Instagram profesional vinculada a la página
  MEDIA_BASE        URL pública donde están los archivos (por ejemplo GitHub Pages del repo)
  GRAPH_VERSION     versión de la API (por defecto v23.0)

Uso:
  python publicar.py            publica lo vencido
  python publicar.py --probar   solo verifica las claves y muestra la cola
  python publicar.py --simular  muestra qué publicaría, sin llamar a Meta
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
COLA = RAIZ / "cola"
ESTADO = RAIZ / "estado" / "publicados.json"
VERSION = os.environ.get("GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
TOKEN = os.environ.get("META_PAGE_TOKEN", "")
PAGE = os.environ.get("META_PAGE_ID", "")
IG = os.environ.get("META_IG_USER_ID", "")
MEDIA_BASE = os.environ.get("MEDIA_BASE", "").rstrip("/")
MAX_INTENTOS = 3
TIPOS = {"posteo", "carrusel", "reel", "historia"}


class ErrorMeta(Exception):
    pass


def llamar(metodo, url, **kw):
    """Llama a la API y devuelve el JSON; si Meta devuelve error, lo levanta con el mensaje."""
    kw.setdefault("timeout", 120)
    r = requests.request(metodo, url, **kw)
    try:
        data = r.json()
    except ValueError:
        data = {"texto": r.text[:300]}
    if r.status_code >= 400 or (isinstance(data, dict) and "error" in data):
        err = data.get("error", data) if isinstance(data, dict) else data
        raise ErrorMeta(f"{r.status_code} {json.dumps(err, ensure_ascii=False)[:400]}")
    return data


def post(ruta, **datos):
    datos["access_token"] = TOKEN
    return llamar("POST", f"{GRAPH}/{ruta}", data=datos)


def get(ruta, **params):
    params["access_token"] = TOKEN
    return llamar("GET", f"{GRAPH}/{ruta}", params=params)


def url_publica(archivo):
    return f"{MEDIA_BASE}/{archivo}"


def es_video(archivo):
    return archivo.lower().endswith((".mp4", ".mov"))


# ---------------- Instagram ----------------

def ig_esperar(contenedor, maximo=600):
    """Espera a que Instagram termine de procesar el contenedor (videos sobre todo)."""
    inicio = time.time()
    while True:
        st = get(contenedor, fields="status_code,status")
        code = st.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            raise ErrorMeta(f"Instagram no pudo procesar el archivo: {st.get('status')}")
        if time.time() - inicio > maximo:
            raise ErrorMeta("Instagram tardó demasiado en procesar el archivo")
        time.sleep(10)


def ig_publicar(contenedor):
    ig_esperar(contenedor)
    return post(f"{IG}/media_publish", creation_id=contenedor)["id"]


def instagram(item):
    tipo, archivos, texto = item["tipo"], item["archivos"], item.get("texto", "")
    if tipo == "posteo":
        c = post(f"{IG}/media", image_url=url_publica(archivos[0]), caption=texto)["id"]
    elif tipo == "carrusel":
        hijos = []
        for a in archivos:
            if es_video(a):
                h = post(f"{IG}/media", media_type="VIDEO", video_url=url_publica(a), is_carousel_item="true")["id"]
            else:
                h = post(f"{IG}/media", image_url=url_publica(a), is_carousel_item="true")["id"]
            ig_esperar(h)
            hijos.append(h)
        c = post(f"{IG}/media", media_type="CAROUSEL", children=",".join(hijos), caption=texto)["id"]
    elif tipo == "reel":
        datos = dict(media_type="REELS", video_url=url_publica(archivos[0]), caption=texto, share_to_feed="true")
        if item.get("portada_ms") is not None:
            datos["thumb_offset"] = str(int(item["portada_ms"]))
        c = post(f"{IG}/media", **datos)["id"]
    elif tipo == "historia":
        a = archivos[0]
        if es_video(a):
            c = post(f"{IG}/media", media_type="STORIES", video_url=url_publica(a))["id"]
        else:
            c = post(f"{IG}/media", media_type="STORIES", image_url=url_publica(a))["id"]
    else:
        raise ErrorMeta(f"tipo desconocido: {tipo}")
    return ig_publicar(c)


# ---------------- Facebook ----------------

def fb_subir_video(endpoint, archivo, final):
    """Reels e historias en video de la página: inicio, carga por URL y cierre."""
    inicio = post(f"{PAGE}/{endpoint}", upload_phase="start")
    video_id, destino = inicio["video_id"], inicio["upload_url"]
    llamar("POST", destino, headers={"Authorization": f"OAuth {TOKEN}", "file_url": url_publica(archivo)})
    fin = post(f"{PAGE}/{endpoint}", upload_phase="finish", video_id=video_id, **final)
    return fin.get("post_id") or fin.get("id") or video_id


def fb_foto_sin_publicar(archivo):
    return post(f"{PAGE}/photos", url=url_publica(archivo), published="false")["id"]


def facebook(item):
    tipo, archivos, texto = item["tipo"], item["archivos"], item.get("texto", "")
    if tipo == "posteo":
        r = post(f"{PAGE}/photos", url=url_publica(archivos[0]), caption=texto)
        return r.get("post_id") or r["id"]
    if tipo == "carrusel":
        fotos = [fb_foto_sin_publicar(a) for a in archivos if not es_video(a)]
        adjuntos = json.dumps([{"media_fbid": f} for f in fotos])
        return post(f"{PAGE}/feed", message=texto, attached_media=adjuntos)["id"]
    if tipo == "reel":
        return fb_subir_video("video_reels", archivos[0], {"video_state": "PUBLISHED", "description": texto})
    if tipo == "historia":
        a = archivos[0]
        if es_video(a):
            return fb_subir_video("video_stories", a, {})
        foto = fb_foto_sin_publicar(a)
        r = post(f"{PAGE}/photo_stories", photo_id=foto)
        return r.get("post_id") or r.get("id") or foto
    raise ErrorMeta(f"tipo desconocido: {tipo}")


RED = {"instagram": instagram, "facebook": facebook}


# ---------------- cola y estado ----------------

def cargar_cola():
    items = []
    for f in sorted(COLA.glob("*.json")):
        item = json.loads(f.read_text(encoding="utf-8"))
        item.setdefault("id", f.stem)
        item.setdefault("redes", ["instagram", "facebook"])
        if item.get("tipo") not in TIPOS:
            print(f"!! {f.name}: tipo inválido {item.get('tipo')!r}")
            continue
        item["_cuando"] = datetime.fromisoformat(item["cuando"])
        items.append(item)
    return sorted(items, key=lambda x: x["_cuando"])


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {}


def guardar_estado(estado):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probar():
    falta = [n for n, v in (("META_PAGE_TOKEN", TOKEN), ("META_PAGE_ID", PAGE), ("META_IG_USER_ID", IG), ("MEDIA_BASE", MEDIA_BASE)) if not v]
    if falta:
        print("Faltan:", ", ".join(falta))
        return 1
    pagina = get(PAGE, fields="name")
    cuenta = get(IG, fields="username")
    print(f"OK página «{pagina.get('name')}» e Instagram @{cuenta.get('username')}")
    for it in cargar_cola():
        print(f"  {it['_cuando'].isoformat()}  {it['tipo']:9}  {it['id']}")
    return 0


def main():
    if "--probar" in sys.argv:
        return probar()
    simular = "--simular" in sys.argv
    ahora = datetime.now(timezone.utc)
    estado = cargar_estado()
    aviso = RAIZ / "estado" / "aviso.txt"
    if aviso.exists():
        aviso.unlink()
    errores, definitivos = [], []
    for item in cargar_cola():
        if item["_cuando"] > ahora:
            continue
        reg = estado.setdefault(item["id"], {})
        for red in item["redes"]:
            r = reg.setdefault(red, {"ok": False, "intentos": 0})
            if r.get("ok") or r.get("intentos", 0) >= MAX_INTENTOS:
                continue
            if simular:
                print(f"[simular] {red:9} {item['tipo']:9} {item['id']}")
                continue
            r["intentos"] = r.get("intentos", 0) + 1
            try:
                pid = RED[red](item)
                r.update(ok=True, id=pid, publicado=datetime.now(timezone.utc).isoformat(timespec="seconds"))
                r.pop("error", None)
                print(f"OK  {red:9} {item['tipo']:9} {item['id']} -> {pid}")
            except (ErrorMeta, requests.RequestException, KeyError) as e:
                r["error"] = str(e)[:500]
                errores.append(f"{item['id']} ({red}): {r['error']}")
                if r["intentos"] >= MAX_INTENTOS:
                    definitivos.append(f"- {item['id']} en {red}, programado para {item['cuando']}: {r['error']}")
                print(f"ERR {red:9} {item['tipo']:9} {item['id']}: {r['error']}")
            guardar_estado(estado)
    if definitivos:
        aviso.parent.mkdir(parents=True, exist_ok=True)
        aviso.write_text("No se pudo publicar después de varios intentos:\n\n" + "\n".join(definitivos) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
