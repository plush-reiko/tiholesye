"""Автопроверки «Тихолесья» (раздел 13.2 ТЗ 21.11).

Запуск: python3 -m http.server 8765 --bind 127.0.0.1 --directory <папка репозитория>   # в отдельном окне
        python3 tests.py [только_эти_разделы через запятую]
Нужен Playwright: pip install playwright && python3 -m playwright install chromium
Каждая проверка печатает «ок» или «ОШИБКА» с пояснением; в конце — итог. Ошибки консоли браузера считаются провалом.
"""
import asyncio, base64, json, os, sys
from playwright.async_api import async_playwright

URL = os.environ.get('TL_URL', 'http://127.0.0.1:8765/index.html')
OLD_URL = os.environ.get('TL_OLD_URL', '')           # старая версия игры (для кода переноса v1), если раздаётся
ONLY = set(sys.argv[1].split(',')) if len(sys.argv) > 1 else None
RES = []


def check(name, ok, info=''):
    RES.append((name, bool(ok), info))
    print(('  ок      ' if ok else '  ОШИБКА  ') + name + (f' — {info}' if info else ''))


async def page(b, init=None, storage=None):
    ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
    if init: await ctx.add_init_script(init)
    if storage is not None:
        await ctx.add_init_script('(() => { try { if (!sessionStorage.getItem("tl_seeded")) { localStorage.setItem("tiholesye.save.v1", %s); sessionStorage.setItem("tl_seeded", "1"); } } catch (e) {} })()' % json.dumps(storage))
    pg = await ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and pg.errors.append(m.text))
    await pg.goto(URL)
    await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
    await pg.wait_for_timeout(300)
    return ctx, pg

SHIFT_DAY = '''(() => { const _D = Date, sh = 86400000;
  class FD extends _D { constructor(...a) { if (!a.length) super(_D.now() + sh); else super(...a); } static now() { return _D.now() + sh; } }
  window.Date = FD; })()'''


async def t_gift(b):
    print('Подарок дня')
    ctx, pg = await page(b)
    vis = await pg.evaluate('() => !document.getElementById("bGift").hidden')
    check('пустое сохранение: меню без ошибок, кнопка подарка видна', vis and not pg.errors, '; '.join(pg.errors[:3]))
    c0 = await pg.evaluate('() => window.__tl.save.coins')
    await pg.click('#bGift')
    try: await pg.click('#bGift', timeout=300, force=True)
    except Exception: pass
    await pg.evaluate('() => document.getElementById("bGift").click()')
    await pg.wait_for_timeout(1500)
    c1 = await pg.evaluate('() => window.__tl.save.coins')
    check('нажатие даёт +100, двойное — не 200', c1 - c0 == 100, f'было {c0}, стало {c1}')
    hid = await pg.evaluate('() => document.getElementById("bGift").hidden')
    toast = await pg.evaluate('() => [...document.querySelectorAll("#toasts .toast")].map((t) => t.textContent).join(" | ")')
    check('кнопка исчезла, есть тост «Подарок леса +100»', hid and 'Подарок леса' in toast and '100' in toast, toast)
    left = await pg.evaluate('() => document.querySelectorAll(".flyic").length')
    shown = await pg.evaluate('() => document.getElementById("mCoins").textContent.replace(/\\s/g, "")')
    check('светлячки долетели и убраны, счётчик показывает новое число', left == 0 and shown == str(c1), f'осталось {left}, счётчик {shown}')
    await pg.reload(); await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"'); await pg.wait_for_timeout(300)
    hid2 = await pg.evaluate('() => document.getElementById("bGift").hidden')
    check('после перезагрузки кнопки нет', hid2)
    # сброс прогресса сохраняет отметку дня
    await pg.click('#bSet'); await pg.wait_for_timeout(150); await pg.click('#bReset'); await pg.click('#bReset'); await pg.wait_for_timeout(300)
    hid3 = await pg.evaluate('() => document.getElementById("bGift").hidden')
    check('«Сбросить прогресс» не даёт второй подарок', hid3)
    errs = list(pg.errors)
    await ctx.close()
    # тот же день + 1: подменяем Date и переносим сохранение
    ctx2 = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
    await ctx2.add_init_script(SHIFT_DAY)
    pg2 = await ctx2.new_page(); pg2.errors = []
    pg2.on('pageerror', lambda e: pg2.errors.append(str(e)))
    await pg2.goto(URL); await pg2.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
    today = await pg2.evaluate('() => { const d = new Date(Date.now() - 86400000); return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`; }')
    await pg2.evaluate('(k) => { const s = window.__tl.save; s.gift = k; window.__tl.persist(); }', today)
    await pg2.reload(); await pg2.wait_for_function('window.__tl && window.__tl.game.state === "menu"'); await pg2.wait_for_timeout(300)
    vis2 = await pg2.evaluate('() => !document.getElementById("bGift").hidden')
    check('с датой +1 день кнопка снова есть', vis2)
    check('ошибок в консоли нет', not errs and not pg2.errors, '; '.join((errs + pg2.errors)[:3]))
    await ctx2.close()


