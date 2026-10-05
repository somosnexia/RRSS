#!/usr/bin/env python3
"""Subtitula reels a partir de los brutos y un guion.

Uso:
    python3 subtitular.py --guion guiones/mi-guion.txt --out salida/reel.mp4 brutos/1.mp4 brutos/2.mp4 ...

- Une los brutos en orden y los deja en vertical 1080x1920 (recorta, no deforma).
- Sincroniza el guion con la voz:
    * con Whisper (faster-whisper) si está instalado y puede cargar el modelo;
    * si no, detectando las pausas de la voz y repartiendo el texto entre los tramos hablados.
- Quema subtítulos tamaño mediano, blancos con borde negro, y las *palabras marcadas* en amarillo.
- Deja también el .ass al lado del vídeo por si hay que retocar tiempos a mano.
"""
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

RAIZ = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(RAIZ, "fonts")

ANCHO, ALTO, FPS = 1080, 1920, 30

# Estilo: tamaño mediano, blanco con borde negro, resaltado amarillo.
FUENTE = "Montserrat ExtraBold"
TAM_FUENTE = 72
MARGEN_INFERIOR = 560  # por encima de la zona de caption/botones de Instagram
AMARILLO = "&H0000E6FF&"  # ASS va en BGR: #FFE600
BLANCO = "&H00FFFFFF&"

MAX_PALABRAS = 4
MAX_CARACTERES = 24


