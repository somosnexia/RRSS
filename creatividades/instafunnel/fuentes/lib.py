import os, math, random
D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, 'html')
W = '../../work/'
PIECES = []  # (name, size, html)

def page(name, size, cls, inner):
    H = 1350 if size == 's45' else 1920
    html = ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="common.css"></head>'
            f'<body><div class="c {size} {cls}">{inner}</div></body></html>')
    open(os.path.join(OUT, name + '.html'), 'w').write(html)
    PIECES.append((name, size))

def grain(size, mult=False, seed=3):
    H = 1350 if size == 's45' else 1920
    return (f'<svg class="grain{" m" if mult else ""}" width="1080" height="{H}"><filter id="gr{seed}"><feTurbulence type="fractalNoise" '
            f'baseFrequency=".85" numOctaves="3" seed="{seed}"/><feColorMatrix type="saturate" values="0"/></filter>'
            f'<rect width="100%" height="100%" filter="url(#gr{seed})"/></svg>')

def brand(): return '<div class="brand">SOMOS <b>NEXIA</b></div>'
def handle(t='@somosnexia'): return f'<div class="handle">{t}</div>'
def pg(i, n): return f'<div class="pg">{i:02d} / {n:02d}</div>'

def img(src, style='', cls='ph'):
    return f'<img class="{cls}" src="{W}{src}" style="{style}">'

def phone(x, y, name, sub, msgs, w=560, av='', scale=1, rot=0):
    m = ''
    for k, t, *tm in msgs:
        if k == 'day': m += f'<div class="day">{t}</div>'
        elif k == 'sys': m += f'<div class="msg sys">{t}</div>'
        else: m += f'<div class="msg {k}">{t}<span class="t">{tm[0] if tm else ""}</span></div>'
    avs = f'background-image:url({W}{av})' if av else 'background:#9fb3c8'
    return (f'<div class="phone" style="left:{x}px;top:{y}px;width:{w}px;transform:scale({scale}) rotate({rot}deg);transform-origin:top left">'
            f'<div class="scr"><div class="wa-h"><span style="font-size:30px">‹</span><div class="av" style="{avs};background-size:cover;background-position:center"></div>'
            f'<div>{name}<small>{sub}</small></div></div><div class="wa-b">{m}</div></div></div>')

def notif(x, y, app, title, body, rot=0, w=520):
    return (f'<div class="notif" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg)">'
            f'<span class="app">{app}</span><br>{title}<small>{body}</small></div>')

def hud(cx, cy, s=1.0, labels=True, H=1350):
    r = lambda v: v * s
    tk = ''
    for i in range(72):
        a = i * 5 * math.pi / 180; r1 = r(226); r2 = r(244 if i % 6 == 0 else 234)
        tk += f'<line x1="{cx+r1*math.cos(a):.1f}" y1="{cy+r1*math.sin(a):.1f}" x2="{cx+r2*math.cos(a):.1f}" y2="{cy+r2*math.sin(a):.1f}" stroke-width="{2 if i%6==0 else 1}"/>'
    lab = ''
    if labels:
        lab = (f'<g font-family="M" font-size="17" fill="#e8f1ff" letter-spacing="2" opacity=".85">'
               f'<text x="{cx+r(265)}" y="{cy-r(240)}">SÓNAR 360°</text><text x="{cx+r(265)}" y="{cy-r(218)}" opacity=".7">ESCANEANDO…</text>'
               f'<text x="{cx+r(290)}" y="{cy+r(80)}">CONTACTOS</text><text x="{cx+r(290)}" y="{cy+r(102)}" opacity=".7">SIN RESPUESTA</text></g>')
    return f'''<svg class="fill" style="mix-blend-mode:screen" width="1080" height="{H}">
 <defs><radialGradient id="hg" cx="{cx}" cy="{cy}" r="{r(120)}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#8fc8ff" stop-opacity=".5"/><stop offset="1" stop-color="#8fc8ff" stop-opacity="0"/></radialGradient></defs>
 <circle cx="{cx}" cy="{cy}" r="{r(120)}" fill="url(#hg)"/>
 <g fill="none" stroke="#e8f1ff">
  <circle cx="{cx}" cy="{cy}" r="{r(78)}" stroke-width="2" opacity=".7"/>
  <circle cx="{cx}" cy="{cy}" r="{r(150)}" stroke-width="1.2" opacity=".5"/>
  <circle cx="{cx}" cy="{cy}" r="{r(168)}" stroke-width="10" opacity=".22" stroke-dasharray="210 30 60 30 120 40"/>
  <circle cx="{cx}" cy="{cy}" r="{r(200)}" stroke-width="1" opacity=".45" stroke-dasharray="2 9"/>
  <path d="M{cx} {cy-r(250)} A{r(250)} {r(250)} 0 0 1 {cx+r(250)} {cy}" stroke-width="3" opacity=".8"/>
  <path d="M{cx} {cy-r(250)} A{r(250)} {r(250)} 0 0 0 {cx-r(250)} {cy}" stroke-width="1.2" opacity=".4"/>
  <circle cx="{cx}" cy="{cy}" r="{r(330)}" stroke-width="1.2" opacity=".35"/>
  <circle cx="{cx}" cy="{cy}" r="{r(420)}" stroke-width="1" opacity=".25" stroke-dasharray="1 14"/>
 </g>
 <g stroke="#e8f1ff" opacity=".6">{tk}</g>
 <g fill="#e8f1ff"><circle cx="{cx}" cy="{cy-r(250)}" r="5" opacity=".9"/><circle cx="{cx+r(250)}" cy="{cy}" r="5" opacity=".9"/>
 <circle cx="{cx+r(231)}" cy="{cy-r(108)}" r="{r(13)}" opacity=".55"/><circle cx="{cx+r(264)}" cy="{cy-r(50)}" r="{r(10)}" opacity=".45"/></g>
 {lab}</svg>'''

