from lib import *
import re

S, V = 's45', 's916'

# ---------- PINEADO 01 · reel cover 9:16 ----------
page('P01', V, 'navy',
     img('1.jpg', 'object-position:50% 0') + '<div class="tint"></div><div class="fadeb"></div>' +
     notif(560, 560, 'WHATSAPP · 23:12', 'Marta', '¿Quedan plazas para enero?', rot=3, w=470) +
     notif(600, 690, 'WHATSAPP · 23:14', 'Lucía', '¿precio? 🙏', rot=-2, w=440) +
     notif(540, 815, 'INSTAGRAM · 23:20', 'ana.mentora', 'Te escribí ayer, ¿me pasas info?', rot=2, w=490) +
     notif(590, 950, 'WHATSAPP · 23:41', 'Carmen', '¿Sigues ahí?', rot=-3, w=430) +
     '<div class="abs h" style="left:64px;right:64px;top:1290px;font-size:96px">Tu negocio crece.<em style="font-size:92px">¿Por qué tu libertad no?</em></div>' +
     '<div class="abs k" style="left:64px;top:1610px;font-size:22px;color:#9cc0ff">Síguenos si quieres crecer sin responderlo todo tú</div>' +
     brand() + handle() + grain(V))

# ---------- PINEADO 02 · carrusel 8 ----------
N = 8
page('P02-01', S, 'cream',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:86px;color:#00367d">Así funciona Submarino NexIA.<em style="font-size:80px">Y no, no es otro chatbot.</em></div>' +
     submarine(40, 640, 1000) + brand() + pg(1, N) + '<div class="handle" style="color:#00367d">desliza →</div>' + grain(S, True))

rows = [('Marta', '¿Quedan plazas para enero?', '23:12', 2), ('Lucía · mentora fitness', '¿precio? 🙏', '23:14', 1), ('Carmen', '¿Sigues ahí?', 'ayer', 3),
        ('+34 6•• ••• •••', 'Hola, vi tu anuncio y…', 'ayer', 1), ('Patricia', 'Me lo pienso y te digo', 'lun', 0), ('Elena', '¿Tienes hueco esta semana?', 'dom', 2)]
lst = ''.join(f'<div style="display:flex;align-items:center;gap:18px;padding:18px 26px;border-bottom:1px solid #e6e6e6"><div style="width:64px;height:64px;border-radius:50%;background:#c9d3de"></div>'
              f'<div style="flex:1"><div style="font-weight:600;font-size:25px;color:#111">{n}</div><div style="font-size:22px;color:#667781">{m}</div></div>'
              f'<div style="text-align:right"><div style="font-size:18px;color:{"#25d366" if u else "#667781"}">{t}</div>'
              + (f'<div style="display:inline-block;margin-top:6px;background:#25d366;color:#fff;border-radius:999px;font-size:17px;font-weight:600;padding:2px 10px">{u}</div>' if u else '') +
              '</div></div>' for n, m, t, u in rows)
page('P02-02', S, 'navy',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:74px">El problema no son los leads.<em style="font-size:70px">Es todo lo que pasa después.</em></div>' +
     f'<div class="abs" style="left:110px;top:560px;width:860px;background:#fff;border-radius:30px;overflow:hidden;box-shadow:0 30px 70px rgba(0,0,0,.5);transform:rotate(-2deg)">{lst}</div>' +
     brand() + pg(2, N) + grain(S))

def step(n, title, em, txt, extra, cls='cream', p=None):
    col = '#00367d' if cls == 'cream' else '#fff'
    return page(f'P02-{p:02d}', S, cls,
                f'<div class="abs num" style="left:64px;top:150px;color:{"#2e4be2" if cls=="cream" else "#9cc0ff"}">PASO {n} DE 4</div>'
                f'<div class="abs h" style="left:64px;width:560px;top:200px;font-size:80px;color:{col}">{title}<em style="font-size:62px">{em}</em></div>'
                f'<div class="abs body" style="left:64px;width:470px;top:560px;color:{col}">{txt}</div>' + extra + brand() + pg(p, N) + grain(S, cls == 'cream'))