def ejecutar(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def duracion(ruta):
    out = ejecutar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", ruta]).stdout
    return float(out.strip())


def tiene_audio(ruta):
    out = ejecutar(["ffprobe", "-v", "error", "-select_streams", "a",
                    "-show_entries", "stream=index", "-of", "csv=p=0", ruta]).stdout
    return bool(out.strip())


# ---------------------------------------------------------------- guion

def leer_guion(ruta):
    """Devuelve [(palabra_visible, resaltada, fin_de_frase)]."""
    palabras = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            linea = quitar_emojis(linea)
            resaltando = False
            tokens = linea.split()
            for i, tok in enumerate(tokens):
                abre = tok.startswith("*") or tok.lstrip("¿¡(\"“").startswith("*")
                if abre:
                    resaltando = True
                marcada = resaltando
                if tok.rstrip(".,:;!?…)\"”").endswith("*"):
                    resaltando = False
                limpia = tok.replace("*", "")
                if not limpia:
                    continue
                fin = i == len(tokens) - 1 or bool(re.search(r"[.:;!?…]$", limpia))
                palabras.append([limpia, marcada, fin])
    return palabras


def quitar_emojis(texto):
    return "".join(c for c in texto
                   if unicodedata.category(c) != "So" and not 0xFE00 <= ord(c) <= 0xFE0F
                   and ord(c) != 0x200D).strip()


def normalizar(p):
    p = unicodedata.normalize("NFD", p.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", p)


# ---------------------------------------------------------------- vídeo

def preparar_video(brutos, destino):
    """Une los brutos en un único vídeo vertical 1080x1920 a 30 fps."""
    filtros, entradas = [], []
    for i, b in enumerate(brutos):
        entradas += ["-i", b]
        filtros.append(
            f"[{i}:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
            f"crop={ANCHO}:{ALTO},setsar=1,fps={FPS},format=yuv420p[v{i}]")
        if tiene_audio(b):
            filtros.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        else:
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{duracion(b)}[a{i}]")
    pares = "".join(f"[v{i}][a{i}]" for i in range(len(brutos)))
    filtros.append(f"{pares}concat=n={len(brutos)}:v=1:a=1[v][a]")
    ejecutar(["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(filtros),
              "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
              "-crf", "18", "-c:a", "aac", "-b:a", "192k", destino])


def extraer_audio(video, wav):
    ejecutar(["ffmpeg", "-y", "-i", video, "-ac", "1", "-ar", "16000", wav])


# ---------------------------------------------------------------- tiempos

def tiempos_whisper(wav, palabras, modelo):
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
    except Exception as e:  # sin paquete o sin acceso al modelo
        print(f"[aviso] Whisper no disponible ({e.__class__.__name__}); uso detección de pausas.")
        return None
    segs, _ = m.transcribe(wav, language="es", word_timestamps=True, vad_filter=True)
    oidas = [(normalizar(w.word), w.start, w.end) for s in segs for w in (s.words or [])]
    oidas = [o for o in oidas if o[0]]
    if not oidas:
        return None
    guion = [normalizar(p[0]) for p in palabras]
    sm = difflib.SequenceMatcher(a=guion, b=[o[0] for o in oidas], autojunk=False)
    t = [None] * len(palabras)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            t[a + k] = (oidas[b + k][1], oidas[b + k][2])
    return interpolar(t, oidas[0][1], oidas[-1][2])


def interpolar(t, inicio, fin):
    """Rellena las palabras del guion que Whisper no reconoció."""
    n = len(t)
    i = 0
    while i < n:
        if t[i] is not None:
            i += 1
            continue
        j = i
        while j < n and t[j] is None:
            j += 1
        a = t[i - 1][1] if i > 0 else inicio
        b = t[j][0] if j < n else fin
        paso = max(b - a, 0.01) / (j - i)
        for k in range(i, j):
            t[k] = (a + paso * (k - i), a + paso * (k - i + 1))
        i = j
    return t


def tramos_de_voz(wav, total):
    err = subprocess.run(["ffmpeg", "-i", wav, "-af", "silencedetect=noise=-32dB:d=0.35",
                          "-f", "null", "-"], text=True, capture_output=True).stderr
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    silencios = list(zip(inicios, finales + [total] * (len(inicios) - len(finales))))
    tramos, cursor = [], 0.0
    for s, e in silencios:
        if s - cursor > 0.15:
            tramos.append((cursor, s))
        cursor = e
    if total - cursor > 0.15:
        tramos.append((cursor, total))
    return tramos or [(0.0, total)]


def tiempos_por_pausas(wav, palabras, total):
    """Reparte las palabras (por nº de letras) sobre el tiempo en que hay voz."""
    tramos = tramos_de_voz(wav, total)
    hablado = sum(e - s for s, e in tramos)
    pesos = [len(p[0]) + 2 + (4 if p[2] else 0) for p in palabras]
    escala = hablado / sum(pesos)

    def a_reloj(x):  # segundos de voz acumulada -> segundos del vídeo
        for s, e in tramos:
            if x <= e - s:
                return s + x
            x -= e - s
        return tramos[-1][1]

    t, acum = [], 0.0
    for w in pesos:
        t.append((a_reloj(acum), a_reloj(acum + w * escala)))
        acum += w * escala
    return t


# ---------------------------------------------------------------- subtítulos

def agrupar(palabras, tiempos):
    bloques, actual = [], []
    for p, t in zip(palabras, tiempos):
        actual.append((p, t))
        texto = " ".join(x[0][0] for x in actual)
        if p[2] or len(actual) >= MAX_PALABRAS or len(texto) >= MAX_CARACTERES:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def ts(s):
    cs = int(round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def escribir_ass(bloques, ruta, total):
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ANCHO}
PlayResY: {ALTO}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,{FUENTE},{TAM_FUENTE},{BLANCO},{BLANCO},&H00000000&,&H64000000&,0,0,0,0,100,100,0,0,1,5,2,2,90,90,{MARGEN_INFERIOR},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for i, b in enumerate(bloques):
        ini = b[0][1][0]
        fin = bloques[i + 1][0][1][0] if i + 1 < len(bloques) else min(b[-1][1][1] + 0.6, total)
        if b[-1][0][2]:  # fin de frase: no alargar sobre la pausa más de 0.6 s
            fin = min(fin, b[-1][1][1] + 0.6)
        partes = []
        for (texto, marcada, _), _t in b:
            texto = texto.replace("{", "(").replace("}", ")")
            partes.append(f"{{\\c{AMARILLO}}}{texto}{{\\c{BLANCO}}}" if marcada else texto)
        pop = "{\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}"
        lineas.append(f"Dialogue: 0,{ts(ini)},{ts(max(fin, ini + 0.25))},Reel,,0,0,0,,{pop}{' '.join(partes)}")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(lineas) + "\n")


def quemar(video, ass, salida):
    esc = lambda p: p.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    ejecutar(["ffmpeg", "-y", "-i", video,
              "-vf", f"ass='{esc(ass)}':fontsdir='{esc(FUENTES)}'",
              "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
              "-c:a", "copy", "-movflags", "+faststart", salida])


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brutos", nargs="+", help="vídeos en el orden en que van en el reel")
    ap.add_argument("--guion", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modelo", default="small", help="modelo de Whisper (tiny/base/small/medium)")
    ap.add_argument("--sin-whisper", action="store_true", help="sincronizar solo por pausas")
    ap.add_argument("--ass", help="usar este .ass ya retocado en vez de generarlo")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("Falta ffmpeg.")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    ass = a.ass or os.path.splitext(a.out)[0] + ".ass"

    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base.mp4")
        print(f"1/4 Uniendo {len(a.brutos)} bruto(s) en vertical 1080x1920…")
        preparar_video(a.brutos, base)
        total = duracion(base)

        if not a.ass:
            wav = os.path.join(tmp, "voz.wav")
            extraer_audio(base, wav)
            palabras = leer_guion(a.guion)
            print("2/4 Sincronizando guion con la voz…")
            t = None if a.sin_whisper else tiempos_whisper(wav, palabras, a.modelo)
            if t is None:
                t = tiempos_por_pausas(wav, palabras, total)
            print("3/4 Generando subtítulos…")
            escribir_ass(agrupar(palabras, t), ass, total)
        print("4/4 Quemando subtítulos…")
        quemar(base, ass, a.out)
    print(f"Listo: {a.out}  (subtítulos editables en {ass})")


if __name__ == "__main__":
    main()
