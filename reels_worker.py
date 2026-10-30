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
               "cover-star", "red-collage", "led-sign", "messages", "the-bill", "tier-list", "uninstall"}
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


_modelo = None


def transcribir(path):
    global _modelo
    from faster_whisper import WhisperModel
    if _modelo is None:
        _modelo = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segs, _ = _modelo.transcribe(path, language="es", word_timestamps=True, vad_filter=True)
    return [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]


# ------------------------------------------------------------------ paso 1: transcripción y propuesta

def preparar(job, token, tmp):
    update(job["id"], estado="Transcribiendo", error="")
    brutos = []
    for i, fid in enumerate(job["brutos"]):
        src = drive_download(token, fid, os.path.join(tmp, f"b{i}.mp4"))
        brutos.append({"id": fid, "duration": round(duracion(src), 2), "words": transcribir(src)})
        print(f"  bruto {i + 1}/{len(job['brutos'])}: {brutos[-1]['duration']} s, {len(brutos[-1]['words'])} palabras")
    api("POST", "/api/reels/worker", {"action": "propose", "id": job["id"], "brutos": brutos})


# ------------------------------------------------------------------ paso 2: render

def montar(proyecto, rutas, dst):
    segs = [s for s in proyecto["segments"] if s.get("include", True)]
    if not segs:
        raise ValueError("El montaje no tiene ningún tramo activo")
    ins, fc = [], []
    for i, s in enumerate(segs):
        a, b = float(s["start"]), float(s["end"])
        ins += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", rutas[s["bruto"]]]
        fc.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,setpts=PTS-STARTPTS[v{i}];"
                  f"[{i}:a]aresample=48000,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.04):.2f}:d=0.04,asetpts=PTS-STARTPTS[a{i}]")
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
            ts = [a_linea_de_tiempo(segs, e["bruto"], float(x)) for x in str(d["ticks"]).split("|")]
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


def subtitulos(proyecto, palabras, plan, dst):
    cfg = proyecto.get("subtitles", {})
    fixes = {k.lower(): v for k, v in (cfg.get("fixes") or {}).items()}
    destacar = {x.lower().strip("¿?¡!.,") for x in cfg.get("highlight") or []}
    ocultar = [(e["start"], e["end"]) for e in plan if e["fx"] in OCULTA_SUBS]
    limpias = []
    for w in palabras:
        base = w["w"].strip()
        clave = base.lower().strip("¿?¡!.,")
        if clave in fixes:
            nuevo = fixes[clave]
            if not nuevo:
                continue
            pre = re.match(r"^[¿¡]*", base).group(0)
            post = re.search(r"[\.,\?!]*$", base).group(0)
            base = pre + nuevo + post
        limpias.append(dict(w, w=base))
    trozos, cur = [], []
    for w in limpias:
        cur.append(w)
        if len(cur) >= 4 or len(" ".join(x["w"] for x in cur)) >= 20 or re.search(r"[\.\?!,]$", w["w"]):
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
            t = x["w"].upper().replace("{", "(").replace("}", ")")
            limpia = x["w"].lower().strip("¿?¡!.,")
            partes.append("{\\c" + MAGENTA_ASS + "}" + t + "{\\c&HFFFFFF&}" if limpia in destacar else t)
        lineas.append(f"Dialogue: 0,{ts(a)},{ts(b)},Main,,0,0,0,,"
                      r"{\fad(40,0)\t(0,90,\fscx108\fscy108)\t(90,160,\fscx100\fscy100)}" + " ".join(partes))
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Montserrat ExtraBold,70,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,2,80,80,560,1

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
        subtitulos(proyecto, palabras_montaje(proyecto, segs), plan, ass)
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