step('01', 'Atiende.', 'A cualquier hora.', 'Responde con <b>tu</b> información: tu oferta, tus plazos, tu forma de hablar. Aunque sean las 23:47.',
     phone(560, 300, 'Lucía', 'en línea', [('day', 'HOY'), ('in', 'Hola! ¿info del programa? 🙏', '23:47'),
                                            ('out', '¡Hola, Lucía! Claro 😊 Es un programa de 12 semanas para mentoras que ya venden. ¿Me cuentas en qué punto está tu negocio?', '23:47'),
                                            ('in', 'Vendo sesiones sueltas pero quiero escalar', '23:49')], w=480) +
     '<div class="demo" style="left:64px;top:1160px">Ejemplo · demo</div>', p=3)

card = ('<div class="abs card" style="left:560px;top:330px;width:460px;transform:rotate(2deg);font-size:24px">'
        '<div class="k" style="font-size:18px;color:#2e4be2;margin-bottom:16px">Ficha del contacto</div>'
        + ''.join(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px dashed #cfd6e4"><span style="color:#4a4a4a">{a}</span><b style="text-align:right">{b}</b></div>'
                  for a, b in [('Negocio', 'Mentoría online'), ('¿Ya vende?', 'Sí ✓'), ('Consultas', 'Cada semana ✓'), ('Necesita', 'Atención y seguimiento'), ('¿Encaja?', 'Sí → agenda')]) +
        '</div>')
step('02', 'Cualifica.', 'Pregunta lo que tú preguntarías.', 'Antes de que llegue a tu agenda, ya sabes quién es, qué necesita y si encaja contigo.', card +
     '<div class="demo" style="left:64px;top:1160px">Ejemplo · demo</div>', cls='navy', p=4)

days = ['L', 'M', 'X', 'J', 'V']
cal = '<div class="abs card" style="left:540px;top:330px;width:480px;padding:26px;transform:rotate(-2deg)"><div class="k" style="font-size:18px;color:#2e4be2">Tu agenda</div><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:16px">'
for d in days: cal += f'<div style="text-align:center;font-weight:600;color:#4a4a4a;font-size:20px">{d}</div>'
for r in range(5):
    for c in range(5):
        on = (r, c) == (1, 3)
        cal += f'<div style="height:64px;border-radius:10px;background:{"#2e4be2" if on else "#eef1f7"};color:#fff;font-size:15px;font-weight:600;padding:6px">{"10:00<br>Lucía" if on else ""}</div>'
cal += '</div><div style="margin-top:18px;font-size:21px;color:#111"><b>Jueves 10:00</b> · Llamada de valoración<br><span style="color:#667781">Reservada por el agente · confirmación enviada</span></div></div>'
step('03', 'Agenda.', 'Solo con quien encaja.', 'Reserva la cita en tu calendario y manda el recordatorio. Tú solo apareces en la llamada.', cal +
     '<div class="demo" style="left:64px;top:1160px">Ejemplo · demo</div>', p=5)

page('P02-06', S, 'navy',
     img('3.jpg', 'object-position:50% 20%') + '<div class="tint"></div><div class="fadeb"></div>' +
     notif(470, 300, 'SUBMARINO NEXIA · AHORA', 'Conversación derivada a Pilar', '«Quiere algo a medida. Mejor que lo hable contigo.»', rot=-2, w=540) +
     '<div class="abs num" style="left:64px;top:860px;color:#9cc0ff">PASO 04 DE 4</div>'
     '<div class="abs h" style="left:64px;right:64px;top:910px;font-size:84px">Deriva.<em style="font-size:70px">Si no sabe, no inventa.</em></div>'
     '<div class="abs body" style="left:64px;right:200px;top:1130px;font-size:30px">Cuando hace falta criterio humano, te pasa el testigo con todo el contexto.</div>' +
     brand() + pg(6, N) + grain(S))

lv = [('01', 'Sónar', 'Detecta y atiende oportunidades', 'WhatsApp y redes'), ('02', 'Reactor', 'Activa la atención en varios canales', 'Web, voz y agenda'),
      ('03', 'Puente de Mando', 'Coordina cualificación y seguimiento', 'Setter y seguimiento'), ('04', 'Astillero', 'Una solución construida a medida', 'Integraciones y CRM')]
