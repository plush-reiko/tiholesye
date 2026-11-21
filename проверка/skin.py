"""Лист одного-нескольких обликов крупно: python3 skin.py ezhik,sova out.png [scale]
Ряд на облик: цвет, силуэт, моргание, без заряда, взмах 1 / .75 / .5 / .25, лицом влево, игровой размер."""
import asyncio, base64, os, sys
from playwright.async_api import async_playwright
IDS, OUT = sys.argv[1].split(','), sys.argv[2]
SC = float(sys.argv[3]) if len(sys.argv) > 3 else 4
URL = os.environ.get('TL_URL', 'http://127.0.0.1:8765/index.html')
JS = r"""({ids, sc}) => {
  const T = window.__tl, A = T.Art;
  const S = [['цвет', {t: 0.873, wing: 1}], ['силуэт', {t: 0.873, wing: 1, sil: true}], ['моргает', {t: 0.873, wing: 1, blink: true}],
    ['без заряда', {t: 0.873, wing: 0}], ['взмах 1', {t: 0.873, wing: 1, flap: 1}], ['.75', {t: 0.873, wing: 1, flap: 0.75}],
    ['.5', {t: 0.873, wing: 1, flap: 0.5}], ['.25', {t: 0.873, wing: 1, flap: 0.25}], ['влево', {t: 0.873, wing: 1, face: -1}], ['t=2.1', {t: 2.1, wing: 1}]];
  const cw = 90 * sc, ch = 96 * sc, small = 46;
  const cv = document.createElement('canvas'); cv.width = cw * S.length + 200; cv.height = ch * ids.length; const x = cv.getContext('2d');
  x.fillStyle = '#141a52'; x.fillRect(0, 0, cv.width, cv.height);
  ids.forEach((id, r) => {
    const sk = T.SKINS.find((s) => s.id === id);
    S.forEach(([nm, a], k) => {
      const c2 = document.createElement('canvas'); c2.width = cw; c2.height = ch; const y = c2.getContext('2d');
      if (a.sil) { y.fillStyle = '#fff'; y.fillRect(0, 0, cw, ch); }
      y.save(); y.translate(cw / 2, ch - 14 * sc); y.scale(sc, sc); A.char(y, sk, a); y.restore();
      if (a.sil) { const c3 = document.createElement('canvas'); c3.width = cw; c3.height = ch; const z = c3.getContext('2d');
        z.translate(cw / 2, ch - 14 * sc); z.scale(sc, sc); A.char(z, sk, a); z.setTransform(1, 0, 0, 1, 0, 0);
        z.globalCompositeOperation = 'source-in'; z.fillStyle = '#000'; z.fillRect(0, 0, cw, ch); y.drawImage(c3, 0, 0); }
      x.drawImage(c2, k * cw, r * ch);
      x.fillStyle = a.sil ? '#000' : '#cfd4ff'; x.font = `${5 * sc}px sans-serif`; x.fillText(nm, k * cw + 4, r * ch + 7 * sc);
      x.strokeStyle = '#2a3270'; x.strokeRect(k * cw + 0.5, r * ch + 0.5, cw, ch);
    });
    // игровой размер: ~3 px на единицу (айфон), как в забеге
    x.save(); x.translate(cw * S.length + 100, r * ch + ch - 30); x.scale(3, 3); A.char(x, sk, {t: 0.873, wing: 1}); x.restore();
  });
  return cv.toDataURL('image/png');
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
        data = await pg.evaluate(JS, {'ids': IDS, 'sc': SC})
        open(OUT, 'wb').write(base64.b64decode(data.split(',')[1]))
        if errors: print('ОШИБКИ:', errors[:10])
        await b.close()
asyncio.run(main())
