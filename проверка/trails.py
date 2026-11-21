"""Следы всех обликов в забеге: python3 trails.py out.png [lite]
Для каждого облика: забег (дзен), герой летит вверх и качается влево-вправо 1,2 с; снимок области вокруг героя."""
import asyncio, os, sys
from playwright.async_api import async_playwright
from PIL import Image
OUT = sys.argv[1]
LITE = len(sys.argv) > 2 and sys.argv[2] == 'lite'
URL = os.environ.get('TL_URL', 'http://127.0.0.1:8765/index.html')
SIM = r"""({id, lite}) => {
  const T = window.__tl, g = T.game, P = T.P;
  T.save.skin = id; T.save.set.fx = lite ? 'low' : 'high'; g.zen = true; T.startRun(true);
  g.parts.length = 0; P.hist.length = 0;
  let maxTrail = 0;
  for (let i = 0; i < 80; i++) {
    g.plats.length = 0; g.coins.length = 0; g.beasts.length = 0;
    P.vy = 520; P.x = 200 + 70 * Math.sin(i / 60 * 2.6);
    T.update(1 / 60);
    let n = 0; for (const q of g.parts) if (q.trail) n++; maxTrail = Math.max(maxTrail, n);
  }
  g.plats.length = 0; g.coins.length = 0; T.render();
  const s = T.view.s; return { x: P.x * s, y: (T.view.H - (P.y - g.camY)) * s, maxTrail, face: P.face };
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
        pg = await ctx.new_page(); errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
        await pg.goto(URL)
        await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
        ids = await pg.evaluate('() => window.__tl.SKINS.map((s) => s.id)')
        tiles = []
        for sid in ids:
            r = await pg.evaluate(SIM, {'id': sid, 'lite': LITE})
            await pg.wait_for_timeout(60)
            x0 = max(0, r['x'] - 110); y0 = max(0, r['y'] - 70)
            await pg.screenshot(path='/tmp/_t.png', clip={'x': x0, 'y': y0, 'width': 220, 'height': 300})
            tiles.append((sid, Image.open('/tmp/_t.png').copy(), r))
            print(sid, 'частиц следа максимум:', r['maxTrail'], 'face', round(r['face'], 2))
        w, h = tiles[0][1].size
        sheet = Image.new('RGB', (w * 6, h * 2), '#000')
        for i, (sid, im, r) in enumerate(tiles): sheet.paste(im, ((i % 6) * w, (i // 6) * h))
        sheet.save(OUT)
        if errors: print('ОШИБКИ:', errors[:10])
        await b.close()
asyncio.run(main())