cards = ''.join(f'<div class="card" style="padding:30px;border:3px solid #00367d;box-shadow:8px 8px 0 #2e4be2;border-radius:22px"><div class="k" style="font-size:18px;color:#2e4be2">Nivel {a}</div>'
                f'<div style="font-weight:800;font-size:44px;color:#00367d;line-height:1.05;margin:10px 0 12px">{b}</div><div style="font-size:24px;color:#333;line-height:1.3">{c}</div>'
                f'<div class="chip" style="margin-top:16px;font-size:19px">{d}</div></div>' for a, b, c, d in lv)
page('P02-07', S, 'cream',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:70px;color:#00367d">Cuatro niveles.<em style="font-size:62px">No son fases: son soluciones distintas.</em></div>'
     f'<div class="abs" style="left:64px;right:64px;top:440px;display:grid;grid-template-columns:1fr 1fr;gap:30px">{cards}</div>'
     '<div class="abs body" style="left:64px;right:64px;top:1170px;font-size:28px;color:#00367d">Elegimos contigo el que necesita tu negocio. Ni más, ni menos.</div>' +
     brand() + pg(7, N) + grain(S, True))

page('P02-08', S, 'blue',
     '<div class="abs k" style="left:64px;top:170px;font-size:26px;color:#cfe0ff">¿Y en tu negocio cómo sería?</div>'
     '<div class="abs h" style="left:56px;top:250px;font-size:120px">Escribe</div>'
     '<div class="abs h" style="left:50px;top:360px;font-size:250px;letter-spacing:-8px">NEXIA</div>'
     '<div class="abs em" style="left:64px;top:640px;font-size:96px;color:#fff">por DM.</div>'
     '<div class="abs body" style="left:64px;right:120px;top:800px;font-size:34px">Te contamos cómo lo adaptaríamos a tu negocio. Sin compromiso y sin tecnicismos.</div>'
     '<div class="abs" style="left:64px;right:64px;top:1030px;background:#fff;border-radius:999px;padding:22px 30px;display:flex;justify-content:space-between;align-items:center;color:#111;font-size:30px;box-shadow:0 18px 40px rgba(0,0,0,.25)">'
     '<span><span style="color:#999">Mensaje… </span><b>NEXIA</b><span style="display:inline-block;width:3px;height:34px;background:#2e4be2;vertical-align:middle;margin-left:4px"></span></span><span style="color:#2e4be2;font-weight:800">Enviar</span></div>' +
     brand() + pg(8, N) + handle() + grain(S))

# ---------- PINEADO 03 · Radar · carrusel 7 ----------
N = 7
p1b = open(os.path.join(D, '../work/p1b.html')).read()
hudsvg = re.search(r'<svg class="hud".*?</svg>', p1b, re.S).group(0).replace('class="hud"', 'class="fill" style="mix-blend-mode:screen"')
script = re.search(r'<script>.*?</script>', p1b, re.S).group(0)
page('P03-01', S, 'navy',
     img('pilar_crop.jpg', 'filter:saturate(.92) contrast(1.04) brightness(1.03)') + '<div class="tint"></div>' + hudsvg +
     '<div class="fill" style="background:linear-gradient(180deg,rgba(10,16,32,0) 55%,rgba(10,16,32,.9) 75%,rgba(10,16,32,.97))"></div>'
     '<div class="abs h" style="left:64px;right:64px;top:930px;font-size:62px">Antes de contratar una IA,<em style="font-size:60px">descubre qué necesitas automatizar de verdad.</em></div>'
     '<div class="abs lbl" style="left:64px;top:1240px;color:#9cc0ff">Radar NexIA · gratis</div>' + brand() + pg(1, N) + script + grain(S))

def lst(items, color='#fff', mark='✕', mc='#ff4d8d', fs=36, gap=34):
    return ''.join(f'<div style="display:flex;gap:26px;align-items:flex-start;margin-bottom:{gap}px;font-size:{fs}px;line-height:1.3;color:{color}">'
                   f'<span style="flex:none;width:54px;height:54px;border:3px solid {mc};color:{mc};border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:32px">{mark}</span><span>{t}</span></div>' for t in items)