def sonar(cx, cy, R, blips, H=1350, sweep=40, rings=4, color='#7fd4ff'):
    """radar screen: blips = list of (angle_deg, frac, label, hot)"""
    g = f'<svg class="fill" width="1080" height="{H}"><defs><radialGradient id="sg" cx="{cx}" cy="{cy}" r="{R}" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#0f3a5e"/><stop offset="1" stop-color="#06121f"/></radialGradient>'
    g += f'<linearGradient id="sw" gradientUnits="userSpaceOnUse" x1="{cx}" y1="{cy}" x2="{cx+R}" y2="{cy}"><stop offset="0" stop-color="{color}" stop-opacity=".0"/><stop offset="1" stop-color="{color}" stop-opacity=".35"/></linearGradient>'
    g += '<filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
    g += f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#sg)" stroke="{color}" stroke-opacity=".6" stroke-width="3"/>'
    for i in range(1, rings + 1):
        g += f'<circle cx="{cx}" cy="{cy}" r="{R*i/(rings+1):.0f}" fill="none" stroke="{color}" stroke-opacity=".25" stroke-width="1.5"/>'
    for a in range(0, 360, 30):
        t = math.radians(a)
        g += f'<line x1="{cx}" y1="{cy}" x2="{cx+R*math.cos(t):.0f}" y2="{cy+R*math.sin(t):.0f}" stroke="{color}" stroke-opacity=".12"/>'
    for a in range(0, 360, 5):
        t = math.radians(a); l = 18 if a % 30 == 0 else 8
        g += f'<line x1="{cx+(R-l)*math.cos(t):.0f}" y1="{cy+(R-l)*math.sin(t):.0f}" x2="{cx+R*math.cos(t):.0f}" y2="{cy+R*math.sin(t):.0f}" stroke="{color}" stroke-opacity=".6"/>'
    a0 = math.radians(-90 + sweep); a1 = math.radians(-90 + sweep - 50)
    g += f'<path d="M{cx} {cy} L{cx+R*math.cos(a1):.0f} {cy+R*math.sin(a1):.0f} A{R} {R} 0 0 1 {cx+R*math.cos(a0):.0f} {cy+R*math.sin(a0):.0f} Z" fill="url(#sw)"/>'
    g += f'<line x1="{cx}" y1="{cy}" x2="{cx+R*math.cos(a0):.0f}" y2="{cy+R*math.sin(a0):.0f}" stroke="{color}" stroke-width="3" opacity=".9"/>'
    for ang, fr, lab, hot in blips:
        t = math.radians(ang); x = cx + R * fr * math.cos(t); y = cy + R * fr * math.sin(t)
        c = '#ff4d8d' if hot else color
        g += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="{c}" filter="url(#glow)"/><circle cx="{x:.0f}" cy="{y:.0f}" r="20" fill="none" stroke="{c}" stroke-opacity=".5"/>'
        if lab:
            anchor = 'start' if math.cos(t) >= -0.2 else 'end'; dx = 30 if anchor == 'start' else -30
            g += f'<text x="{x+dx:.0f}" y="{y+7:.0f}" text-anchor="{anchor}" font-family="M" font-size="20" letter-spacing="2" fill="{c}">{lab}</text>'
    g += '</svg>'
    return g

