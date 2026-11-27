"""Fondo detrás de la persona: desenfocado, color liso, «flujo Nexia» (animado, de la marca) o un vídeo propio.

La persona se recorta con el mismo modelo local que usan los efectos (MediaPipe Selfie Segmenter): no consulta
ningún servicio. El recorte puede fallar un poco en el pelo o con objetos en la mano; con pantalla verde sale más limpio.
"""
import math
import os
import random
import subprocess

import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.abspath(__file__))
MODELO = os.path.join(RAIZ, ".claude", "skills", "effects", "models", "selfie_segmenter.tflite")
AZUL, MAGENTA = (19, 58, 226), (224, 32, 110)  # RGB


# ------------------------------------------------------------------ recorte de la persona

def guiado(gris, m, r=8, eps=2e-3):
    """Ajusta el borde de la máscara a los bordes de la imagen (pelo, hombros)."""
    caja = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))
    mi, mm = caja(gris), caja(m)
    a = (caja(gris * m) - mi * mm) / (caja(gris * gris) - mi * mi + eps)
    return np.clip(caja(a) * gris + caja(mm - a * mi), 0, 1)


class Recorte:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        self.mp = mp
        self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=MODELO), running_mode=vision.RunningMode.VIDEO,
            output_confidence_masks=True, output_category_mask=False))
        self.antes = None

    def __call__(self, rgb, ms):
        """rgb uint8 pequeño -> máscara 0..1 del mismo tamaño."""
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        m = self.seg.segment_for_video(img, ms).confidence_masks[-1].numpy_view().astype(np.float32)
        m = m.reshape(m.shape[0], m.shape[1])
        if m.shape != rgb.shape[:2]:
            m = cv2.resize(m, (rgb.shape[1], rgb.shape[0]))
        m = guiado(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255, m)
        m = np.clip((m - 0.55) * 1.8 + 0.5, 0, 1)  # un pelín hacia dentro: mejor que no asome el fondo viejo
        if self.antes is not None:  # suaviza el temblor del borde entre fotogramas
            m = 0.65 * m + 0.35 * self.antes
        self.antes = m
        return m


# ------------------------------------------------------------------ fondos