page('P03-02', S, 'deep',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:96px">¿Te suena?</div>'
     '<div class="abs" style="left:64px;right:64px;top:330px">' + lst(['Respondes lo mismo <b>una y otra vez</b>.', 'Miras WhatsApp fuera de horario «solo un momento».',
                                                                    'Haces el seguimiento a mano (cuando te acuerdas).', 'Tienes llamadas con gente que no encaja.', 'Sientes que desconectar es dejar de vender.'], mark='✓', fs=50, gap=58) + '</div>' +
     brand() + pg(2, N) + grain(S))

page('P03-03', S, 'cream',
     '<div class="abs k" style="left:64px;top:150px;font-size:24px;color:#2e4be2">Radar NexIA</div>'
     '<div class="abs h" style="left:64px;right:64px;top:200px;font-size:96px;color:#00367d">Es para ti si…</div>'
     '<div class="abs" style="left:64px;right:64px;top:400px">' + lst(['Eres mentora, coach o asesora de negocios.', 'Ya tienes una oferta validada y recibes consultas.',
                                                                    'Repites respuestas o tareas comerciales cada semana.', 'Quieres usar IA partiendo de un <b>problema real</b>.'], color='#0b1a3a', mark='✓', mc='#2e4be2', fs=54, gap=64) + '</div>' +
     brand() + pg(3, N) + grain(S, True))

page('P03-04', S, 'deep',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:72px">Qué escanea<em style="font-size:66px">Radar NexIA.</em></div>' +
     sonar(540, 790, 400, [(-150, .78, 'CAPTACIÓN', 0), (-60, .62, 'ATENCIÓN', 1), (10, .8, 'CUALIFICACIÓN', 0), (120, .7, 'SEGUIMIENTO', 1), (175, .5, 'AGENDA', 0)]) +
     '<div class="abs k" style="left:64px;right:64px;top:1240px;font-size:20px;color:#7fd4ff;text-align:center">Responde · Analiza · Recomienda</div>' +
     brand() + pg(4, N) + grain(S))

facts = [('12', 'preguntas'), ('1', 'por pantalla'), ('&lt;15', 'minutos'), ('0', 'tecnicismos')]
fx = ''.join(f'<div style="border-top:3px solid #9cc0ff;padding-top:16px"><div style="font-weight:800;font-size:110px;line-height:1">{a}</div><div class="k" style="font-size:22px;color:#9cc0ff;margin-top:8px">{b}</div></div>' for a, b in facts)
page('P03-05', S, 'navy',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:80px">Cómo funciona.</div>'
     f'<div class="abs" style="left:64px;right:64px;top:360px;display:grid;grid-template-columns:1fr 1fr;gap:56px 60px">{fx}</div>'
     '<div class="abs body" style="left:64px;right:64px;top:1030px">Sin compromiso. Sin saber de tecnología. Respondes desde el móvil, cuando te venga bien.</div>' +
     brand() + pg(5, N) + grain(S))

doc = ('<div class="doc" style="left:120px;top:330px;width:840px;height:820px;padding:56px 60px;transform:rotate(-2deg);font-size:30px;line-height:1.5">'
       '<div style="font-family:P;font-weight:800;font-size:40px;color:#00367d;letter-spacing:1px">INFORME · RADAR NEXIA</div>'
       '<div style="font-family:M;font-size:20px;color:#666;letter-spacing:2px;margin:6px 0 34px">PARA: TU NEGOCIO · ENVIADO POR EMAIL</div>'
       '<div>Captación ............ <span style="background:#e9f6f5">revisado</span></div><div>Atención ............. <span style="background:#ffe1ec">fuga detectada</span></div>'
       '<div>Cualificación ........ <span style="background:#e9f6f5">revisado</span></div><div>Seguimiento .......... <span style="background:#ffe1ec">fuga detectada</span></div>'
       '<div>Agenda ............... <span style="background:#e9f6f5">revisado</span></div>'
       '<div style="margin-top:34px;border-top:2px dashed #999;padding-top:24px">Nivel recomendado: <span style="font-family:PF;font-style:italic;color:#2e4be2;font-size:40px">el que de verdad necesitas</span><br>…o «todavía no es tu momento».</div>'
       '</div><div class="stamp" style="left:700px;top:1080px;transform:rotate(-8deg);font-size:28px">Ejemplo</div>')
