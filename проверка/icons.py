"""Иконки «Тихолесья» функциями самой игры (canvas → PNG): python3 icons.py <папка-репозитория>
Ёжик на вершине пня, стволы ночного леса, светящиеся трутовики и светлячки. Всё важное — в центральных 80 % (maskable)."""
import asyncio, base64, os, sys
from playwright.async_api import async_playwright
REPO = sys.argv[1]
URL = os.environ.get('TL_URL', 'http://127.0.0.1:8765/index.html')
JS = r"""(S) => {
  const T = window.__tl, A = T.Art, Z0 = T.ZONES[0];
  const cv = document.createElement('canvas'); cv.width = cv.height = S; const c = cv.getContext('2d');
  const hx = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)), mix = (a, b, k) => { const p = hx(a), q = hx(b); return '#' + p.map((v, i) => Math.round(v + (q[i] - v) * k).toString(16).padStart(2, '0')).join(''); };
  const NEAR0 = mix(Z0.sky[0], '#000000', 0.3), WOOD = mix(NEAR0, Z0.stone, 0.48), WOOD_D = mix(NEAR0, Z0.stone, 0.2), WOOD_L = mix(NEAR0, Z0.stone, 0.78);
  const k = S / 116;                         // единиц мира на холст: иконка — 116 × 116 ед.
  c.setTransform(k, 0, 0, k, 0, 0);
  // небо и стволы: дальние светлее, ближний слева тёмный
  c.fillStyle = Z0.sky[1]; c.fillRect(0, 0, 116, 116);
  c.fillStyle = mix(Z0.sky[1], Z0.sky[2], 0.55); A.poly(c, [[50, -2], [66, -2], [67.4, 118], [48.6, 118]]); c.fill();
  c.fillStyle = mix(Z0.sky[1], Z0.sky[2], 0.3); A.poly(c, [[84, -2], [97, -2], [98.6, 118], [82.6, 118]]); c.fill();
  c.fillStyle = mix(Z0.sky[0], '#000000', 0.12); A.poly(c, [[-4, -2], [15.4, -2], [16.2, 40], [17.4, 118], [-4, 118]]); c.fill();
  // светлячки: ореол и точка, как в лесу
  const ff = (x, y, r) => { c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.75; c.drawImage(A.glow('#ffe3a0'), x - r * 4.6, y - r * 4.6, r * 9.2, r * 9.2); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1; c.fillStyle = '#fff6dc'; A.dot(c, x, y, r); };
  ff(90, 21, 1.9); ff(101.4, 53, 1.5); ff(27, 90, 1.7);
  // трутовики на ближнем стволе — светятся голубым
  const P = A.SHROOM[0], rr = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
  A.halo(c, 22, 40, 30, P[0], 0.22);
  A.bracket(c, 15.6, 37, 1, 15, P, rr); A.bracket(c, 15.8, 46.4, 1, 10.5, P, rr);
  // пень: бока чуть неровные, правая половина в тени, кора штрихами
  const L = [[28.6, 78], [27.4, 92], [26.2, 104], [25, 118]], R = [[87.4, 78], [88.6, 92], [89.8, 104], [91.4, 118]];
  const body = [[89, 76], [86, 70.4], [83.4, 74], [79, 71.6], [74.8, 75], [58, 74.4], [40, 75.4], [30, 74.6], [27, 77], ...L, ...R.slice().reverse()];
  A.poly(c, body); c.fillStyle = WOOD; c.fill();
  c.save(); c.clip();
  A.poly(c, [[62, 60], [120, 60], [120, 120], [60, 120]]); c.fillStyle = WOOD_D; c.fill();
  c.strokeStyle = WOOD_L; c.lineCap = 'round';
  for (const [x, y, l, w] of [[36, 86, 16, 0.9], [44, 96, 14, 0.8], [33, 102, 12, 0.8], [52, 90, 10, 0.7]]) { c.lineWidth = w; c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + 1, y + l * 0.5, x + 0.3, y + l); c.stroke(); }
  c.strokeStyle = WOOD; for (const [x, y, l, w] of [[70, 88, 14, 0.8], [78, 98, 12, 0.7]]) { c.lineWidth = w; c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + 1, y + l * 0.5, x + 0.3, y + l); c.stroke(); }
  c.restore();
  // вершина пня: моховая шапка игры (платформа home)
  A.setScale(k);
  const sp = A.plat('home', 66, 0, 1);
  c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.drawImage(sp.c, (58 - sp.ox) * k, (73 - sp.oy) * k, sp.w * k, sp.h * k); c.restore();
  // Ёжик смотрит вправо: мягкий ореол облика и сам облик крупно
  const sk = T.SKINS.find((s) => s.id === 'ezhik');
  c.globalCompositeOperation = 'lighter'; c.globalAlpha = 0.16; c.drawImage(A.glow(sk.glow), 60 - 24, 72 - 42, 48, 48); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1;
  c.save(); c.translate(60, 72.8); c.scale(0.84, 0.84); A.char(c, sk, { t: 0.873, wing: 1, face: 1 }); c.restore();
  // бумажное зерно, как у интерфейса
  c.setTransform(1, 0, 0, 1, 0, 0);
  const id = c.getImageData(0, 0, S, S), d = id.data; let s = 12345;
  for (let i = 0; i < d.length; i += 4) { s = (s * 16807) % 2147483647; const n = ((s / 2147483647) - 0.5) * 10; d[i] += n; d[i + 1] += n; d[i + 2] += n; }
  c.putImageData(id, 0, 0);
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
        for size in [512, 192, 180]:
            data = await pg.evaluate(JS, size)
            open(os.path.join(REPO, f'icon-{size}.png'), 'wb').write(base64.b64decode(data.split(',')[1]))
            print('icon', size)
        if errors: print('ОШИБКИ:', errors[:10])
        await b.close()
asyncio.run(main())
