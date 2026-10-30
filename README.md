# RRSS · Somos Nexia

Nuestro editor de reels con Claude, más piezas de contenido para redes.

## Qué hay aquí

| Ruta | Qué es |
|---|---|
| `subtitular.py` | Subtitulador de reels: une los brutos, los pasa a vertical 1080x1920, sincroniza el guion con la voz y quema subtítulos con palabras resaltadas |
| `guiones/` | Guiones de texto para el subtitulador |
| `fonts/` | Tipografía de los subtítulos (Montserrat ExtraBold) |
| `.claude/skills/effects/` | Skill `/effects`: 45 efectos de vídeo que siguen la cara |
| `landing-guia-seo/` | Landing de la guía SEO (versión HTML y bloque para WordPress con formulario de Brevo) |

Los vídeos (`*.mp4`, `*.mov`) y la carpeta `exports/` no se versionan. Los brutos viven en Drive: `VIDEOS BRUTOS / 🤖 Cosas de IA`.

## Subtitulador

```
python3 subtitular.py --guion guiones/mi-guion.txt --out salida/reel.mp4 brutos/1.mp4 brutos/2.mp4
```

- Sincroniza con Whisper (faster-whisper) si está instalado; si no, reparte el texto entre los tramos hablados.
- Las palabras marcadas con `*asteriscos*` en el guion salen en amarillo.
- Deja el `.ass` al lado del vídeo por si hay que retocar tiempos a mano.

## Efectos de vídeo (`/effects`)

La skill de 45 efectos viene de
[Vibha-Ramprakash/claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects)
(licencia MIT, commit `99c9a33`). Claude Code la carga automáticamente al abrir este repo.

Uso: sube un vídeo vertical y escribe, por ejemplo:

```
/effects orbit from 3 to 6 seconds
```

La primera vez Claude ejecuta `scripts/setup.sh`, que crea un entorno Python (`.venv`, ignorado por git). Necesita `ffmpeg` y Python 3.10+. En Linux (sesiones en la nube) también hace falta `libegl1` (`apt-get install -y libegl1`).

Para que un efecto entre en una palabra concreta: `scripts/words.py <vídeo>` saca el segundo exacto de cada palabra.

Los efectos solo añaden imagen. Los subtítulos se ponen con `subtitular.py`.