class Flujo:
    """Fondo azul noche con pasos conectados por líneas y luces que viajan entre ellos. Se dibuja a media resolución."""

    def __init__(self, w, h, semilla=7):
        self.w, self.h = w // 2, h // 2
        r = random.Random(semilla)
        # Los pasos van sobre todo a los lados y arriba, que es donde no está la persona.
        sitios = [(0.20, 0.09), (0.74, 0.15), (0.15, 0.27), (0.85, 0.33), (0.19, 0.47), (0.83, 0.53), (0.13, 0.67), (0.86, 0.73), (0.24, 0.86), (0.74, 0.92)]
        self.nodos = [(x, y, r.uniform(0, math.tau), r.uniform(0.25, 0.5)) for x, y in sitios]
        self.lineas = [(i, i + 1) for i in range(len(sitios) - 1)] + [(1, 3), (4, 6), (7, 9)]
        t = np.linspace(0, 1, self.h, dtype=np.float32)[:, None, None]
        self.base = np.repeat((1 - t) * np.float32([8, 12, 34]) + t * np.float32([14, 26, 92]), self.w, axis=1)
        yy, xx = np.mgrid[0:self.h // 4, 0:self.w // 4].astype(np.float32)
        self.yy, self.xx = yy / (self.h // 4), xx / (self.w // 4)

    def _pos(self, i, t):
        x, y, fase, vel = self.nodos[i]
        return np.array([(x + 0.018 * math.sin(t * vel + fase)) * self.w, (y + 0.010 * math.cos(t * vel * 1.3 + fase)) * self.h])

    def __call__(self, t):
        img = self.base.copy()
        # Dos resplandores que se mueven despacio.
        luz = np.zeros((*self.xx.shape, 3), np.float32)
        for cx, cy, color, fuerza in ((0.2 + 0.1 * math.sin(t * 0.21), 0.3 + 0.08 * math.cos(t * 0.17), AZUL, 0.55),
                                      (0.85 + 0.08 * math.cos(t * 0.19), 0.75 + 0.07 * math.sin(t * 0.23), MAGENTA, 0.30)):
            d = ((self.xx - cx) * 0.9) ** 2 + ((self.yy - cy) * 1.6) ** 2
            luz += np.exp(-d / 0.09)[..., None] * np.float32(color) * fuerza
        img += cv2.resize(luz, (self.w, self.h))
        img = np.clip(img, 0, 255).astype(np.uint8)
        capa = img.copy()
        pos = [self._pos(i, t) for i in range(len(self.nodos))]
        u = self.w / 540
        curvas = []
        for a, b in self.lineas:
            p, q = pos[a], pos[b]
            medio = (p[1] + q[1]) / 2
            s = np.linspace(0, 1, 40)[:, None]
            pts = (1 - s) ** 3 * p + 3 * (1 - s) ** 2 * s * np.array([p[0], medio]) + 3 * (1 - s) * s ** 2 * np.array([q[0], medio]) + s ** 3 * q
            curvas.append(pts)
            cv2.polylines(capa, [pts.astype(np.int32)], False, (110, 140, 255), max(1, int(2 * u)), cv2.LINE_AA)
        img = cv2.addWeighted(capa, 0.55, img, 0.45, 0)
        brillo = np.zeros_like(img)
        for k, pts in enumerate(curvas):  # una luz recorre cada línea
            i = int(((t * 0.28 + k * 0.17) % 1) * (len(pts) - 1))
            color = MAGENTA if k % 4 == 1 else (170, 200, 255)
            cv2.circle(brillo, tuple(int(v) for v in pts[i]), int(6 * u), color, -1, cv2.LINE_AA)
        img = cv2.add(img, cv2.add(cv2.GaussianBlur(brillo, (0, 0), 7 * u), brillo))
        capa = img.copy()
        for i, p in enumerate(pos):  # cada paso: una tarjeta con su icono y dos rayas de texto
            x, y = int(p[0]), int(p[1])
            an, al = int(112 * u), int(54 * u)
            _tarjeta(capa, x - an // 2, y - al // 2, an, al, int(14 * u), (34, 48, 110))
            _tarjeta(capa, x - an // 2 + int(10 * u), y - int(15 * u), int(30 * u), int(30 * u), int(8 * u), MAGENTA if i % 4 == 2 else AZUL)
            for j, largo in enumerate((52, 34)):
                yy = y - int(8 * u) + j * int(15 * u)
                cv2.line(capa, (x - int(6 * u), yy), (x - int(6 * u) + int(largo * u), yy), (150, 168, 230), max(2, int(5 * u)), cv2.LINE_AA)
        img = cv2.addWeighted(capa, 0.82, img, 0.18, 0)
        return cv2.GaussianBlur(img, (0, 0), 1.2 * u)  # algo de desenfoque para que la persona destaque


def _tarjeta(img, x, y, w, h, r, color):
    cv2.rectangle(img, (x + r, y), (x + w - r, y + h), color, -1)
    cv2.rectangle(img, (x, y + r), (x + w, y + h - r), color, -1)
    for cx, cy in ((x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)):
        cv2.circle(img, (cx, cy), r, color, -1, cv2.LINE_AA)


def desenfocado(frame, m):
    """El mismo fondo, borroso. Se calcula sin contar a la persona para que no deje un halo alrededor."""
    h, w = frame.shape[:2]
    chico = cv2.resize(frame, (w // 8, h // 8), interpolation=cv2.INTER_AREA).astype(np.float32)
    peso = np.clip(1 - cv2.resize(m, (w // 8, h // 8), interpolation=cv2.INTER_AREA), 0, 1) ** 2 + 1e-3
    num = cv2.GaussianBlur(chico * peso[..., None], (0, 0), 3.5)
    den = cv2.GaussianBlur(peso, (0, 0), 3.5)[..., None]
    return cv2.resize((num / den) * 0.92, (w, h), interpolation=cv2.INTER_CUBIC)


class VideoDeFondo:
    """Un vídeo propio detrás: se recorta para llenar la pantalla, se repite si es corto y va sin su sonido."""

    def __init__(self, path, w, h, fps):
        self.w, self.h = w, h
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", path, "-an", "-vf",
                                   f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=rgb24",
                                   "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=10 ** 8)

    def __call__(self, t):
        b = self.p.stdout.read(self.w * self.h * 3)
        if len(b) < self.w * self.h * 3:
            raise RuntimeError("el vídeo de fondo no se puede leer")
        return np.frombuffer(b, np.uint8).reshape(self.h, self.w, 3)

    def cerrar(self):
        self.p.kill()
        self.p.wait()


def encoger(frame, m, escala=0.62):
    """La persona más pequeña, apoyada abajo en el centro, para dejar ver lo que hay detrás."""
    h, w = m.shape
    # Donde tocaba los lados del encuadre original se difumina: encogida, ahí quedaría un corte recto.
    borde = max(2, int(w * 0.05))
    rampa = np.ones(w, np.float32)
    rampa[:borde] = np.linspace(0, 1, borde, dtype=np.float32)
    rampa[-borde:] = rampa[:borde][::-1]
    M = np.float32([[escala, 0, w * (1 - escala) / 2], [0, escala, h * (1 - escala)]])
    chica = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT)
    return chica, cv2.warpAffine(m * rampa[None, :], M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


# ------------------------------------------------------------------ proceso

def aplicar(entrada, salida, modo, color="#133AE2", cortes=(), saltar=(), ancho=1080, alto=1920, fps=30, rapido=False,
            video=None, persona="normal"):
    """entrada -> salida con el fondo cambiado (el sonido se copia tal cual).

    cortes: segundos donde cambia de toma (se olvida el recorte anterior). saltar: tramos (desde, hasta) que ya traen
    el fondo puesto (pantalla verde) y se dejan como están. video: el archivo de fondo (modo «video»).
    persona: «pequena» la coloca más pequeña abajo.
    """
    lee = subprocess.Popen(["ffmpeg", "-v", "error", "-i", entrada, "-vf", f"fps={fps},scale={ancho}:{alto},format=rgb24", "-f", "rawvideo", "-"],
                           stdout=subprocess.PIPE, bufsize=10 ** 8)
    escribe = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ancho}x{alto}", "-r", str(fps), "-i", "-",
                                "-i", entrada, "-map", "0:v", "-map", "1:a:0?", "-c:v", "libx264", "-preset", "ultrafast" if rapido else "veryfast",
                                "-crf", "20" if rapido else "16", "-pix_fmt", "yuv420p", "-c:a", "copy", salida], stdin=subprocess.PIPE)
    recorte = Recorte()
    flujo = Flujo(ancho, alto) if modo == "flujo" else None
    propio = VideoDeFondo(video, ancho, alto, fps) if modo == "video" else None
    liso = np.float32([int(color[i:i + 2], 16) for i in (1, 3, 5)]) if modo == "color" else None
    mw, mh = 540, int(round(540 * alto / ancho / 2)) * 2
    pendientes = sorted(c for c in cortes if c > 0)
    n, tam = 0, ancho * alto * 3
    try:
        while True:
            b = lee.stdout.read(tam)
            if len(b) < tam:
                break
            t = n / fps
            frame = np.frombuffer(b, np.uint8).reshape(alto, ancho, 3)
            while pendientes and t >= pendientes[0] - 0.5 / fps:
                pendientes.pop(0)
                recorte.antes = None
            detras = propio(t) if propio else None  # avanza siempre, para que el fondo no se pare en ningún tramo
            if not any(a - 0.5 / fps <= t < z - 0.5 / fps for a, z in saltar):
                m = recorte(cv2.resize(frame, (mw, mh), interpolation=cv2.INTER_AREA), int(n * 1000 / fps))
                m = cv2.resize(m, (ancho, alto), interpolation=cv2.INTER_LINEAR)
                if modo == "flujo":
                    atras = cv2.resize(flujo(t), (ancho, alto), interpolation=cv2.INTER_LINEAR).astype(np.float32)
                elif modo == "color":
                    atras = liso
                elif modo == "video":
                    atras = detras.astype(np.float32)
                else:
                    atras = desenfocado(frame, m)
                if persona == "pequena" and modo != "desenfoque":
                    frame, m = encoger(frame, m)
                a = m[..., None]
                frame = np.clip(frame.astype(np.float32) * a + atras * (1 - a) + 0.5, 0, 255).astype(np.uint8)
            escribe.stdin.write(frame.tobytes())
            if n % (fps * 5) == 0:
                print(f"  fondo {t:5.1f}s", flush=True)
            n += 1
    finally:
        if propio:
            propio.cerrar()
        lee.kill()
        lee.wait()
        escribe.stdin.close()
        codigo = escribe.wait()
    if codigo != 0 or n == 0:
        raise RuntimeError("No se pudo cambiar el fondo del vídeo")
    return salida
