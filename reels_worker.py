#!/usr/bin/env python3
"""Motor de render del editor de reels del panel Nexia.

Lo ejecuta GitHub Actions (workflow `reels.yml` del repo nexia-dashboard). Habla solo con la API del
dashboard, que le da el trabajo pendiente y un token temporal de Drive:

  Nueva     -> descarga los brutos, los transcribe y manda la transcripción al dashboard,
               que pide a Claude la propuesta de montaje y efectos  -> "Propuesta lista"
  En cola   -> lee el proyecto (JSON en Drive), monta los tramos, añade efectos y subtítulos,
               sube el reel a Drive                                   -> "Para revisar"

Variables de entorno: NEXIA_URL (https://app.somosnexia.com) y NEXIA_WORKER_SECRET.
No imprime transcripciones ni tokens: los logs de Actions se pueden leer.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

import fondo
import sonido

RAIZ = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(RAIZ, ".claude", "skills", "effects", "scripts", "fx.py")
FUENTES = os.path.join(RAIZ, "fonts")
NEXIA = os.environ.get("NEXIA_URL", "https://app.somosnexia.com").rstrip("/")
SECRET = os.environ["NEXIA_WORKER_SECRET"]
W, H, FPS = 1080, 1920, 30

# Efectos que ya muestran el texto en pantalla: mientras están activos no se ponen subtítulos.
OCULTA_SUBS = {"timeline", "reject-stamp", "checklist", "comment-box", "todo", "split-headline", "headline-box",
               "cover-star", "red-collage", "led-sign", "messages", "the-bill", "tier-list", "uninstall", "apple-toggles"}
MAGENTA_ASS = "&H6E20E0&"  # #E0206E en BGR


# ------------------------------------------------------------------ API del dashboard y Drive

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{NEXIA}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode() or "{}")


def update(edicion_id, **campos):
    api("POST", "/api/reels/worker", {"action": "update", "id": edicion_id, **campos})


def drive_download(token, file_id, dst):
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return dst


def drive_json(token, file_id):
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def drive_upload_video(token, path, name, folder_id):
    """Subida reanudable (los reels pesan decenas de MB) y enlace público de lectura para verlo en el panel."""
    size = os.path.getsize(path)
    meta = json.dumps({"name": name, "parents": [folder_id], "mimeType": "video/mp4"}).encode()
    req = urllib.request.Request("https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&fields=id",
                                 data=meta, method="POST", headers={
                                     "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                                     "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(req, timeout=120) as r:
        session = r.headers["Location"]
    with open(path, "rb") as f:
        up = urllib.request.Request(session, data=f.read(), method="PUT", headers={"Content-Type": "video/mp4"})
        with urllib.request.urlopen(up, timeout=1200) as r:
            file_id = json.loads(r.read().decode())["id"]
    perm = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
                                  data=json.dumps({"role": "reader", "type": "anyone"}).encode(), method="POST",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(perm, timeout=60).read()
    except Exception as e:  # sin enlace público el panel no puede previsualizarlo, pero el vídeo existe
        print("aviso: no se pudo abrir el enlace del vídeo:", e)
    return file_id


# ------------------------------------------------------------------ utilidades de vídeo

def run(cmd):
    subprocess.run(cmd, check=True)


def duracion(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def tiene_audio(path):
    """Las grabaciones de pantalla suelen venir sin pista de audio: ni se transcriben ni se pueden pasar por [i:a]."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                         check=True, capture_output=True, text=True).stdout
    return bool(out.strip())


def verde_de_fondo(path):
    """Color del fondo si el bruto está grabado sobre pantalla verde (se mira una esquina del primer fotograma); si no, None."""
    try:
        px = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-vf", "crop=2:2:24:24,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            check=True, capture_output=True).stdout
        r, g, b = px[0], px[1], px[2]
    except Exception:
        return None
    return f"0x{r:02X}{g:02X}{b:02X}" if g > r + 40 and g > b + 40 else None


def fotogramas(path, dur, n=6):
    """n fotogramas pequeños (JPEG en base64) repartidos por el vídeo, para que el dashboard detecte subtítulos ya quemados."""
    import base64
    out = []
    for k in range(n):
        t = max(0.0, dur * (k + 0.5) / n)
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                            "-vf", "scale=360:-2", "-q:v", "6", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                           capture_output=True)
        if r.returncode == 0 and r.stdout:
            out.append(base64.b64encode(r.stdout).decode())
    return out


