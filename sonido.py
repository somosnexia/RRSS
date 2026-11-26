"""Lo que se oye: silencios y voz medidos sobre el audio, para colocar palabras y cortes donde de verdad toca.

Whisper da el segundo de cada palabra a ojo: a menudo la estira sobre la pausa de al lado y los cortes quedan raros.
Aquí se mide el volumen cada 10 ms y se ajustan las palabras (al transcribir) y los cortes (al montar).
Solo usa numpy; no consulta ningún servicio.
"""
import subprocess

import numpy as np

PASO = 0.01  # segundos por medida
HZ = 16000


def audio_de(path):
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(HZ), "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def volumen(audio):
    """Volumen (dB) cada 10 ms, suavizado en 30 ms."""
    n = int(HZ * PASO)
    if len(audio) < n:
        return np.full(1, -100.0)
    trozos = audio[: len(audio) // n * n].reshape(-1, n)
    rms = np.sqrt(np.mean(trozos ** 2, axis=1) + 1e-10)
    rms = np.convolve(rms, np.ones(3) / 3, mode="same")
    return 20 * np.log10(rms + 1e-10)


def hay_voz(db):
    """True donde suena algo claramente por encima del ruido de la sala. Se rellenan huecos de menos de 120 ms."""
    suelo, voz = np.percentile(db, 10), np.percentile(db, 90)
    if voz - suelo < 12:  # sin contraste entre voz y ruido: no hay forma fiable de separar silencios
        return None
    v = db > suelo + 0.35 * (voz - suelo)
    i = 0
    while i < len(v):
        if not v[i]:
            j = i
            while j < len(v) and not v[j]:
                j += 1
            if 0 < i and j < len(v) and (j - i) * PASO < 0.12:
                v[i:j] = True
            i = j
        else:
            i += 1
    return v


def _bloques(v, a, b):
    """Tramos con voz dentro de [a, b] (en medidas)."""
    out, i = [], a
    while i < b:
        if v[i]:
            j = i
            while j < b and v[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def ajustar_palabras(palabras, audio):
    """Recorta cada palabra a lo que suena (las pausas dejan de ir pegadas a la palabra) y termina las que se quedan cortas."""
    v = hay_voz(volumen(audio))
    if v is None:
        return palabras
    out = []
    for k, w in enumerate(palabras):
        s, e = float(w["s"]), float(w["e"])
        a, b = max(0, int(s / PASO)), min(len(v), int(round(e / PASO)))
        bloques = _bloques(v, a, b)
        silencio = (b - a) - sum(j - i for i, j in bloques)
        if bloques and silencio * PASO >= 0.25:
            # Se queda con el bloque más largo; si hay empate, el primero.
            i, j = max(bloques, key=lambda t: t[1] - t[0])
            s, e = max(s, i * PASO - 0.03), min(e, j * PASO + 0.05)
        # Si al acabar la palabra todavía suena, se alarga hasta el silencio (como mucho 0,2 s y sin pisar la siguiente).
        tope = min(e + 0.2, float(palabras[k + 1]["s"]) if k + 1 < len(palabras) else len(v) * PASO)
        i = int(round(e / PASO))
        while i < len(v) and v[i] and (i + 1) * PASO <= tope:
            i += 1
        e = max(e, min(i * PASO, tope))
        if out:
            s = max(s, out[-1]["e"])
        e = max(e, s + 0.08)
        out.append({"w": w["w"], "s": round(s, 2), "e": round(e, 2)})
    return out


def punto_mas_callado(db, desde, hasta, actual):
    """El instante de menor volumen en [desde, hasta]. Si no mejora al menos 3 dB al actual, se queda el actual."""
    a, b = max(0, int(desde / PASO)), min(len(db), int(hasta / PASO) + 1)
    if b - a < 2:
        return actual
    i = a + int(np.argmin(db[a:b]))
    ahora = db[min(len(db) - 1, max(0, int(actual / PASO)))]
    return i * PASO if db[i] < ahora - 3 else actual


def afinar_corte(db, inicio, fin, primera, ultima, antes, despues, duracion):
    """Mueve el principio y el final de un tramo al punto más callado cercano, sin comerse la primera ni la última palabra.

    primera/ultima: (s, e) de las palabras de los extremos del tramo; antes/despues: segundo donde acaba o empieza
    la palabra vecina que NO entra (None si no hay).
    """
    bajo = max(0.0, inicio - 0.12, (antes - 0.08) if antes is not None else 0.0)
    alto = min(inicio + 0.08, primera[0] + 0.01)
    a = punto_mas_callado(db, bajo, alto, inicio) if alto > bajo else inicio
    bajo = max(fin - 0.06, ultima[1] - 0.06)
    alto = min(duracion, fin + 0.25, (despues + 0.08) if despues is not None else duracion)
    b = punto_mas_callado(db, bajo, alto, fin) if alto > bajo else fin
    return a, b