page('P03-06', S, 'cream',
     '<div class="abs h" style="left:64px;right:64px;top:140px;font-size:66px;color:#00367d">Qué recibes.<em style="font-size:52px">Tu informe, en los próximos minutos.</em></div>' + doc +
     brand() + pg(6, N) + grain(S, True))

page('P03-07', S, 'deep',
     '<div class="abs h" style="left:64px;right:64px;top:140px;font-size:64px">No es para ti si…</div>'
     '<div class="abs" style="left:64px;right:64px;top:290px">' + lst(['Todavía no tienes clara tu oferta.', 'No recibes contactos con regularidad.', 'No existe ni un proceso manual.', 'No quieres compartir cómo trabajas.'], fs=42, gap=44) + '</div>'
     '<div class="abs" style="left:64px;right:64px;top:930px;border-top:2px solid rgba(255,255,255,.25);padding-top:40px">'
     '<div class="h" style="font-size:58px">¿Sigues aquí?<em style="font-size:52px">Solicita tu Radar NexIA gratuito.</em></div>'
     '<div class="cta" style="margin-top:30px">Enlace en la bio →</div></div>' + brand() + pg(7, N) + grain(S))

# ---------- FMA ----------
p4c = open(os.path.join(D, '../work/p4c.html')).read()
wrap = re.search(r'<div class="wrap">.*?</svg></div>', p4c, re.S).group(0).replace('src="7.jpg"', f'src="{W}7.jpg"').replace('<div class="wrap">','<div style="position:absolute;inset:0;filter:grayscale(.75) contrast(1.3) brightness(.62)">').replace('<img class="ph"','<img style="position:absolute;left:0;top:-250px;width:1080px"').replace('<svg class="cuffs"','<svg style="position:absolute;inset:0"')
page('FMA01', V, '',
     '<div class="abs" style="left:0;top:0;width:1080px;height:1350px;transform:scale(1.4222);transform-origin:50% 0;background:#05070d">' + wrap + '</div>'
     '<div class="fill" style="background:#0b1a4a;mix-blend-mode:color;opacity:.35"></div>'
     '<div class="fill" style="background:radial-gradient(ellipse 60% 40% at 50% 38%,rgba(0,0,0,0) 40%,rgba(3,5,12,.75) 100%),linear-gradient(180deg,rgba(3,5,12,0) 60%,rgba(3,5,12,.95) 78%)"></div>' +
     notif(560, 300, 'WHATSAPP · AHORA', '99+ mensajes nuevos', 'de 37 chats · «¿sigues ahí?»', w=450) +
     '<div class="abs h" style="left:64px;right:64px;top:1330px;font-size:84px">Tu negocio vende.<em style="font-size:84px;color:#8fb0ff">Pero tu WhatsApp te tiene secuestrada.</em></div>'
     '<div class="abs k" style="left:64px;right:64px;top:1640px;font-size:22px;color:#dfe6ff">Sigue a @somosnexia · negocios que venden sin tenerte de guardia</div>'
     '<div class="stamp" style="left:64px;top:1740px;transform:rotate(-3deg);font-size:24px;color:#e0206e;border-color:#e0206e">Exigen: 3 h/día</div>' + brand() + grain(V))

# FMA02 · parte de averías
N = 5
def leak(x, y, n):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:84px;height:84px;border:5px solid #c8102e;border-radius:50%;display:flex;align-items:center;justify-content:center;'
            f'font-family:M;font-size:34px;color:#c8102e;background:rgba(241,235,223,.85)">{n}</div>')
