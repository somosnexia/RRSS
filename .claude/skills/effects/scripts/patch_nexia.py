"""Adapta fx.py a Somos Nexia. Se puede ejecutar varias veces sin romper nada.

- Firma por defecto @somosnexia en lugar de la de la autora original.
- Firma configurable con `handle` también en headline-wall.
- apple-toggles: `ticks` en segundos del vídeo, como dice la documentación.
- comment-box: interfaz de Instagram en español y respuesta por defecto de Nexia.
"""
import sys

path = sys.argv[1]
s = open(path, encoding='utf-8').read()

reps = [
    ("('@vibha.in.progress  ·  ' + meta) if meta else '@vibha.in.progress'",
     "(e.o.get('handle', '@somosnexia') + '  ·  ' + meta) if meta else e.o.get('handle', '@somosnexia')"),
    ("'@vibha.in.progress  ·  '", "'@somosnexia  ·  '"),
    ("'@vibha.in.progress'", "'@somosnexia'"),
    ("'vibha.in.progress'", "'somosnexia'"),
    ("ts = [float(x) for x in e.o['ticks'].split('|')]",
     "ts = [float(x) - e.start for x in e.o['ticks'].split('|')]"),
    ("reply = e.o.get('reply', 'Sent you the pack'); chip = e.o.get('chip', '22 effects')",
     "reply = e.o.get('reply', 'Te mando la guía'); chip = e.o.get('chip', 'Guía gratis')"),
    ("'Comments', font=", "'Comentarios', font="),
    ("'Start the conversation.'", "'Empieza la conversación.'"),
    ("'Reply', font=", "'Responder', font="),
    ("'Author', font=", "'Autora', font="),
    ("'you', font=", "'tú', font="),
    ("getlength('you ')", "getlength('tú ')"),
    ("'now', font=", "'ahora', font="),
    ("ad.text((sz / 2, sz / 2), 'V',", "ad.text((sz / 2, sz / 2), handle.lstrip('@')[:1].upper(),"),
]
n = 0
for a, b in reps:
    if a in s:
        s = s.replace(a, b); n += 1
open(path, 'w', encoding='utf-8').write(s)
print(f'patch_nexia: {n} cambios aplicados')
