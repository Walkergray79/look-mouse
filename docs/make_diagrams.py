"""Regenerates the diagrams in this folder:  python3 docs/make_diagrams.py"""
import os
out = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, LINE, ACC, PI, HI, BG, CARD, SCR = "#1c2330", "#5b667a", "#cfd5e0", "#2f6fed", "#1a9a5b", "#ffcf3f", "#f7f8fb", "#ffffff", "#e3e9f6"
FONT = 'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif"'

def head(w, h, title, sub):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" {FONT} role="img" aria-label="{title}">
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="{BG}" stroke="{LINE}" stroke-width="2"/>
<text x="30" y="44" font-size="22" font-weight="700" fill="{INK}">{title}</text>
<text x="30" y="68" font-size="14" fill="{MUTED}">{sub}</text>
'''

def t(x, y, s, size=13, fill=INK, anchor="middle", weight="400"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>\n'

# ---------------------------------------------------------------- setup.svg
s = head(960, 610, "What's on the desk", "Your screens, keyboard and mouse stay exactly as they are. The Pi and camera are the only additions.")
# screens
for x, y, w, h, a, b in ((150, 100, 110, 190, "Left", "(portrait)"), (290, 150, 230, 135, "Centre", ""), (550, 150, 230, 135, "Right", "")):
    s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{SCR}" stroke="{INK}" stroke-width="2.5"/>\n'
    s += t(x + w / 2, y + h / 2 + (0 if b else 5), a, 14, INK, weight="600")
    if b: s += t(x + w / 2, y + h / 2 + 18, b, 12, MUTED)
# camera
s += f'<path d="M388 141 H275 V400 H330" fill="none" stroke="{PI}" stroke-width="3"/>\n'
s += f'<rect x="388" y="130" width="34" height="20" rx="5" fill="{PI}"/><circle cx="405" cy="140" r="5" fill="#fff"/>\n'
s += f'<path d="M432 134 L470 112" stroke="{MUTED}" stroke-width="1.5"/>\n'
s += t(476, 108, "Camera", 14, PI, "start", "700") + t(476, 126, "watches your head and eyes", 12, MUTED, "start")
s += t(266, 345, "camera cable", 12, MUTED, "end")
# Pi
s += f'<rect x="330" y="360" width="160" height="80" rx="10" fill="{PI}"/>\n'
s += t(410, 394, "Raspberry Pi 4", 16, "#fff", weight="700") + t(410, 416, "works out where you look", 12, "#fff")
s += t(410, 466, "On your network: its settings page", 12, MUTED) + t(410, 482, "opens in your browser", 12, MUTED)
# USB
s += f'<path d="M490 400 H660" stroke="{ACC}" stroke-width="3"/><path d="M660 400 l-12 -7 v14 z" fill="{ACC}"/>\n'
s += t(575, 388, "USB cable", 13, ACC, weight="700") + t(575, 420, "the computer sees an", 12, MUTED) + t(575, 436, "ordinary mouse", 12, MUTED)
# PC
s += f'<rect x="660" y="360" width="180" height="80" rx="10" fill="{CARD}" stroke="{INK}" stroke-width="2.5"/>\n'
s += t(750, 394, "Windows computer", 16, INK, weight="700") + t(750, 416, "nothing installed on it", 12, MUTED)
s += f'<path d="M750 285 V360" stroke="{MUTED}" stroke-width="2" stroke-dasharray="5 5"/>\n' + t(760, 328, "screen cables", 12, MUTED, "start")
# keyboard + mouse
s += f'<path d="M700 505 V440 M805 500 V440" stroke="{MUTED}" stroke-width="2"/>\n'
s += f'<rect x="610" y="505" width="160" height="44" rx="7" fill="{CARD}" stroke="{INK}" stroke-width="2.5"/>\n'
for i in range(8):
    s += f'<rect x="{620 + i * 15}" y="514" width="11" height="9" rx="2" fill="{LINE}"/>\n'
s += f'<rect x="{740}" y="512" width="22" height="13" rx="3" fill="{HI}" stroke="{INK}" stroke-width="1.5"/>\n'
s += f'<rect x="620" y="531" width="140" height="9" rx="2" fill="{LINE}"/>\n'
s += f'<rect x="790" y="500" width="30" height="50" rx="15" fill="{CARD}" stroke="{INK}" stroke-width="2.5"/><path d="M805 500 V520" stroke="{INK}" stroke-width="2"/>\n'
s += f'<path d="M608 519 H597" stroke="{MUTED}" stroke-width="1.5"/>\n'
s += t(592, 516, "Scroll Lock", 14, INK, "end", "700") + t(592, 534, "is the trigger", 12, MUTED, "end")
s += t(715, 580, "Your normal keyboard and mouse, plugged in as usual", 12, MUTED)
open(f"{out}/setup.svg", "w").write(s + "</svg>\n")

# ---------------------------------------------------------------- step strips
EYE = f'<path d="M-30 0 Q0 -24 30 0 Q0 24 -30 0 Z" fill="#fff" stroke="{INK}" stroke-width="2.5"/><circle r="9" fill="{ACC}"/><circle r="3.5" fill="{INK}"/>'
KEY = f'<rect x="-34" y="-20" width="68" height="40" rx="8" fill="{HI}" stroke="{INK}" stroke-width="2.5"/><text y="5" font-size="13" font-weight="700" text-anchor="middle" fill="{INK}">ScrLk</text>'
CHIP = f'<rect x="-26" y="-18" width="52" height="36" rx="5" fill="{PI}"/>' + "".join(f'<rect x="{-20 + i * 10}" y="-24" width="4" height="6" fill="{PI}"/><rect x="{-20 + i * 10}" y="18" width="4" height="6" fill="{PI}"/>' for i in range(5)) + '<circle r="6" fill="#fff"/>'
CUR = f'<path d="M-10 -22 L-10 16 L0 7 L7 22 L13 19 L6 5 L19 5 Z" fill="{INK}" stroke="#fff" stroke-width="2"/>'
TERM = f'<rect x="-32" y="-20" width="64" height="40" rx="6" fill="{INK}"/><text x="-22" y="5" font-size="15" font-weight="700" fill="{HI}" font-family="monospace">&gt;_</text>'
SCRN = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{SCR}" stroke="{INK}" stroke-width="2"/>' for x, y, w, h in ((-36, -20, 16, 34), (-17, -12, 26, 18), (12, -12, 26, 18)))
CLICK = SCRN + f'<g transform="translate(26 4) scale(.6)">{CUR}</g>'
DOT = f'<rect x="-32" y="-20" width="64" height="40" rx="6" fill="#0d1016"/><circle r="8" fill="{HI}"/><circle r="2.5" fill="#0d1016"/>'

def strip(name, title, sub, cards):
    s = head(960, 300, title, sub)
    for i, (icon, ttl, a, b) in enumerate(cards):
        x = 30 + i * 230
        s += f'<rect x="{x}" y="92" width="210" height="182" rx="12" fill="{CARD}" stroke="{LINE}" stroke-width="1.5"/>\n'
        s += f'<circle cx="{x + 24}" cy="116" r="13" fill="{ACC}"/>' + t(x + 24, 121, str(i + 1), 14, "#fff", weight="700")
        s += f'<g transform="translate({x + 105} 152)">{icon}</g>\n'
        s += t(x + 105, 210, ttl, 16, INK, weight="700") + t(x + 105, 233, a, 12, MUTED) + t(x + 105, 250, b, 12, MUTED)
        if i < len(cards) - 1:
            s += f'<path d="M{x + 213} 183 h14 m-6 -6 l6 6 l-6 6" fill="none" stroke="{ACC}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>\n'
    open(f"{out}/{name}", "w").write(s + "</svg>\n")

strip("how-it-works.svg", "What happens each time", "The cursor only ever moves when you ask it to.", [
    (EYE, "Look", "Look at the spot you want,", "on any screen."),
    (KEY, "Press", "Tap Scroll Lock on your", "normal keyboard."),
    (CHIP, "Pi locates", "The Pi reads your head and", "eye direction from the camera."),
    (CUR, "Cursor jumps", "The cursor appears there.", "Carry on with your mouse."),
])
strip("first-time-setup.svg", "First-time setup", "Done once. Calibrate again if you move the camera or a screen.", [
    (TERM, "Install", "Run the installer on the Pi,", "reboot, plug in the USB cable."),
    (SCRN, "Screens", "Enter your Windows screen", "layout in the settings page."),
    (CLICK, "Pointer check", "Click each screen and watch", "the cursor land on it."),
    (DOT, "Calibrate", "On each screen, look at the", "dot and press Space."),
])

# ---------------------------------------------------------------- glasses.svg
s = head(960, 400, "The glasses upgrade", "Two cameras, two jobs. The Pi adds the readings together.")
def box(x, y, w, h, colour, title, a, b):
    r = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{CARD}" stroke="{colour}" stroke-width="2.5"/>\n'
    return r + t(x + w / 2, y + h - 62, title, 16, colour, weight="700") + t(x + w / 2, y + h - 40, a, 12, MUTED) + t(x + w / 2, y + h - 23, b, 12, MUTED)
# desk camera: a head seen from the front, with a turn arrow
s += box(30, 100, 270, 190, PI, "Desk camera", "Which way your head is turned,", "to within a degree or two.")
s += f'<g transform="translate(165 158)"><circle r="26" fill="{SCR}" stroke="{INK}" stroke-width="2.5"/><circle cx="-9" cy="-4" r="3" fill="{INK}"/><circle cx="9" cy="-4" r="3" fill="{INK}"/><path d="M-8 11 Q0 16 8 11" fill="none" stroke="{INK}" stroke-width="2"/><path d="M-44 -6 A46 46 0 0 1 -30 -34 m0 0 l-9 1 m9 -1 l1 9 M44 -6 A46 46 0 0 0 30 -34 m0 0 l9 1 m-9 -1 l-1 9" fill="none" stroke="{PI}" stroke-width="2.5" stroke-linecap="round"/></g>\n'
s += t(330, 205, "+", 34, INK, weight="700")
# glasses camera: glasses with a small camera aimed at one eye
s += box(360, 100, 270, 190, ACC, "Glasses camera", "Which way your eye is turned", "within your head, much more finely.")
s += f'<g transform="translate(495 158)"><rect x="-58" y="-18" width="48" height="36" rx="10" fill="{SCR}" stroke="{INK}" stroke-width="2.5"/><rect x="10" y="-18" width="48" height="36" rx="10" fill="{SCR}" stroke="{INK}" stroke-width="2.5"/><path d="M-10 -4 Q0 -12 10 -4" fill="none" stroke="{INK}" stroke-width="2.5"/><circle cx="34" cy="0" r="8" fill="{ACC}"/><circle cx="34" cy="0" r="3.5" fill="{INK}"/><circle cx="-34" cy="0" r="8" fill="#fff" stroke="{INK}" stroke-width="1.5"/><circle cx="-34" cy="0" r="3.5" fill="{INK}"/><rect x="50" y="20" width="18" height="12" rx="3" fill="{ACC}"/><path d="M52 20 L40 8" stroke="{ACC}" stroke-width="2" stroke-dasharray="3 3"/></g>\n'
s += f'<path d="M640 195 h26 m-7 -7 l7 7 l-7 7" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>\n'
# result
s += f'<rect x="680" y="100" width="250" height="190" rx="12" fill="{INK}"/>\n'
s += f'<g transform="translate(805 158)"><rect x="-50" y="-30" width="100" height="60" rx="5" fill="{SCR}"/><circle cx="14" cy="-6" r="9" fill="none" stroke="{ACC}" stroke-width="2"/><g transform="translate(16 -2) scale(.55)">{CUR}</g></g>\n'
s += t(805, 228, "A finer landing spot", 16, "#fff", weight="700") + t(805, 250, "Head direction + eye direction", 12, "#c9d1e0") + t(805, 267, "= the point on the screen.", 12, "#c9d1e0")
s += t(480, 330, "Without the glasses, the desk camera does both jobs, and can only see your eyes roughly from that distance.", 13, MUTED)
s += t(480, 352, "With them, it only has to track your head. Calibrate again whenever the glasses have shifted on your face.", 13, MUTED)
open(f"{out}/glasses.svg", "w").write(s + "</svg>\n")