page('FMA02-01', S, 'cream',
     '<div class="abs k" style="left:64px;top:140px;font-size:22px;color:#c8102e">Parte de averías · confidencial</div>'
     '<div class="abs h" style="left:64px;right:64px;top:190px;font-size:66px;color:#00367d">¿Quieres invertir más en publicidad?<em style="font-size:54px">Primero dime qué haces con los contactos que ya te escriben.</em></div>' +
     submarine(40, 720, 1000, debris=False) + leak(250, 870, '01') + leak(560, 960, '02') + leak(820, 880, '03') +
     brand() + pg(1, N) + '<div class="handle" style="color:#00367d">3 vías de agua →</div>' + grain(S, True))

def averia(p, n, t, sint, cons):
    page(f'FMA02-{p:02d}', S, 'kraft',
         '<div class="doc" style="left:70px;top:150px;width:940px;height:1060px;padding:60px 64px;transform:rotate(-1.2deg);font-size:46px;line-height:1.4">'
         f'<div style="font-family:M;font-size:22px;letter-spacing:4px;color:#c8102e">PARTE DE AVERÍAS · VÍA DE AGUA {n}</div>'
         f'<div style="font-family:P;font-weight:800;font-size:76px;line-height:1;color:#00367d;margin:22px 0 46px;text-transform:uppercase;letter-spacing:-1px">{t}</div>'
         f'<div style="font-family:M;font-size:22px;letter-spacing:3px;color:#666">SÍNTOMA</div><div style="margin:8px 0 36px">{sint}</div>'
         f'<div style="font-family:M;font-size:22px;letter-spacing:3px;color:#666">CONSECUENCIA</div><div style="margin-top:8px">{cons}</div></div>'
         f'<div class="stamp" style="right:110px;top:1060px;transform:rotate(-7deg);font-size:30px">Vía {n}</div>' + pg(p, N) + grain(S, True, seed=p))
averia(2, '01', 'Respuestas tardías', 'La consulta llega a las 23:47. La respuesta, al día siguiente a media mañana.', 'El interés se enfría. O se va con quien contestó antes.')
averia(3, '02', 'Sin cualificación', 'Llamadas largas con gente que no tenía presupuesto, ni prisa, ni encaje.', 'Agenda llena. Facturación igual.')
averia(4, '03', 'Sin seguimiento', '«Me lo pienso y te digo». Y nadie vuelve a escribir.', 'Ventas que estaban a un mensaje de distancia.')
page('FMA02-05', S, 'ink',
     '<div class="abs h" style="left:64px;right:64px;top:260px;font-size:96px">Más leads no arreglan un mal seguimiento.</div>'
     '<div class="abs em" style="left:64px;right:64px;top:720px;font-size:56px;line-height:1.15">Síguenos para detectar las fugas comerciales que no se ven en tus likes.</div>'
     '<div class="cta" style="position:absolute;left:64px;top:1040px">Seguir a @somosnexia</div>' + brand() + pg(5, N) + grain(S))

# FMA03 · el robot no decide tu precio
page('FMA03', V, 'navy',
     img('8.jpg', 'object-position:50% 30%;filter:brightness(.8)') + '<div class="tint"></div><div class="fadet"></div>'
     '<div class="fill" style="background:linear-gradient(180deg,rgba(8,13,28,0) 60%,rgba(8,13,28,.9) 85%)"></div>'
     '<div class="abs h" style="left:64px;right:64px;top:170px;font-size:72px">No, no vamos a dejar que un robot<em style="font-size:76px">decida el precio de tu mentoría.</em></div>' +
     phone(250, 1000, 'Marta', 'en línea', [('in', 'Si me apunto hoy, ¿me haces un 30 % de descuento? 😅', '18:02'),
                                           ('out', '¡Gracias por preguntar, Marta! Los precios y descuentos los decide el equipo, no yo. Te paso con ellas ahora mismo 🙌', '18:02'),
                                           ('sys', 'Conversación derivada al equipo · con contexto')], w=580) +
     '<div class="demo" style="left:64px;top:940px">Ejemplo · demo</div>'
     '<div class="abs k" style="left:64px;right:64px;top:1800px;font-size:20px">Sigue a @somosnexia · IA sin perder tu esencia</div>' + brand() + grain(V))

