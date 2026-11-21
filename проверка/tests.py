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
      for (let k = 0; k < 40; k++) T.genUpTo(g.startY + 70000);
      const ps = g.plats;
      for (const p of ps) if (p.type === 'puff') { puffs++; w.add(p.w); if (!ps.some((q) => q.type === 'static' && Math.abs(q.baseY - p.baseY) < 12)) alone++; }
      return { puffs, alone, widths: [...w] }; }''')
    check('рядом с каждым листом есть обычная кочка, ширина листа 66', g['puffs'] > 20 and g['alone'] == 0 and g['widths'] == [66], str(g))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


BEAST_SETUP = r"""(kind) => { const T = window.__tl, g = T.game, P = T.P;
  g.zen = false; T.startRun(true); g.reveal = 1;
  const keep = g.plats.filter((q) => q.type === 'ground'); g.plats.length = 0; g.plats.push(...keep); g.beasts.length = 0; g.coins.length = 0;
  const y = P.y + 500; g.camY = y - 400;
  const host = { id: 7e6, type: 'static', x: 200, top: y - 11, prevTop: y - 11, baseY: y - 11, w: 90, zi: 0, v: 0, dust: '#fff', sq: 0, sqv: 0, dead: false, item: null, t: 0, vx: 0, minX: 0, maxX: 0, amp: 0, om: 0, on: true, alpha: 1, fall: 0, vy: 0 };
  if (kind === 'beetle') g.plats.push(host);
  let s = 1; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const b = T.makeBeast(kind, host, y - 70, r); g.beasts.push(b);
  if (kind === 'owl') { b.state = 'dive'; b.st = 0; b.p0 = b.p1 = b.p2 = [b.x, b.y]; }
  if (kind === 'spider') { b.A = 0.001; }
  T.update(1 / 120);
  P.inv = 0; P.shield = false; P.fly = null; P.flow = 0; P.mult = 1;
  window.__b = b; return { x: b.x, y: b.y }; }"""

HIT = r"""([mode, kind]) => { const T = window.__tl, g = T.game, P = T.P, b = window.__b, s0 = T.save.stats.stomps;
  const step = () => { T.update(1 / 120); g.camY = b.y - 400; };
  if (kind === 'owl') { b.p0 = b.p1 = b.p2 = [b.x, b.y]; }
  if (mode === 'top') { P.x = b.x; P.y = b.y + 9; P.vy = -300; }
  if (mode === 'side') { P.x = b.x + 15; P.y = b.y - 22; P.vy = 250; }
  if (mode === 'bubble') { P.x = b.x + 15; P.y = b.y - 22; P.vy = 250; P.shield = true; }
  if (mode === 'comet') { P.x = b.x; P.y = b.y - 20; P.fly = { kind: 'comet', t: 1, max: 1, v: 0 }; }
  if (mode === 'tent') { P.x = b.x + 4; P.y = b.y - 10 - 30 - 20; P.vy = 250; }
  if (kind === 'beetle') { b.pause = 9; }
  let vyMax = -1e9, vyMin = 1e9;
  for (let i = 0; i < 3; i++) { step(); vyMax = Math.max(vyMax, P.vy); vyMin = Math.min(vyMin, P.vy); }
  return { dead: b.dead, how: b.how, vyMax, vyMin, inv: P.inv, shield: P.shield, stomps: T.save.stats.stomps - s0 }; }"""

GEN_SHARES = r"""() => { const T = window.__tl, g = T.game, Z = T.ZONES; const cnt = {}, want = {}, bad = []; let owlPairs = 0;
  for (let seed = 1; seed <= 40; seed++) {
    g.seed = seed * 7919; g.zen = false; T.startRun(true); for (let k = 0; k < 40; k++) T.genUpTo(g.startY + 7000 * 10);
    const owls = [];
    for (const b of g.beasts) {
      const h = (b.y - g.startY) / 10; let zi = 0; for (let k = 1; k < Z.length; k++) if (h >= Z[k].from) zi = k;
      (cnt[zi] = cnt[zi] || {})[b.kind] = (cnt[zi][b.kind] || 0) + 1; (want[zi] = want[zi] || {})[b.want] = (want[zi][b.want] || 0) + 1;
      if (b.kind === 'beetle' && !(b.hp.type === 'static' && b.hp.w >= 66 && g.plats.includes(b.hp))) bad.push('жук без кочки');
      if (b.kind === 'owl') owls.push(b.y);
      if (h + 15 < T.BEAST_FROM[b.kind]) bad.push(b.kind + ' ниже своей высоты ' + Math.round(h));
    }
    owls.sort((a, c) => a - c); for (let i = 1; i < owls.length; i++) if (owls[i] - owls[i - 1] < T.view.H) owlPairs++;
  }
  g.seed = 0; return { cnt, want, bad: bad.slice(0, 5), owlPairs }; }"""

MOTION = r"""() => { const T = window.__tl, g = T.game, P = T.P; const out = {};
  g.zen = false; T.startRun(true); const keep = g.plats.filter((q) => q.type === 'ground'); g.plats.length = 0; g.plats.push(...keep); g.beasts.length = 0;
  const y = P.y + 600; let s = 3; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const host = { id: 7e6 + 1, type: 'static', x: 150, top: y, prevTop: y, baseY: y, w: 84, zi: 0, v: 0, dust: '#fff', sq: 0, sqv: 0, dead: false, item: null, t: 0, vx: 0, minX: 0, maxX: 0, amp: 0, om: 0, on: true, alpha: 1, fall: 0, vy: 0 };
  g.plats.push(host);
  const sp = T.makeBeast('spider', host, y, r), bt = T.makeBeast('beetle', host, y, r); g.beasts.push(sp, bt);
  let dy = 0, dx = 0, umax = 0; const xs = [];
  P.fly = { kind: 'dandelion', t: 99, max: 99, v: 0 };
  for (let i = 0; i < 1200; i++) { P.x = 380; P.y = y - 300; g.camY = y - 300; T.update(1 / 60); dy = Math.max(dy, Math.abs(sp.y - sp.y0)); dx = Math.max(dx, Math.abs(sp.x - sp.x0)); umax = Math.max(umax, Math.abs(bt.u)); xs.push(bt.x); }
  out.spider = { dy, A: sp.A, dx }; out.beetle = { umax, lim: host.w / 2 - 10, minX: Math.min(...xs), maxX: Math.max(...xs), alive: g.beasts.includes(bt) };
  g.beasts.length = 0;
  const ow = T.makeBeast('owl', host, y, r); g.beasts.push(ow);
  let tWarn = -1, tDive = -1, t = 0;
  for (let i = 0; i < 400 && tDive < 0; i++) { P.x = 200; P.y = ow.perch - 250; g.camY = ow.perch - 500; T.update(1 / 60); t += 1 / 60; if (ow.state === 'warn' && tWarn < 0) tWarn = t; if (ow.state === 'dive' && tDive < 0) tDive = t; }
  out.owl = { tWarn, tDive, gap: tDive - tWarn };
  P.fly = null;
  g.zen = true; T.startRun(true); for (let k = 0; k < 40; k++) T.genUpTo(g.startY + 70000); out.zen = g.beasts.length; g.zen = false;
  return out; }"""


async def t_beasts(b):
    print('Ворчуны')
    ctx, pg = await page(b)
    r = await pg.evaluate(GEN_SHARES)
    TABLE = {1: {'burr': .65, 'spider': .35}, 2: {'burr': .30, 'spider': .25, 'beetle': .45}, 3: {'burr': .25, 'spider': .15, 'beetle': .20, 'owl': .40}, 4: {'burr': .20, 'beetle': .10, 'owl': .30, 'jelly': .40}}
    for zi, tab in TABLE.items():
        w = r['want'].get(str(zi), {}); n = sum(w.values()) or 1
        exp = dict(tab)
        if zi == 1:                       # паук только с 1 100 м: в 900–1 100 выпадает один репейник
            exp = {'spider': tab['spider'] * 500 / 700, 'burr': 1 - tab['spider'] * 500 / 700}
        sh = {k: w.get(k, 0) / n for k in exp}
        dev = max(abs(sh[k] - exp[k]) for k in exp)
        c = r['cnt'].get(str(zi), {}); nc = sum(c.values()) or 1
        check(f'зона {zi}: выпавшие виды совпадают с таблицей 9.2 (±0,1)', dev <= 0.1 and n > 30,
              f'выпало {dict((k, round(v, 2)) for k, v in sh.items())}, n={n}; появилось {dict((k, round(v / nc, 2)) for k, v in c.items())}')
    check('жуки только на своей кочке, все виды не ниже своей высоты', not r['bad'], str(r['bad']))
    check('два сыча не оказываются на одном экране', r['owlPairs'] == 0, str(r['owlPairs']))
    VJ = 850
    for kind in ['burr', 'spider', 'beetle', 'owl', 'jelly']:
        res = {}
        for mode in ['top', 'side', 'bubble', 'comet'] + (['tent'] if kind == 'jelly' else []):
            await pg.evaluate(BEAST_SETUP, kind)
            res[mode] = await pg.evaluate(HIT, [mode, kind])
        t = res['top']
        if kind == 'jelly':
            check('jelly: прыжок на колокол — супер-прыжок (VJ·1,75), засчитан как сбитый ворчун', t['dead'] and t['how'] == 'stomp' and t['vyMax'] > VJ * 1.7 and t['stomps'] == 1, str(t))
        else:
            check(f'{kind}: прыжок сверху побеждает и подбрасывает', t['dead'] and t['how'] == 'stomp' and t['vyMax'] > VJ * 1.0 and t['stomps'] == 1, str(t))
        sd = res['side']
        check(f'{kind}: касание сбоку сталкивает вниз', (not sd['dead']) and sd['vyMin'] <= -420 and sd['inv'] > 0.9, str(sd))
        bb = res['bubble']
        check(f'{kind}: с пузырём — пузырь лопается, ворчун побеждён', bb['dead'] and bb['how'] == 'bubble' and not bb['shield'] and bb['inv'] > 0.6, str(bb))
        cm = res['comet']
        check(f'{kind}: в полёте кометы — побеждён', cm['dead'] and cm['how'] == 'fly', str(cm))
        if kind == 'jelly':
            tn = res['tent']
            check('jelly: щупальца жалят', (not tn['dead']) and tn['vyMin'] <= -420, str(tn))
    m = await pg.evaluate(MOTION)
    sp, bt, ow = m['spider'], m['beetle'], m['owl']
    check('паук ходит в пределах амплитуды (±5 по x)', sp['dy'] <= sp['A'] + 0.01 and sp['dx'] <= 5.01, str(sp))
    check('жук не уходит со своей кочки', bt['umax'] <= bt['lim'] + 0.01 and bt['alive'], str(bt))
    check('сыч предупреждает не меньше чем за 0,8 с', ow['tWarn'] >= 0 and ow['gap'] >= 0.79, str(ow))
    check('в дзене ворчунов нет', m['zen'] == 0, str(m['zen']))
    sf = await pg.evaluate('() => { const T = window.__tl; T.Snd.unlock(); return T.Snd.selfTest(); }')
    check('все звуки синтезируются без ошибок (selfTest)', not sf['bad'], str(sf))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


TESTS = [('gift', t_gift), ('coins', t_coins), ('ghost', t_ghost), ('leaf', t_leaf), ('beasts', t_beasts)]


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