_modelo = None

# Nombres que Whisper suele destrozar. A estos se suman los del guion de cada pieza.
VOCABULARIO = ["Nexia", "Somos Nexia", "somosnexia", "Claude", "ChatGPT", "Gemini", "ManyChat", "CapCut", "Notion", "Make",
               "Metricool", "Instagram", "TikTok", "LinkedIn", "WhatsApp", "Canva", "IA", "DMs", "reel", "radar", "Submarino"]


def pistas(indicaciones):
    """Vocabulario de ayuda para el transcriptor: el de siempre más los nombres propios y siglas del guion."""
    propios = re.findall(r"(?<![\.\?!:¿¡]\s)(?<![¿¡\"«])(?<!^)\b([A-ZÁÉÍÓÚÑ][\wáéíóúñ]*[A-Z0-9]?[\wáéíóúñ]*)\b", indicaciones or "", flags=re.M)
    vistos = []
    for p in VOCABULARIO + propios:
        if len(p) > 1 and p not in vistos:
            vistos.append(p)
    return ", ".join(vistos[:60])


def modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        nombre = os.environ.get("WHISPER_MODEL", "large-v3-turbo")
        try:
            _modelo = WhisperModel(nombre, device="cpu", compute_type="int8")
        except Exception as e:  # sin el modelo grande se sigue con el de antes antes que dejar el reel sin hacer
            print(f"aviso: no se pudo cargar {nombre} ({e}); se usa small")
            _modelo = WhisperModel("small", device="cpu", compute_type="int8")
    return _modelo


def transcribir(path, indicaciones=""):
    if not tiene_audio(path):
        return []  # vídeo sin sonido (p. ej. grabación de pantalla): no hay nada que transcribir
    # El audio se saca con ffmpeg (16 kHz mono) y no con PyAV: faster-whisper choca con algunas versiones de av.
    audio = sonido.audio_de(path)
    # Sin arrastrar el texto anterior: así no se inventa bucles y respeta mejor las repeticiones (que luego se cortan).
    segs, _ = modelo().transcribe(audio, language="es", word_timestamps=True, vad_filter=True,
                                  condition_on_previous_text=False,
                                  # Una frase bien puntuada como pista: así escribe los nombres y además pone comas y puntos.
                                  hotwords=f"Hola, ¿qué tal? Hoy te hablo de {pistas(indicaciones)}. Vale, empezamos.")
    palabras = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]
    return sonido.ajustar_palabras(palabras, audio)


# ------------------------------------------------------------------ paso 1: transcripción y propuesta

def preparar(job, token, tmp):
    update(job["id"], estado="Transcribiendo", error="")
    brutos, frames, omitidos = [], [], []
    for i, fid in enumerate(job["brutos"]):
        src = drive_download(token, fid, os.path.join(tmp, f"b{i}.mp4"))
        try:
            dur = round(duracion(src), 2)
        except subprocess.CalledProcessError:
            # Subida vacía o corrupta en Drive: se salta ese bruto y el resto sigue adelante.
            print(f"  bruto {i + 1}/{len(job['brutos'])} ({fid}): archivo vacío o ilegible ({os.path.getsize(src)} bytes), se omite")
            omitidos.append(fid)
            continue
        brutos.append({"id": fid, "duration": dur, "words": transcribir(src, job.get("indicaciones", ""))})
        try:
            frames.append(fotogramas(src, brutos[-1]["duration"]))
        except Exception:
            frames.append([])
        print(f"  bruto {i + 1}/{len(job['brutos'])}: {brutos[-1]['duration']} s, {len(brutos[-1]['words'])} palabras")
    if not brutos:
        raise ValueError("Ningún vídeo en bruto se puede leer (archivos vacíos o dañados en Drive). Vuelve a subirlos.")
    api("POST", "/api/reels/worker", {"action": "propose", "id": job["id"], "brutos": brutos, "frames": frames})


# ------------------------------------------------------------------ paso 2: render

