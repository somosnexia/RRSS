# RRSS
Nuestro editor de reels con claude

## Efectos de vídeo (`/effects`)

El repo incluye la skill de 45 efectos de vídeo de
[Vibha-Ramprakash/claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects)
(licencia MIT, commit `99c9a33`) en `.claude/skills/effects/`. Claude Code la carga
automáticamente al abrir este repo.

Uso: sube un vídeo vertical a la conversación y escribe, por ejemplo:

```
/effects orbit from 3 to 6 seconds
```

La primera vez Claude ejecuta `scripts/setup.sh`, que crea un entorno Python (`.venv`,
ignorado por git). Necesita `ffmpeg` y Python 3.10+. En Linux (sesiones en la nube)
también hace falta `libegl1` (`apt-get install -y libegl1`).

Para actualizar la skill, vuelve a copiar el repo original sobre `.claude/skills/effects/`.