async def t_coins(b):
    print('Светлячки без стаек')
    ctx, pg = await page(b)
    r = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P;
      g.zen = false; T.startRun(true); g.reveal = 1;
      P.flow = 14; P.mult = 3;
      g.coins.length = 0; g.coins.push({ x: P.x, y: P.y + 20, ph: 1, big: false, pull: false, dead: false });
      const c0 = T.run.coins; P.vy = 0; T.update(1 / 60);
      return { got: T.run.coins - c0, swarm: 'swarm' in g, mult: document.getElementById('hMult').textContent, sparks: g.parts.filter((q) => q.k === 'g').length }; }''')
    check('при ×3 поимка одного светлячка даёт +3', r['got'] == 3, str(r))
    check('стаек больше нет (game.swarm удалён)', not r['swarm'])
    check('вспышка из 3 искр, «×3» у счётчика', r['sparks'] == 3 and r['mult'] == '×3', str(r))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


async def t_ghost(b):
    print('Призрачная кочка')
    ctx, pg = await page(b)
    r = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P;
      g.zen = false; T.startRun(true);
      const keep = g.plats.filter((q) => q.type === 'ground'); g.plats.length = 0; g.plats.push(...keep);     // только земля: ничто не перехватит прыжок
      const y = P.y + 400; g.camY = y - 300; const mk = (top) => { const pl = { id: 9e6 + Math.random(), type: 'fake', x: P.x, top, prevTop: top, baseY: top, w: 78, zi: 0, v: 1, dust: '#dde3ff', sq: 0, sqv: 0, dead: false, item: null, t: 0, vx: 0, minX: 0, maxX: 0, amp: 0, om: 0, on: true, alpha: 1, fall: 0, vy: 0 }; g.plats.push(pl); return pl; };
      // сверху: герой падает на призрачную кочку
      const a = mk(y); P.y = y + 6; P.vy = -300; P.fly = null; T.update(1 / 30);
      const fromAbove = { melted: !!a.fall, passed: P.vy < 0 };
      // снизу: герой пролетает сквозь
      const b2 = mk(P.y + 60); P.vy = 900; for (let i = 0; i < 10; i++) { T.update(1 / 60); g.camY = y - 300; }
      return { fromAbove, through: !!b2.fall }; }''')
    check('не держит и тает от касания сверху', r['fromAbove']['melted'] and r['fromAbove']['passed'], str(r))
    check('тает, когда пролетаешь сквозь', r['through'], str(r))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


async def t_leaf(b):
    print('Сухой лист')
    ctx, pg = await page(b)
    r = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P, s = T.save;
      g.zen = false; T.startRun(true);
      const keep = g.plats.filter((q) => q.type === 'ground'); g.plats.length = 0; g.plats.push(...keep);
      s.missions = [{ type: 'puffs', n: 10, rw: 40, p: 0, done: false }];
      const y = P.y + 300, pl = { id: 9e6 + 7, type: 'puff', x: 200, top: y, prevTop: y, baseY: y, w: 66, zi: 0, v: 1, dust: '#c9c0d8', sq: 0, sqv: 0, dead: false, item: null, t: 0, vx: 0, minX: 0, maxX: 0, amp: 0, om: 0, on: true, alpha: 1, fall: 0, vy: 0 };
      g.plats.push(pl); P.x = 200; P.y = y + 2; P.vy = -300; P.fly = null; g.camY = y - 300; T.update(1 / 60);
      const held = P.vy > 700 && !!pl.fall;
      const xs = [], tops = []; let n = 0;
      P.fly = { kind: 'dandelion', t: 99, max: 99, v: 0 }; P.y = y + 100; g.camY = P.y - T.view.H * 0.44;     // герой зависает над листом, камера стоит
      while (!pl.dead && n < 400) { T.update(1 / 60); n++; xs.push(pl.x); tops.push(pl.top); P.y = y + 100; g.camY = P.y - T.view.H * 0.44; }
      return { held, dead: pl.dead, secs: n / 60, minX: Math.min(...xs), maxX: Math.max(...xs), drop: y - Math.min(...tops), mission: s.missions[0] ? s.missions[0].p : -1, stat: s.stats.puffs }; }''')
    check('держит один прыжок и сразу срывается', r['held'], str(r))
    check('падает с покачиванием и исчезает за ~1,6 с', r['dead'] and 1.5 <= r['secs'] <= 1.75 and r['maxX'] - r['minX'] > 25 and r['drop'] > 80, str(r))
    check('задание «Сорви N сухих листьев» и статистика считают', r['mission'] == 1 and r['stat'] >= 1, str(r))
    g = await pg.evaluate('''() => { const T = window.__tl, g = T.game; g.seed = 4242; g.zen = true; T.startRun(true);
      let puffs = 0, alone = 0, w = new Set();
      T.genUpTo(g.startY + 70000);
      const ps = g.plats;
      for (const p of ps) if (p.type === 'puff') { puffs++; w.add(p.w); if (!ps.some((q) => q.type === 'static' && Math.abs(q.baseY - p.baseY) < 12)) alone++; }
      return { puffs, alone, widths: [...w] }; }''')
    check('рядом с каждым листом есть обычная кочка, ширина листа 66', g['puffs'] > 20 and g['alone'] == 0 and g['widths'] == [66], str(g))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


TESTS = [('gift', t_gift), ('coins', t_coins), ('ghost', t_ghost), ('leaf', t_leaf)]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get('CHROME') or None)
        for key, fn in TESTS:
            if ONLY and key not in ONLY: continue
            try: await fn(b)
            except Exception as e: check(f'{key}: исключение', False, str(e)[:300])
        await b.close()
    bad = [r for r in RES if not r[1]]
    print(f'\nИтог: {len(RES) - len(bad)} из {len(RES)} проверок прошли' + ('' if not bad else ', провалены: ' + ', '.join(r[0] for r in bad)))
    sys.exit(1 if bad else 0)

asyncio.run(main())