def ajustar_a_palabras(proyecto):
    """Nunca cortar una palabra: si un tramo empieza o acaba a mitad de palabra, se abre hasta incluirla entera."""
    for s in proyecto["segments"]:
        b = proyecto["brutos"][s["bruto"]]
        a, e = float(s["start"]), float(s["end"])
        words = b["words"]
        for i, w in enumerate(words):
            # Se incluye la palabra entera sin arrastrar la de al lado (el panel aplica esta misma regla).
            if w["s"] < a < w["e"] - 0.03:
                a = max(w["s"] - 0.08, min(words[i - 1]["e"] if i else 0.0, w["s"]))
            if w["s"] < e - 0.03 and w["e"] > e:
                e = min(w["e"] + 0.15, max(words[i + 1]["s"] if i + 1 < len(words) else float(b["duration"]), w["e"]))
        s["start"], s["end"] = round(max(0.0, a), 3), round(min(float(b["duration"]), e), 3)


def afinar_cortes(proyecto, rutas, segs):
    """Cada corte se lleva al punto más callado de al lado y se cuadra con los fotogramas (así imagen y sonido duran igual)."""
    medidas = {}
    for s in segs:
        i = s["bruto"]
        b = proyecto["brutos"][i]
        a, e = float(s["start"]), float(s["end"])
        dentro = [k for k, w in enumerate(b["words"]) if w["s"] >= a - 0.02 and w["e"] <= e + 0.08]
        if dentro and tiene_audio(rutas[i]):
            if i not in medidas:
                medidas[i] = sonido.volumen(sonido.audio_de(rutas[i]))
            p, u = dentro[0], dentro[-1]
            a, e = sonido.afinar_corte(medidas[i], a, e, (b["words"][p]["s"], b["words"][p]["e"]), (b["words"][u]["s"], b["words"][u]["e"]),
                                       b["words"][p - 1]["e"] if p > 0 else None,
                                       b["words"][u + 1]["s"] if u + 1 < len(b["words"]) else None, float(b["duration"]))
        a = round(a * FPS) / FPS
        e = a + max(1, round((e - a) * FPS)) / FPS
        s["start"], s["end"] = round(a, 4), round(e, 4)


def montar(proyecto, rutas, dst, w=W, h=H, rapido=False):
    ajustar_a_palabras(proyecto)
    segs = [s for s in proyecto["segments"] if s.get("include", True)]
    if not segs:
        raise ValueError("El montaje no tiene ningún tramo activo")
    afinar_cortes(proyecto, rutas, segs)
    ins, fc, sonido = [], [], {}
    # Fondo opcional: {"mode": "color", "color": "#RRGGBB"}. Solo se aplica a los brutos grabados sobre verde.
    cfg = proyecto.get("background") or {}
    fondo = None
    if cfg.get("mode") == "color" and re.fullmatch(r"#[0-9A-Fa-f]{6}", str(cfg.get("color", ""))):
        fondo = "0x" + cfg["color"][1:].upper()
    claves = {b: verde_de_fondo(rutas[b]) for b in {s["bruto"] for s in segs}} if fondo else {}
    if fondo:
        print("  fondo:", cfg["color"], "· brutos con pantalla verde:", [b for b, c in claves.items() if c] or "ninguno")
    for i, s in enumerate(segs):
        a, b = float(s["start"]), float(s["end"])
        ins += ["-ss", f"{a:.4f}", "-t", f"{b - a:.4f}", "-i", rutas[s["bruto"]]]
        if sonido.setdefault(s["bruto"], tiene_audio(rutas[s["bruto"]])):
            audio = f"[{i}:a]aresample=48000,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.04):.2f}:d=0.04,asetpts=PTS-STARTPTS[a{i}]"
        else:  # bruto sin audio: silencio de la misma duración para que el concat no falle
            audio = f"anullsrc=r=48000:cl=stereo:d={b - a:.3f},asetpts=PTS-STARTPTS[a{i}]"
        base = f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1,setpts=PTS-STARTPTS"
        clave = claves.get(s["bruto"])
        if fondo and clave:  # sustituye la pantalla verde por el color elegido (el desvío de verde limpia los bordes)
            fc.append(f"{base},chromakey={clave}:0.12:0.06,despill=type=green:mix=0.5:expand=0,format=yuva420p[k{i}];"
                      f"color=c={fondo}:s={w}x{h}:r={FPS}:d={b - a:.3f}[bg{i}];[bg{i}][k{i}]overlay=shortest=1,format=yuv420p,setpts=PTS-STARTPTS[v{i}];" + audio)
        else:
            fc.append(f"{base}[v{i}];" + audio)
    n = len(segs)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5[a]")
    run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "ultrafast" if rapido else "veryfast", "-crf", "20" if rapido else "16",
         "-c:a", "aac", "-b:a", "192k", dst])
    return segs