def submarine(x, y, w, ink='#00367d', ink2='#2e4be2', paper='#f1ebdf', debris=True, id='s'):
    """riso-style engraved submarine. viewBox 1000x520"""
    hull = 'M110 300 C110 228 250 196 520 196 L770 202 C870 208 935 250 945 300 C935 350 870 388 770 394 L520 400 C250 400 110 372 110 300 Z'
    tower = 'M455 198 L478 112 C480 104 488 100 496 100 L628 100 C636 100 644 106 646 114 L668 200 Z'
    hatch = ''.join(f'<line x1="{i}" y1="300" x2="{i-90}" y2="420"/>' for i in range(120, 1000, 12))
    hatch2 = ''.join(f'<line x1="{i}" y1="96" x2="{i-60}" y2="200"/>' for i in range(470, 700, 10))
    ports = ''.join(f'<circle cx="{px}" cy="290" r="17" fill="{paper}" stroke="{ink}" stroke-width="5"/><circle cx="{px-4}" cy="286" r="6" fill="{ink2}" opacity=".6"/>' for px in range(250, 760, 85))
    rivets = ''.join(f'<circle cx="{px}" cy="236" r="3" fill="{ink}"/><circle cx="{px}" cy="352" r="3" fill="{ink}"/>' for px in range(180, 900, 28))
    bubbles = ''.join(f'<circle cx="{960+random.Random(i).randint(-10,40)}" cy="{300-i*26}" r="{4+ (i*7)%11}" fill="none" stroke="{ink}" stroke-width="3"/>' for i in range(8))
    deb = ''
    if debris:
        for (bx, by, t, r) in [(60, 40, '¿precio?', -8), (330, -10, '¿info?', 6), (730, 20, '¿sigues ahí?', -4), (40, 450, 'visto 23:47', 5), (700, 445, '¿hay plazas?', -6)]:
            deb += (f'<g transform="translate({bx},{by}) rotate({r})"><rect x="0" y="0" width="{len(t)*19+44}" height="62" rx="20" fill="{paper}" stroke="{ink}" stroke-width="4"/>'
                    f'<path d="M24 60 L18 82 L44 60" fill="{paper}" stroke="{ink}" stroke-width="4" stroke-linejoin="round"/><rect x="20" y="58" width="30" height="6" fill="{paper}"/>'
                    f'<text x="22" y="42" font-family="P" font-weight="600" font-size="30" fill="{ink}">{t}</text></g>')
    return f'''<svg style="position:absolute;left:{x}px;top:{y}px" width="{w}" height="{w*0.52:.0f}" viewBox="0 0 1000 520">
<defs><clipPath id="{id}h"><path d="{hull}"/></clipPath><clipPath id="{id}t"><path d="{tower}"/></clipPath></defs>
<g transform="translate(9,7)" opacity=".85" style="mix-blend-mode:multiply"><path d="{hull}" fill="{ink2}"/><path d="{tower}" fill="{ink2}"/></g>
<path d="{hull}" fill="none" stroke="{ink}" stroke-width="7"/>
<g clip-path="url(#{id}h)" stroke="{ink}" stroke-width="3">{hatch}</g>
<path d="{tower}" fill="{paper}" stroke="{ink}" stroke-width="7"/>
<g clip-path="url(#{id}t)" stroke="{ink}" stroke-width="2.5" opacity=".7">{hatch2}</g>
<path d="M600 100 L600 30 L650 30" fill="none" stroke="{ink}" stroke-width="9" stroke-linecap="round"/>
<rect x="640" y="18" width="34" height="24" rx="5" fill="{ink}"/>
<path d="M905 262 L985 222 L990 300 L985 378 L905 338 Z" fill="{paper}" stroke="{ink}" stroke-width="6"/>
<path d="M120 300 L60 300" stroke="{ink}" stroke-width="5"/>
<path d="M300 205 L330 168 L380 168 L360 205" fill="{paper}" stroke="{ink}" stroke-width="5"/>
{ports}{rivets}
<text x="300" y="350" font-family="M" font-size="34" letter-spacing="10" fill="{ink}">NEXIA · S-01</text>
{bubbles}{deb}
</svg>'''

def badge(x, y, text, rot=0, bg='#fff', top='HOLA, SOY', color='#c8102e', w=420):
    return (f'<div class="abs" style="left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg);background:{color};border-radius:18px;'
            f'box-shadow:0 10px 24px rgba(0,0,0,.35);padding:10px 0 16px;text-align:center;font-family:P">'
            f'<div style="color:#fff;font-weight:800;font-size:30px;letter-spacing:2px">{top}</div>'
            f'<div style="background:{bg};margin:8px 14px 0;border-radius:6px;padding:16px 10px;color:#111;font-family:SE;font-size:38px;line-height:1.05">{text}</div></div>')
