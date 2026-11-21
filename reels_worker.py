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


def transcribir(path):
    global _modelo
    from faster_whisper import WhisperModel
    if _modelo is None:
        _modelo = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    if not tiene_audio(path):
        return []  # vídeo sin sonido (p. ej. grabación de pantalla): no hay nada que transcribir
    # El audio se saca con ffmpeg (16 kHz mono) y no con PyAV: faster-whisper choca con algunas versiones de av.
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, _ = _modelo.transcribe(audio, language="es", word_timestamps=True, vad_filter=True)
    return [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]


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
        brutos.append({"id": fid, "duration": dur, "words": transcribir(src)})
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
        for w in b["words"]:
            if w["s"] < a < w["e"] - 0.03:
                a = w["s"] - 0.08
            if w["s"] < e - 0.03 and w["e"] > e:
                e = w["e"] + 0.15
        s["start"], s["end"] = round(max(0.0, a), 3), round(min(float(b["duration"]), e), 3)


def montar(proyecto, rutas, dst):
    ajustar_a_palabras(proyecto)
    segs = [s for s in proyecto["segments"] if s.get("include", True)]
    if not segs:
        raise ValueError("El montaje no tiene ningún tramo activo")
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
        ins += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", rutas[s["bruto"]]]
        if sonido.setdefault(s["bruto"], tiene_audio(rutas[s["bruto"]])):
            audio = f"[{i}:a]aresample=48000,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.04):.2f}:d=0.04,asetpts=PTS-STARTPTS[a{i}]"
        else:  # bruto sin audio: silencio de la misma duración para que el concat no falle
            audio = f"anullsrc=r=48000:cl=stereo:d={b - a:.3f},asetpts=PTS-STARTPTS[a{i}]"
        base = f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,setpts=PTS-STARTPTS"
        clave = claves.get(s["bruto"])
        if fondo and clave:  # sustituye la pantalla verde por el color elegido (el desvío de verde limpia los bordes)
            fc.append(f"{base},chromakey={clave}:0.12:0.06,despill=type=green:mix=0.5:expand=0,format=yuva420p[k{i}];"
                      f"color=c={fondo}:s={W}x{H}:r={FPS}:d={b - a:.3f}[bg{i}];[bg{i}][k{i}]overlay=shortest=1,format=yuv420p,setpts=PTS-STARTPTS[v{i}];" + audio)
        else:
            fc.append(f"{base}[v{i}];" + audio)
    n = len(segs)
    fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5[a]")
    run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", dst])
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
    ocultar = [(e["start"], e["end"]) for e in plan if e["fx"] in OCULTA_SUBS]
    limpias = corregir(palabras, cfg.get("fixes") or {})
    trozos, cur = [], []
    for w in limpias:
        if cur and len(" ".join(x["w"] for x in cur + [w])) > MAX_CARACTERES:
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
        efecto = (r"{\an2\pos(540,1580)\fad(120,80)}" if marca
                  else r"{\an2\pos(540,1360)\fad(40,0)\t(0,90,\fscx108\fscy108)\t(90,160,\fscx100\fscy100)}")
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
Style: Marca,Poppins SemiBold,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,5,3,2,90,90,560,1
Style: Rotulo,Poppins SemiBold,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,3,0,1,2,2,8,80,80,210,1
Style: Cierre,Poppins SemiBold,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,4,0,1,0,3,5,80,80,0,1
Style: Velo,Poppins SemiBold,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    open(dst, "w", encoding="utf-8").write(cab + "\n".join(lineas) + "\n")


def renderizar(job, token, folder, tmp):
    update(job["id"], estado="Renderizando", error="")
    proyecto = drive_json(token, job["proyecto"])
    rutas = {}
    usados = {s["bruto"] for s in proyecto["segments"] if s.get("include", True)}
    for i in sorted(usados):
        rutas[i] = drive_download(token, proyecto["brutos"][i]["id"], os.path.join(tmp, f"b{i}.mp4"))
    compo = os.path.join(tmp, "compo.mp4")
    segs = montar(proyecto, rutas, compo)
    plan = plan_de_efectos(proyecto, segs)
    base = compo
    if plan:
        json.dump({"effects": plan}, open(os.path.join(tmp, "plan.json"), "w"), ensure_ascii=False)
        conefectos = os.path.join(tmp, "fx.mp4")
        run([sys.executable, FX, "--plan", os.path.join(tmp, "plan.json"), compo, conefectos])
        base = conefectos
    final = os.path.join(tmp, "final.mp4")
    vf = []
    if proyecto.get("subtitles", {}).get("enabled", True):
        ass = os.path.join(tmp, "subs.ass")
        subtitulos(proyecto, palabras_montaje(proyecto, segs), plan, ass, duracion(compo))
        vf = ["-vf", f"subtitles={ass}:fontsdir={FUENTES}"]
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", base, "-i", compo, "-map", "0:v", "-map", "1:a", *vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", "-shortest", final])
    version = int(job.get("version") or 0) + 1
    nombre = f"{re.sub(r'[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ _-]', '', job['titulo']).strip() or 'Reel'} v{version}.mp4"
    video_id = drive_upload_video(token, final, nombre, folder)
    update(job["id"], estado="Para revisar", video=video_id, version=version,
           resultado=f"https://drive.google.com/file/d/{video_id}/view", error="")
    print(f"  listo: {nombre} ({duracion(final):.1f} s)")


def main():
    info = api("GET", "/api/reels/worker")
    jobs = info.get("jobs", [])
    print(f"{len(jobs)} trabajo(s) pendiente(s)")
    for job in jobs:
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


if __name__ == "__main__":
    main()