def a_linea_de_tiempo(segs, bruto, t):
    """Segundo de un bruto -> segundo del montaje (None si ese momento no entra)."""
    off = 0.0
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        if s["bruto"] == bruto and a - 0.05 <= t <= b + 0.05:
            return off + min(max(t, a), b) - a
        off += b - a
    return None


def plan_de_efectos(proyecto, segs):
    plan = []
    for e in proyecto.get("effects", []):
        a = a_linea_de_tiempo(segs, e["bruto"], float(e["start"]))
        b = a_linea_de_tiempo(segs, e["bruto"], float(e["end"]))
        if a is None or b is None or b - a < 0.3:
            continue
        d = {k: v for k, v in e.items() if k not in ("bruto", "start", "end", "id") and v not in (None, "")}
        d.update(start=round(a, 3), end=round(b, 3))
        if "ticks" in d:  # los ticks vienen en segundos del bruto
            crudos = d["ticks"] if isinstance(d["ticks"], (list, tuple)) else re.split(r"[|,;\s]+", str(d["ticks"]).strip("[] "))
            ts = [a_linea_de_tiempo(segs, e["bruto"], float(x)) for x in crudos if str(x).strip() != ""]
            d["ticks"] = "|".join(f"{x:.2f}" for x in ts if x is not None)
        plan.append(d)
    return sorted(plan, key=lambda d: d["start"])


def palabras_montaje(proyecto, segs):
    out, off = [], 0.0
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        for w in proyecto["brutos"][s["bruto"]]["words"]:
            if w["s"] >= a - 0.02 and w["e"] <= b + 0.08:
                out.append({"w": w["w"], "s": round(w["s"] - a + off, 2), "e": round(min(w["e"], b) - a + off, 2)})
        off += b - a
    return out


# Errores típicos de la transcripción automática. Las correcciones del proyecto mandan sobre estas.
# Las claves pueden ser varias palabras ("cap cut"): se funden en una sola.
FIXES_BASE = {"clon": "Claude", "clod": "Claude", "cloud": "Claude", "claudio": "Claude", "cloe": "Claude", "clot": "Claude",
              "clau": "Claude", "cloude": "Claude", "cap cut": "CapCut", "cinco cut": "CapCut", "cinco up cut": "CapCut",
              "capcat": "CapCut", "chat gpt": "ChatGPT", "chat jpt": "ChatGPT", "many chat": "ManyChat", "nexia": "Nexia"}
MAX_PALABRAS, MAX_CARACTERES = 3, 18  # líneas cortas: no tocan los bordes y no se descompensan con el resalte


def _limpia(t):
    return t.lower().strip("¿?¡!.,")


def corregir(palabras, fixes):
    fixes = {**FIXES_BASE, **{" ".join(_limpia(x) for x in k.split()): v for k, v in fixes.items()}}
    claves = sorted(fixes, key=lambda k: -len(k.split()))
    out, i = [], 0
    while i < len(palabras):
        hecho = False
        for k in claves:
            n = len(k.split())
            trozo = palabras[i:i + n]
            if len(trozo) == n and " ".join(_limpia(w["w"]) for w in trozo) == k:
                nuevo = fixes[k]
                if nuevo:
                    pre = re.match(r"^[¿¡]*", trozo[0]["w"].strip()).group(0)
                    post = re.search(r"[\.,\?!]*$", trozo[-1]["w"].strip()).group(0)
                    out.append({"w": pre + nuevo + post, "s": trozo[0]["s"], "e": trozo[-1]["e"]})
                i += n
                hecho = True
                break
        if not hecho:
            out.append(dict(palabras[i], w=palabras[i]["w"].strip()))
            i += 1
    return out