# FMA04 · organigrama
def face(x, y, d, role, big=False):
    s = d / 150 * 0.5
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{d+120}px;text-align:center">'
            f'<div style="margin:0 auto;width:{d}px;height:{d}px;border-radius:50%;border:5px solid #00367d;background:url({W}1.jpg) no-repeat;'
            f'background-size:{1333*s:.0f}px;background-position:{-(680*s-d/2):.0f}px {-(470*s-d/2):.0f}px;box-shadow:6px 6px 0 #2e4be2"></div>'
            f'<div style="margin-top:14px;font-weight:800;font-size:{30 if big else 24}px;color:#00367d;text-transform:uppercase;line-height:1.1">{role}</div></div>')
lines = ('<svg class="fill" width="1080" height="1920"><g stroke="#00367d" stroke-width="4" fill="none">'
         '<path d="M540 640 V700 M200 700 H880 M200 700 V740 M540 700 V740 M880 700 V740"/>'
         '<path d="M200 1000 V1040 M880 1000 V1040 M540 1000 V1040 M200 1040 H880 M200 1040 V1080 M540 1040 V1080 M880 1040 V1080"/></g></svg>')
page('FMA04', V, 'cream',
     '<div class="abs k" style="left:64px;top:170px;font-size:24px;color:#2e4be2">Organigrama de tu empresa · v. 2026</div>' + lines +
     face(450, 300, 200, 'CEO', True) +
     face(110, 760, 160, 'Marketing') + face(450, 760, 160, 'Atención<br>al cliente') + face(790, 760, 160, 'Ventas') +
     face(110, 1100, 160, 'Agenda') + face(450, 1100, 160, 'Seguimiento') + face(790, 1100, 160, 'Recepción') +
     '<div class="abs h" style="left:64px;right:64px;top:1440px;font-size:70px;color:#00367d">Tu negocio tiene departamento comercial.<em style="font-size:96px">Se llama tú.</em></div>'
     '<div class="abs k" style="left:64px;right:64px;top:1790px;font-size:20px;color:#00367d">Sigue a @somosnexia si quieres dejar de contratarte a ti misma para todo</div>' +
     brand() + grain(V, True))

# ---------- RETARGETING ----------
page('RT01', V, 'cream',
     '<div class="abs" style="left:0;top:0;width:1080px;height:1120px;overflow:hidden">' + img('2.jpg', 'object-position:50% 25%') + '</div>'
     '<div class="abs h" style="left:64px;right:64px;top:1170px;font-size:78px;color:#00367d">Claro que nadie atiende como tú.<em style="font-size:58px">La pregunta es si necesitas hacerlo tú todo.</em></div>'
     '<div class="abs" style="left:64px;right:64px;top:1560px;display:flex;flex-wrap:wrap;gap:14px">'
     '<span class="chip">No inventa respuestas</span><span class="chip">No improvisa descuentos</span><span class="chip">Te pasa el testigo</span></div>'
     '<div class="cta b" style="position:absolute;left:64px;top:1700px;font-size:28px">Descubre cómo funciona Submarino NexIA →</div>' +
     '<div class="brand" style="color:#00367d">SOMOS <b>NEXIA</b></div>' + grain(V, True))

ivr = ('<div class="abs" style="left:90px;top:440px;width:900px;background:#cfd2c8;border:6px solid #8a8d84;border-radius:20px;padding:40px 46px;font-family:M;font-size:30px;line-height:1.5;color:#2b2d28;filter:grayscale(1);transform:rotate(-1.5deg)">'
       '<div style="font-size:20px;letter-spacing:4px;opacity:.7">ATENCIÓN AUTOMÁTICA · 2004</div>'
       'Bienvenida. Para precios, pulse 1.<br>Para información, pulse 2.<br>…<br>No le he entendido.<br>Para precios, pulse 1.</div>'
       '<div class="stamp" style="left:690px;top:760px;transform:rotate(-10deg);font-size:30px">Clienta perdida</div>')
