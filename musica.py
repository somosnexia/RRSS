"""Música de fondo: la canción elegida suena bajo la voz y se aparta sola mientras se habla."""
import os
import subprocess

# Sonoridad de la música antes de apartarse (la voz del montaje va a -14 LUFS).
NIVEL = {"suave": -27, "normal": -22, "alta": -17}


def _ffmpeg(args):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-400:])


def _segundos(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _canales(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return int(r.stdout.strip() or 2)


def mezclar(video, cancion, volumen, desde, dur, tmp):
    """Devuelve un .m4a con la voz de `video` y la `cancion` debajo, de `dur` segundos.

    La canción empieza en el segundo `desde` (si se pasa del final, desde el principio) y se repite si es corta.
    """
    largo = _segundos(cancion)
    if largo < 1:
        raise RuntimeError("el archivo de la canción no tiene sonido que se pueda leer")
    inicio = float(desde or 0)
    if inicio >= largo - 1:
        inicio = 0.0
    trozo = os.path.join(tmp, "cancion.wav")
    _ffmpeg(["-ss", f"{inicio:.2f}", "-i", cancion, "-vn", "-ac", "2", "-ar", "48000", "-t", f"{dur:.2f}", trozo])
    salida = os.path.join(tmp, "mezcla.m4a")
    cierre = min(1.5, dur / 4)
    # Una voz grabada en mono se copia tal cual a los dos lados: convertirla sin más la dejaría 3 dB más baja.
    estereo = "pan=stereo|c0=c0|c1=c0" if _canales(video) == 1 else "aformat=channel_layouts=stereo"
    filtro = (
        f"[1:a]loudnorm=I={NIVEL.get(volumen, NIVEL['suave'])}:TP=-2,aresample=48000,"
        f"afade=t=in:d=0.4,afade=t=out:st={max(dur - cierre, 0):.2f}:d={cierre:.2f}[m];"
        f"[0:a]aresample=48000,{estereo},asplit=2[voz][llave];"
        "[m][llave]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[bajo];"
        "[voz][bajo]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[a]"
    )
    _ffmpeg(["-i", video, "-stream_loop", "-1", "-i", trozo, "-filter_complex", filtro, "-map", "[a]",
             "-t", f"{dur:.2f}", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", salida])
    return salida