def subtitulos(proyecto, palabras, plan, dst, total=None):
    cfg = proyecto.get("subtitles", {})
    marca = cfg.get("style") == "marca"
    destacar = {_limpia(x) for x in cfg.get("highlight") or []}
    # Tamaño y posición pedidos en el panel; sin ellos manda el estilo.
    tam = cfg.get("tamano")
    escala, max_car = {"grande": (1.4, 14), "pequeno": (0.82, 22)}.get(tam, (1.0, MAX_CARACTERES))
    letra = "" if escala == 1.0 else "\\fs%d" % round((72 if marca else 70) * escala)
    sitio = {"arriba": "\\an8\\pos(540,430)", "centro": "\\an5\\pos(540,1150)", "abajo": "\\an2\\pos(540,1580)"}.get(
        cfg.get("posicion"), "\\an2\\pos(540,1580)" if marca else "\\an2\\pos(540,1360)")
    ocultar = [(e["start"], e["end"]) for e in plan if e["fx"] in OCULTA_SUBS]
    limpias = corregir(palabras, cfg.get("fixes") or {})
    trozos, cur = [], []
    for w in limpias:
        if cur and len(" ".join(x["w"] for x in cur + [w])) > max_car:
            trozos.append(cur)
            cur = []
        cur.append(w)
        if len(cur) >= MAX_PALABRAS or re.search(r"[\.\?!,]$", w["w"]):
            trozos.append(cur)
            cur = []
    if cur:
        trozos.append(cur)

    def ts(t):
        return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"

    lineas = []
    for k, c in enumerate(trozos):
        a, b = c[0]["s"], c[-1]["e"] + 0.12
        if k + 1 < len(trozos):
            b = min(b, trozos[k + 1][0]["s"])
        if any(a < y and b > x for x, y in ocultar) or b <= a:
            continue
        partes = []
        for x in c:
            t = x["w"].replace("{", "(").replace("}", ")")
            if not marca:
                t = t.upper()
            limpia = _limpia(x["w"])
            partes.append("{\\c" + MAGENTA_ASS + "}" + t + "{\\c&HFFFFFF&}" if limpia in destacar else t)
        animacion = r"\fad(120,80)" if marca else r"\fad(40,0)\t(0,90,\fscx108\fscy108)\t(90,160,\fscx100\fscy100)"
        efecto = "{" + sitio + letra + animacion + "}"
        lineas.append(f"Dialogue: 1,{ts(a)},{ts(b)},{'Marca' if marca else 'Main'},,0,0,0,,{efecto}" + " ".join(partes))
    pasos = [str(x) for x in (cfg.get("pasos") or [])] if marca else []
    if pasos and total:
        # Tira de pasos arriba: cada paso se ilumina cuando se nombra por primera vez.
        ini = []
        for k, p in enumerate(pasos):
            clave = _limpia(p.split()[0])
            t = next((w["s"] for w in limpias if _limpia(w["w"]) == clave and (not ini or w["s"] > ini[-1])), None)
            ini.append(t if t is not None else (ini[-1] + 1 if ini else 0.8))
        fin_tira = max(total - 2.6, 0)
        inicios = [0.8] + ini[1:]
        finales = ini[1:] + [fin_tira]
        for k in range(len(pasos)):
            a0, b0 = inicios[k], finales[k]
            if b0 <= a0:
                continue
            trozos = []
            for j, p in enumerate(pasos):
                est = "{\\c&HFFFFFF&\\1a&H00&\\bord3}" if j == k else "{\\c&HFFFFFF&\\1a&H99&\\bord2}"
                trozos.append(est + f"{j + 1}  " + p.replace("{", "(").replace("}", ")"))
            lineas.append(f"Dialogue: 1,{ts(a0)},{ts(b0)},Rotulo,,0,0,0,,"
                          r"{\an8\pos(540,300)\fs64\fad(250,150)}" + "     ".join(trozos))
    if marca and total:
        # Rótulo de marca: «somosnexia» discreto arriba al abrir y, al cerrar, un velo suave con el nombre centrado.
        lineas.append(f"Dialogue: 1,{ts(0.3)},{ts(2.3)},Rotulo,,0,0,0,,"
                      r"{\an8\pos(540,210)\fad(500,500)}somosnexia")
        t0 = max(total - 2.6, 0)
        lineas.append(f"Dialogue: 0,{ts(t0)},{ts(total)},Velo,,0,0,0,,"
                      r"{\p1\pos(0,0)\1c&H000000&\1a&H66&\fad(600,0)}m 0 0 l 1080 0 1080 1920 0 1920{\p0}")
        lineas.append(f"Dialogue: 1,{ts(t0 + 0.2)},{ts(total)},Cierre,,0,0,0,,"
                      r"{\an5\pos(540,900)\fad(600,0)}somosnexia")
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Montserrat ExtraBold,70,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,2,80,80,560,1
Style: Marca,Poppins SemiBold,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,5,3,2,90,90,560,1
Style: Rotulo,Poppins SemiBold,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,3,0,1,2,2,8,80,80,210,1
Style: Cierre,Poppins SemiBold,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,4,0,1,0,3,5,80,80,0,1
Style: Velo,Poppins SemiBold,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    open(dst, "w", encoding="utf-8").write(cab + "\n".join(lineas) + "\n")


