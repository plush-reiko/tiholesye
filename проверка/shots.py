"""Снимки «Тихолесья» для проверки на глаз (основа — Приложение В ТЗ 21.11).

Запуск:
  python3 -m http.server 8765 --bind 127.0.0.1 --directory <папка репозитория>   # в отдельном окне
  python3 shots.py <папка для снимков> [URL]
"""
import asyncio, base64, os, sys
from playwright.async_api import async_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else 'shots'
URL = sys.argv[2] if len(sys.argv) > 2 else 'http://127.0.0.1:8765/index.html'
os.makedirs(OUT, exist_ok=True)

SHEET = r"""({what, scale}) => {
  const T = window.__tl, A = T.Art, cv = document.createElement('canvas'), x = cv.getContext('2d');
  const label = (s, cx, cy, col) => { x.fillStyle = col; x.font = `${10 * scale}px sans-serif`; x.textAlign = 'center'; x.fillText(s, cx, cy); };
  if (what === 'skins' || what === 'silhouettes') {
    const cols = 6, cw = 110 * scale, ch = 120 * scale, n = T.SKINS.length, dark = what === 'skins';
    cv.width = cw * cols; cv.height = ch * Math.ceil(n / cols);
    x.fillStyle = dark ? '#141a52' : '#ffffff'; x.fillRect(0, 0, cv.width, cv.height);
    T.SKINS.forEach((sk, i) => {
      const c2 = document.createElement('canvas'); c2.width = cw; c2.height = ch; const y = c2.getContext('2d');
      y.translate(cw / 2, ch - 22 * scale); y.scale(scale * 1.2, scale * 1.2); A.char(y, sk, { t: 0.873, wing: 1 });
      if (!dark) { y.setTransform(1, 0, 0, 1, 0, 0); y.globalCompositeOperation = 'source-in'; y.fillStyle = '#000'; y.fillRect(0, 0, cw, ch); }
      const ox = (i % cols) * cw, oy = Math.floor(i / cols) * ch;
      x.drawImage(c2, ox, oy); label(sk.name, ox + cw / 2, oy + ch - 6 * scale, dark ? '#eef0ff' : '#000');
    });
  }
  if (what === 'states') {
    const S = [['покой', { t: 0.873, wing: 1 }], ['моргает', { t: 0.873, wing: 1, blink: true }], ['взмах', { t: 0.873, wing: 1, flap: 0.6 }], ['без заряда', { t: 0.873, wing: 0 }]];
    const cw = 110 * scale, ch = 110 * scale;
    cv.width = cw * S.length; cv.height = ch * T.SKINS.length; x.fillStyle = '#141a52'; x.fillRect(0, 0, cv.width, cv.height);
    T.SKINS.forEach((sk, r) => S.forEach(([nm, a], k) => {
      x.save(); x.translate(k * cw + cw / 2, r * ch + ch - 22 * scale); x.scale(scale * 1.2, scale * 1.2); A.char(x, sk, a); x.restore();
      label(`${sk.name} · ${nm}`, k * cw + cw / 2, r * ch + ch - 6 * scale, '#eef0ff');
    }));
  }
  if (what === 'plats') {
    A.setScale(scale);
    const types = [['static', 84], ['moving', 84], ['bouncy', 72], ['puff', 66], ['fake', 78], ['phase', 78], ['home', 150]];
    const cw = 170 * scale, ch = 80 * scale;
    cv.width = cw * 2; cv.height = ch * Math.ceil(types.length / 2); x.fillStyle = '#1a155e'; x.fillRect(0, 0, cv.width, cv.height);
    types.forEach(([tp, w], i) => {
      const s = A.plat(tp, w, 0, 1), cx = (i % 2) * cw + cw / 2, cy = Math.floor(i / 2) * ch + 22 * scale;
      x.drawImage(s.c, cx - s.ox * scale, cy - s.oy * scale, s.w * scale, s.h * scale); label(tp, cx, cy + 52 * scale, '#eef0ff');
    });
  }
  return cv.toDataURL('image/png');
}"""

JUMP = r"""(h) => {
  const T = window.__tl, g = T.game, P = T.P, y = g.startY + h * 10;
  for (let k = 0; k < 40 && g.plats.length; k++) T.genUpTo(y + 1500);
  P.y = y; P.vy = 400; T.run.maxY = y; g.camY = y - T.view.H * 0.44;
  for (let k = 0; k < 30; k++) T.update(1 / 60);
  P.y = y + 200; P.vy = 300; g.camY = P.y - T.view.H * 0.44; T.update(1 / 60); T.render();
}"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get('CHROME') or None)
        ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
        await pg.goto(URL)
        await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
        await pg.wait_for_timeout(1200)
        shot = lambda name: pg.screenshot(path=os.path.join(OUT, name + '.png'))
        await shot('01-menu')
        await pg.click('#bShop'); await pg.wait_for_timeout(400); await shot('02-shop')
        await pg.click('#shop [data-close]'); await pg.wait_for_timeout(200)
        await pg.click('#bSet'); await pg.wait_for_timeout(200); await pg.click('#bHelp'); await pg.wait_for_timeout(400); await shot('03-help')
        await pg.click('#help [data-close]'); await pg.wait_for_timeout(200); await pg.click('#settings [data-close]'); await pg.wait_for_timeout(200)
        for what in ['skins', 'silhouettes', 'states', 'plats']:
            data = await pg.evaluate(SHEET, {'what': what, 'scale': 3})
            open(os.path.join(OUT, f'10-{what}.png'), 'wb').write(base64.b64decode(data.split(',')[1]))
        await pg.evaluate('() => { const T = window.__tl; T.game.zen = true; T.startRun(true); }')
        await pg.wait_for_timeout(800)
        for h in [350, 1100, 2100, 3600, 5600]:
            await pg.evaluate(JUMP, h); await pg.wait_for_timeout(400); await shot(f'20-run-{h}m')
        print('ошибок в консоли:', len(errors)); [print(' ', e) for e in errors[:20]]
        await b.close()

asyncio.run(main())