page('RT02', V, 'navy',
     '<div class="abs h" style="left:64px;right:64px;top:150px;font-size:62px">Si tu IA responde como un contestador de 2004,<em style="font-size:66px">tenemos un problema.</em></div>' + ivr +
     phone(260, 960, 'Elena', 'en línea', [('in', 'Hola, ¿el programa sirve si vendo servicios y no cursos?', '11:20'),
                                           ('out', '¡Sí, Elena! Está pensado justo para servicios de alto valor. ¿Cuántas consultas te llegan a la semana, más o menos?', '11:20')], w=560) +
     '<div class="demo" style="left:64px;top:1560px">Ejemplo · demo</div>'
     '<div class="cta" style="position:absolute;left:64px;top:1680px">Reserva una demostración →</div>' + brand() + grain(V))

page('RT03', V, 'navy',
     '<div class="abs" style="left:0;top:0;width:1080px;height:1100px;overflow:hidden">' + img('5.jpg', 'object-position:50% 30%') + '<div class="tint"></div>'
     '<div class="fill" style="background:linear-gradient(180deg,rgba(11,19,36,0) 70%,#0b1324)"></div></div>'
     '<div class="abs h" style="left:64px;right:64px;top:1080px;font-size:80px">¿Otro software para configurar tú?<em style="font-size:96px">No, gracias.</em></div>'
     '<div class="abs body" style="left:64px;right:64px;top:1430px;font-size:32px">Tú nos cuentas cómo funciona tu negocio. <b>Nosotras</b> nos encargamos de la arquitectura, el entrenamiento, las conexiones y las pruebas.</div>'
     '<div class="cta" style="position:absolute;left:64px;top:1700px;font-size:28px">Descubre qué implementaríamos por ti →</div>' + brand() + grain(V))

page('RT04-1', V, 'deep',
     '<div class="abs h" style="left:64px;right:64px;top:200px;font-size:80px">No compres una automatización<em style="font-size:72px">sin saber dónde se atasca tu negocio.</em></div>' +
     sonar(540, 1180, 430, [(-140, .7, '¿ATASCO?', 1), (-30, .55, '', 0), (40, .82, '¿FUGA?', 1), (150, .6, '', 0), (100, .3, '', 0)], H=1920) +
     '<div class="abs k" style="left:64px;right:64px;top:1720px;text-align:center;font-size:22px;color:#7fd4ff">Radar NexIA · 1/3</div>' + brand() + grain(V))
page('RT04-2', V, 'deep',
     '<div class="abs h" style="left:64px;right:64px;top:220px;font-size:70px">Radar NexIA analiza cómo…</div>'
     '<div class="abs" style="left:64px;right:64px;top:520px">' + lst(['…<b>captas</b> contactos.', '…los <b>atiendes</b>.', '…los <b>cualificas</b>.', '…les haces <b>seguimiento</b>.'], mark='✓', mc='#7fd4ff', fs=60, gap=60) + '</div>'
     '<div class="abs em" style="left:64px;right:64px;top:1250px;font-size:62px;color:#fff;line-height:1.15">Sin compromiso.<br>Sin tener que entender de tecnología.</div>'
     '<div class="abs k" style="left:64px;right:64px;top:1720px;text-align:center;font-size:22px;color:#7fd4ff">Radar NexIA · 2/3</div>' + brand() + grain(V))
page('RT04-3', V, 'blue',
     '<div class="abs h" style="left:64px;right:64px;top:400px;font-size:110px">Completa tu diagnóstico<em style="font-size:110px;color:#fff">gratuito.</em></div>'
     '<div class="abs k" style="left:64px;top:900px;font-size:26px;color:#dfe8ff">12 preguntas · menos de 15 minutos</div>'
     '<div class="abs" style="left:140px;right:140px;top:1080px;background:#fff;color:#2e4be2;border-radius:22px;padding:30px;text-align:center;font-weight:800;font-size:34px;box-shadow:0 20px 50px rgba(0,0,0,.3)">🔗 RADAR NEXIA</div>'
     '<div class="abs" style="left:0;right:0;top:1260px;text-align:center;font-size:110px">☝️</div>'
     '<div class="abs k" style="left:64px;right:64px;top:1720px;text-align:center;font-size:22px;color:#dfe8ff">Radar NexIA · 3/3</div>' + brand() + grain(V))

import json; json.dump(PIECES, open(os.path.join(D, 'list1.json'), 'w'))
print(len(PIECES))