def reloj(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def revisar(proyecto, segs, plan, compo):
    """Lo que conviene mirar antes de dar el reel por bueno, medido por el programa (sin IA)."""
    avisos = []
    for e in proyecto.get("effects", []):
        a = a_linea_de_tiempo(segs, e["bruto"], float(e["start"]))
        b = a_linea_de_tiempo(segs, e["bruto"], float(e["end"]))
        if a is None or b is None or b - a < 0.3:
            avisos.append(f"El efecto «{e['fx']}» no ha salido: su momento está cortado o es demasiado corto.")
    # Imagen congelada y silencios largos, medidos sobre el montaje (los efectos que paran la imagen no cuentan).
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", compo, "-vf", "freezedetect=n=-60dB:d=0.7",
                        "-af", "silencedetect=n=-35dB:d=1.2", "-f", "null", "-"], capture_output=True, text=True)
    quietas = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", r.stderr)]
    for t in quietas[:3]:
        avisos.append(f"La imagen se queda quieta en el {reloj(t)}.")
    total = duracion(compo)
    silencios = [(float(a), float(d)) for a, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", r.stderr)]
    for fin, dur in [x for x in silencios if x[0] < total - 0.3][:3]:
        avisos.append(f"Hay {dur:.1f} s de silencio hacia el {reloj(fin - dur)}: se quita con «Quitar silencios».")
    return avisos


def cambiar_fondo(proyecto, rutas, segs, compo, ancho, alto, borrador, tmp):
    """Pone el fondo elegido detrás de la persona. Con «color», lo grabado en verde ya lo ha resuelto el montaje."""
    cfg = proyecto.get("background") or {}
    modo = cfg.get("mode")
    color = str(cfg.get("color", ""))
    if modo not in ("desenfoque", "color", "flujo") or (modo == "color" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color)):
        return compo
    verdes = {b: bool(verde_de_fondo(rutas[b])) for b in {s["bruto"] for s in segs}} if modo == "color" else {}
    cortes, saltar, t = [], [], 0.0
    for s in segs:
        d = float(s["end"]) - float(s["start"])
        cortes.append(t)
        if verdes.get(s["bruto"]):
            saltar.append((t, t + d))
        t += d
    if len(saltar) == len(segs):
        return compo
    salida = os.path.join(tmp, "fondo.mp4")
    return fondo.aplicar(compo, salida, modo, color or "#133AE2", cortes, saltar, ancho, alto, FPS, borrador)


def papelera(token, file_id):
    """Manda a la papelera de Drive (recuperable) un borrador que ya ha sido sustituido."""
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{file_id}?supportsAllDrives=true",
                                 data=json.dumps({"trashed": True}).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:
        print("aviso: no se pudo retirar el borrador anterior:", e)


def renderizar(job, token, folder, tmp):
    update(job["id"], estado="Renderizando", error="")
    proyecto = drive_json(token, job["proyecto"])
    rutas = {}
    usados = {s["bruto"] for s in proyecto["segments"] if s.get("include", True)}
    for i in sorted(usados):
        rutas[i] = drive_download(token, proyecto["brutos"][i]["id"], os.path.join(tmp, f"b{i}.mp4"))
    # Borrador: mitad de resolución y compresión rápida, para ver los cambios antes de generar el definitivo.
    borrador = proyecto.get("borrador") is True
    ancho, alto = (W // 2, H // 2) if borrador else (W, H)
    compo = os.path.join(tmp, "compo.mp4")
    segs = montar(proyecto, rutas, compo, ancho, alto, borrador)
    plan = plan_de_efectos(proyecto, segs)
    revisable = compo  # la revisión mira el vídeo antes de tocar el fondo (un fondo animado taparía una imagen congelada)
    compo = cambiar_fondo(proyecto, rutas, segs, compo, ancho, alto, borrador, tmp)
    base = compo
    if plan:
        json.dump({"effects": plan}, open(os.path.join(tmp, "plan.json"), "w"), ensure_ascii=False)
        conefectos = os.path.join(tmp, "fx.mp4")
        run([sys.executable, FX, "--plan", os.path.join(tmp, "plan.json"), "--width", str(ancho), compo, conefectos])
        base = conefectos
    final = os.path.join(tmp, "final.mp4")
    vf = []
    if proyecto.get("subtitles", {}).get("enabled", True):
        ass = os.path.join(tmp, "subs.ass")
        subtitulos(proyecto, palabras_montaje(proyecto, segs), plan, ass, duracion(compo))
        vf = ["-vf", f"subtitles={ass}:fontsdir={FUENTES}"]
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", base, "-i", compo, "-map", "0:v", "-map", "1:a", *vf,
         "-c:v", "libx264", "-preset", "ultrafast" if borrador else "medium", "-crf", "26" if borrador else "19", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", "-shortest", final])
    avisos = revisar(proyecto, segs, plan, revisable)
    version = int(job.get("version") or 0) + (0 if borrador else 1)
    limpio = re.sub(r'[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ _-]', '', job['titulo']).strip() or 'Reel'
    nombre = f"{limpio} BORRADOR.mp4" if borrador else f"{limpio} v{version}.mp4"
    video_id = drive_upload_video(token, final, nombre, folder)
    update(job["id"], estado="Para revisar", video=video_id, version=version,
           resultado=f"https://drive.google.com/file/d/{video_id}/view" + ("#borrador" if borrador else ""), error="\n".join(avisos)[:1800])
    # El borrador anterior ya no sirve (los vídeos definitivos nunca se tocan).
    if str(job.get("resultado", "")).endswith("#borrador") and job.get("video"):
        papelera(token, job["video"])
    print(f"  listo: {nombre} ({duracion(final):.1f} s, {len(avisos)} aviso(s))")


def procesar(intentos):
    """Atiende lo que haya en cola. Devuelve True si ha trabajado en algo."""
    info = api("GET", "/api/reels/worker")
    # Si un trabajo vuelve a aparecer una y otra vez (p. ej. no se pudo guardar su estado), se deja de insistir.
    jobs = [j for j in info.get("jobs", []) if intentos.get((j["id"], j["estado"], j.get("proyecto")), 0) < 3]
    if jobs:
        print(f"{len(jobs)} trabajo(s) pendiente(s)")
    for job in jobs:
        clave = (job["id"], job["estado"], job.get("proyecto"))
        intentos[clave] = intentos.get(clave, 0) + 1
        print(f"- {job['estado']}: {job['titulo']}")
        with tempfile.TemporaryDirectory() as tmp:
            try:
                if job["estado"] == "Nueva":
                    preparar(job, info["token"], tmp)
                elif job["estado"] == "En cola":
                    renderizar(job, info["token"], info["outputFolder"], tmp)
            except Exception as e:
                traceback.print_exc()
                try:
                    update(job["id"], estado="Error", error=f"{type(e).__name__}: {e}"[:1800])
                except Exception:
                    pass
        # El token de Drive dura una hora: si quedan trabajos, se pide uno nuevo.
        info["token"] = api("GET", "/api/reels/worker?token=1").get("token", info["token"])
    return bool(jobs)


def main(pausa=20, vida=70 * 60):
    """Tras acabar se queda un rato mirando la cola: mientras se está editando, cada cambio arranca en segundos.

    Si al arrancar no hay nada que hacer, se apaga enseguida (otro motor ya lo atendió): no gasta minutos.
    ESPERA_MINUTOS: minutos sin trabajo antes de apagarse (0 = se apaga al acabar). `vida`: a partir de ahí ya no
    espera más, para no llegar al límite de tiempo del trabajo de GitHub.
    """
    espera = float(os.environ.get("ESPERA_MINUTOS") or 0) * 60
    inicio = libre_desde = time.time()
    intentos, fallos, trabajado = {}, 0, False
    while True:
        try:
            # Primero una pregunta ligera; solo si hay algo se pide el trabajo y el permiso de Drive.
            if api("GET", "/api/reels/worker?peek=1").get("pending", 0) and procesar(intentos):
                libre_desde, trabajado = time.time(), True
            fallos = 0
        except Exception:
            traceback.print_exc()
            fallos += 1
            if fallos >= 5:
                raise
        ahora = time.time()
        if espera <= 0 or (not trabajado and not fallos) or ahora - libre_desde >= espera or ahora - inicio >= vida:
            break
        time.sleep(pausa)
    print("motor apagado: sin trabajo pendiente")


if __name__ == "__main__":
    main()
