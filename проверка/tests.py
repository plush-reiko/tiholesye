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


# Код переноса из версии до 21.11 (index.html из git, коммит 23571e5): облики svetik, gribok, kot, zvezda, надет kot;
# следы none, sparks, aurora; 1 000 светлячков, рекорд 500 м, 5 заданий, музыка выключена, управление «края», крылья 2.
# Сделан самой старой игрой: save → 'TL1.' + base64(JSON). Возврат за него: kot 750 + zvezda 3 900 + sparks 100 + aurora 1 800 = 6 550.
OLD_CODE = "TL1.eyJ2IjoxLCJjb2lucyI6MTAwMCwiYmVzdCI6NTAwLCJiZXN0WmVuIjowLCJydW5zIjo3LCJ0b3RhbENvaW5zIjoyNDAwLCJ0b3RhbEhlaWdodCI6MCwic2tpbiI6ImtvdCIsInRyYWlsIjoiYXVyb3JhIiwic2tpbnMiOlsic3ZldGlrIiwiZ3JpYm9rIiwia290IiwienZlemRhIl0sInRyYWlscyI6WyJub25lIiwic3BhcmtzIiwiYXVyb3JhIl0sInVwIjp7IndpbmdzIjoyLCJkYW5kZWxpb24iOjAsImNvbWV0IjowLCJtYWduZXQiOjAsImx1Y2siOjAsImJ1YmJsZSI6MH0sIm1pc3Npb25zIjpbeyJ0eXBlIjoiaGVpZ2h0IiwibiI6MzAwLCJydyI6NTAsInAiOjAsImRvbmUiOmZhbHNlfSx7InR5cGUiOiJjb2luc1J1biIsIm4iOjIwLCJydyI6MzUsInAiOjAsImRvbmUiOmZhbHNlfSx7InR5cGUiOiJ3aW5ncyIsIm4iOjUsInJ3IjozNSwicCI6MCwiZG9uZSI6ZmFsc2V9XSwibVRpZXIiOnt9LCJtRG9uZSI6NSwic3RhdHMiOnsic3RvbXBzIjowLCJib3VuY3kiOjAsInB1ZmZzIjowLCJmbGlnaHRzIjowLCJ3aW5ncyI6MCwibWF4TXVsdCI6MX0sInNldCI6eyJtdXNpYyI6ZmFsc2UsInNmeCI6dHJ1ZSwiY29udHJvbCI6InNpZGVzIiwiZngiOiJoaWdoIiwibXVzaWNWb2wiOjEsInNmeFZvbCI6MX0sInR1dCI6ZmFsc2UsInplbiI6ZmFsc2UsImdpZnQiOiIyMDI2LTExLTIxIiwibXVsdFRpcCI6ZmFsc2UsInJlY2VudCI6W10sInBsYXlUaW1lIjowfQ=="
OLD_JSON = "{\"v\":1,\"coins\":1000,\"best\":500,\"bestZen\":0,\"runs\":7,\"totalCoins\":2400,\"totalHeight\":0,\"skin\":\"kot\",\"trail\":\"aurora\",\"skins\":[\"svetik\",\"gribok\",\"kot\",\"zvezda\"],\"trails\":[\"none\",\"sparks\",\"aurora\"],\"up\":{\"wings\":2,\"dandelion\":0,\"comet\":0,\"magnet\":0,\"luck\":0,\"bubble\":0},\"missions\":[{\"type\":\"height\",\"n\":300,\"rw\":50,\"p\":0,\"done\":false},{\"type\":\"coinsRun\",\"n\":20,\"rw\":35,\"p\":0,\"done\":false},{\"type\":\"wings\",\"n\":5,\"rw\":35,\"p\":0,\"done\":false}],\"mTier\":{},\"mDone\":5,\"stats\":{\"stomps\":0,\"bouncy\":0,\"puffs\":0,\"flights\":0,\"wings\":0,\"maxMult\":1},\"set\":{\"music\":false,\"sfx\":true,\"control\":\"sides\",\"fx\":\"high\",\"musicVol\":1,\"sfxVol\":1},\"tut\":false,\"zen\":false,\"gift\":\"2026-11-21\",\"multTip\":false,\"recent\":[],\"playTime\":0}"
OLD_REFUND = 6550


async def menu(pg):
    await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"'); await pg.wait_for_timeout(300)


async def toasts(pg):
    return await pg.evaluate('() => [...document.querySelectorAll("#toasts .toast")].map((t) => t.textContent.replace(/\\s+/g, " ")).join(" | ")')


def digits(s):
    return ''.join(ch for ch in s if ch.isdigit())


async def t_migration(b):
    print('Миграция сохранений v1 → v2')
    old = json.loads(OLD_JSON)
    # 1. старое сохранение в хранилище
    ctx, pg = await page(b, storage=OLD_JSON)
    s = await pg.evaluate('() => window.__tl.save')
    tt = await toasts(pg)
    check('после загрузки: облики ezhik и mukhomor, надет ezhik', s['skins'] == ['ezhik', 'mukhomor'] and s['skin'] == 'ezhik', f"{s['skins']} / {s['skin']}")
    check('светлячков больше на 6 550', s['coins'] == old['coins'] + OLD_REFUND, f"было {old['coins']}, стало {s['coins']}")
    check('тост о возврате с суммой', 'Облики обновились' in tt and '6550' in digits(tt), tt)
    check('схема v2, без следов, refund обнулён, прочее на месте', s['v'] == 2 and 'trail' not in s and 'trails' not in s and s['refund'] == 0
          and s['best'] == old['best'] and s['mDone'] == old['mDone'] and s['up']['wings'] == 2 and s['set']['music'] is False and s['set']['control'] == 'sides',
          json.dumps({k: s.get(k) for k in ['v', 'refund', 'best', 'mDone']}))
    stored = await pg.evaluate('() => JSON.parse(localStorage.getItem("tiholesye.save.v1"))')
    check('в хранилище уже v2 с refund 0', stored['v'] == 2 and stored['refund'] == 0 and stored['coins'] == s['coins'])
    await pg.reload(); await menu(pg)
    s2 = await pg.evaluate('() => window.__tl.save'); tt2 = await toasts(pg)
    check('повторная загрузка не начисляет и не показывает тост', s2['coins'] == s['coins'] and 'Облики обновились' not in tt2, f"{s2['coins']} {tt2}")
    errs = list(pg.errors); await ctx.close()
    # 2. код переноса из старой версии — в новую, через поле в настройках
    ctx, pg = await page(b)
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('(code) => { document.getElementById("saveIn").value = code; }', OLD_CODE)
    await pg.evaluate('() => document.getElementById("bImport").click()'); await pg.wait_for_timeout(400)
    s3 = await pg.evaluate('() => window.__tl.save'); tt3 = await toasts(pg)
    check('код TL1. старой версии загружается: облики, светлячки с возвратом, тост', s3['skins'] == ['ezhik', 'mukhomor'] and s3['coins'] == old['coins'] + OLD_REFUND and 'Облики обновились' in tt3,
          f"{s3['skins']} {s3['coins']} | {tt3}")
    code2 = await pg.evaluate('() => window.__tl.exportCode()')
    data2 = await pg.evaluate('(c) => JSON.parse(decodeURIComponent(escape(atob(c.slice(4)))))', code2)
    check('новый код: префикс TL1. и v 2', code2.startswith('TL1.') and data2['v'] == 2)
    ok = await pg.evaluate('(c) => window.__tl.importCode(c)', code2)
    s4 = await pg.evaluate('() => window.__tl.save')
    check('код v2 загружается обратно без второго возврата', ok and s4['coins'] == s3['coins'] and s4['skins'] == s3['skins'], f"{s4['coins']}")
    errs += pg.errors; await ctx.close()
    # 3. рекорд 3 200 м и 12 заданий: рысь и светлячок сразу после загрузки
    rich = dict(old, best=3200, mDone=12)
    ctx, pg = await page(b, storage=json.dumps(rich))
    s5 = await pg.evaluate('() => window.__tl.save'); tt5 = await toasts(pg)
    check('рекорд 3 200 м: рысь сразу; 12 заданий: светлячок сразу', 'rys' in s5['skins'] and 'svetlyachok' in s5['skins'] and 'Рысь' in tt5, f"{s5['skins']} | {tt5}")
    # 4. сброс прогресса: чистое v2, настройки и отметка подарка остаются
    await pg.evaluate('() => { const s = window.__tl.save; s.gift = "2026-11-21"; s.set.sfx = false; window.__tl.persist(); }')
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('() => { const b = document.getElementById("bReset"); b.click(); b.click(); }'); await pg.wait_for_timeout(300)
    s6 = await pg.evaluate('() => window.__tl.save')
    check('«Сбросить прогресс»: v2, только ёжик, 0 светлячков; настройки и подарок на месте', s6['v'] == 2 and s6['skins'] == ['ezhik'] and s6['coins'] == 0
          and s6['set']['sfx'] is False and s6['set']['music'] is False and s6['gift'] == '2026-11-21', json.dumps({k: s6.get(k) for k in ['v', 'skins', 'coins', 'gift']}))
    errs += pg.errors; await ctx.close()
    # 5. если раздаётся старая версия (TL_OLD_URL): свежий код прямо из неё
    if OLD_URL:
        ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
        po = await ctx.new_page(); await po.goto(OLD_URL); await po.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
        code_old = await po.evaluate('''() => { const s = window.__tl.save; s.coins = 77; s.skins = ['svetik', 'lis', 'sova', 'kaplya', 'kometa']; s.skin = 'sova'; s.trails = ['none', 'notes']; s.trail = 'notes';
          return 'TL1.' + btoa(unescape(encodeURIComponent(JSON.stringify(s)))); }''')
        await ctx.close()
        ctx, pg = await page(b)
        ok = await pg.evaluate('(c) => window.__tl.importCode(c)', code_old)
        await pg.evaluate('() => window.__tl.afterLoad()')
        s7 = await pg.evaluate('() => window.__tl.save')
        check('свежий код из старой версии: лис и совёнок остались, капля → 300, ноты → 800, за комету 0',
              ok and s7['skins'] == ['ezhik', 'lis', 'sova'] and s7['skin'] == 'sova' and s7['coins'] == 77 + 300 + 800, f"{s7['skins']} {s7['skin']} {s7['coins']}")
        errs += pg.errors; await ctx.close()
    check('ошибок в консоли нет', not errs, '; '.join(errs[:3]))


async def t_skins(b):
    print('Облики, взмахи, следы, лавка')
    ctx, pg = await page(b)
    sh = await pg.evaluate('''() => { document.getElementById('bShop').click();
      const tabs = [...document.querySelectorAll('#shopTabs button')].map((x) => x.textContent.trim());
      const cards = document.querySelectorAll('#shopBody .card').length, trail = document.getElementById('bbTrail').textContent;
      return { tabs, cards, trail, cur: window.__tl.save.skin }; }''')
    check('пустое сохранение: надет Ёжик; в лавке вкладки «Облики» и «Усиления», 12 карточек, «След: листики»',
          sh['cur'] == 'ezhik' and sh['tabs'] == ['Облики', 'Усиления'] and sh['cards'] == 12 and sh['trail'] == 'След: листики', str(sh))
    # каждый покупается (или открывается) и надевается через лавку
    bought = await pg.evaluate('''() => { const T = window.__tl, s = T.save, out = [];
      s.coins = 99999;
      for (const sk of T.SKINS) {
        if (sk.unlock) { if (sk.unlock.type === 'height') s.best = Math.max(s.best, sk.unlock.n); else s.mDone = Math.max(s.mDone, sk.unlock.n); T.checkUnlocks(0); }
        const i = T.SKINS.indexOf(sk);
        document.querySelectorAll('#shopBody .card')[i].click();
        const btn = document.getElementById('bbBtn'); if (!btn.hidden && !btn.disabled) btn.click();
        if (s.skin !== sk.id) document.querySelectorAll('#shopBody .card')[i].click();
        out.push([sk.id, s.skins.includes(sk.id), s.skin === sk.id, document.getElementById('bbTrail').textContent, sk.trailName]);
      }
      return out; }''')
    bad = [x for x in bought if not (x[1] and x[2] and x[3] == 'След: ' + x[4])]
    check('каждый облик покупается/открывается и надевается, у каждого строка «След: …»', not bad, str(bad or [x[3] for x in bought]))
    spent = await pg.evaluate('() => 99999 - window.__tl.save.coins')
    check('потрачено ровно по ценам таблицы 10.3', spent == 150 + 400 + 700 + 1000 + 1300 + 1700 + 2100 + 2600 + 3200, str(spent))
    # 10 с забега на каждом: взмахи, след не больше 40 частиц
    r = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P, s = T.save, out = {};
      document.getElementById('shop').hidden = true;
      for (const sk of T.SKINS) {
        s.skin = sk.id; g.zen = true; T.startRun(true);
        let maxTrail = 0, flapSeen = 0, emitted = 0; const seen = new Set();
        for (let i = 0; i < 600; i++) {
          if (P.vy < -150 && P.y < T.run.maxY - 60) P.vy = 850;                // бот-пружина: не даём упасть
          if (i % 90 === 10) { s.up.wings = 3; P.wing = 1; T.flap(); }
          T.update(1 / 60); if (i % 2 === 0) T.render();
          let n = 0; for (const q of g.parts) if (q.trail) { n++; if (!seen.has(q)) { seen.add(q); emitted++; } }
          maxTrail = Math.max(maxTrail, n); if (P.flap > 0) flapSeen++;
        }
        out[sk.id] = { maxTrail, flapSeen, emitted, dash: sk.trail.k === 'dash' ? P.hist.length : -1 };
      }
      return out; }''')
    over = {k: v for k, v in r.items() if v['maxTrail'] > 40}
    check('10 с забега на каждом облике без ошибок', not pg.errors, '; '.join(pg.errors[:3]))
    check('след вылетает у каждого (у Светлячка — путь для пунктира)', all((v['emitted'] > 5) if v['dash'] < 0 else v['dash'] > 10 for v in r.values()),
          str({k: (v['emitted'], v['dash']) for k, v in r.items()}))
    check('живых частиц следа не больше 40', not over, str(over or {k: v['maxTrail'] for k, v in r.items()}))
    check('взмах проигрывается у каждого', all(v['flapSeen'] > 4 for v in r.values()), str({k: v['flapSeen'] for k, v in r.items()}))
    # нагрузка: выпуск следа без пауз упирается в 40
    st = await pg.evaluate('''() => { const T = window.__tl, g = T.game; T.save.skin = 'mukhomor'; T.startRun(true); g.parts.length = 0;
      for (let i = 0; i < 200; i++) T.emitTrail(0.5); return g.parts.filter((q) => q.trail).length; }''')
    check('при сплошном выпуске частиц следа не больше 40', st <= 40, str(st))
    fk = await pg.evaluate('() => window.__tl.SKINS.map((s) => s.flapK)')
    check('длительность взмаха задана у каждого облика и не одна на всех', all(isinstance(x, (int, float)) and x > 0 for x in fk) and len(set(fk)) >= 6, str(fk))
    # разворот: смена направления за ~0,1 с
    fc = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P, c = T.ctl; T.save.skin = 'lis'; g.zen = true; T.startRun(true);
      const f = []; c.keyL = true; for (let i = 0; i < 12; i++) { if (P.vy < -150) P.vy = 850; T.update(1 / 60); f.push(+P.face.toFixed(2)); }
      c.keyL = false; c.keyR = true; for (let i = 0; i < 12; i++) { if (P.vy < -150) P.vy = 850; T.update(1 / 60); f.push(+P.face.toFixed(2)); }
      c.keyR = false; return f; }''')
    check('при смене направления облик разворачивается за ~0,1 с', min(fc[:12]) <= -0.99 and fc[23] >= 0.99, str(fc))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()



TEXTS_SRC = [      # строки раздела 12, которые видны только в забеге (подсказки) или после миграции
    '×2 — теперь каждый пойманный светлячок считается за двух. Новые кочки подряд разгонят множитель до ×5',
    'Прыгай на новые кочки подряд — растёт множитель светлячков, до ×5. Снова на ту же кочку — он падает',
    'Облики обновились: вернули светлячков за прежние облики и следы',
]
TEXTS_HELP = [     # памятка: название и описание
    ('Сухой лист', 'Лёгкий и ломкий. Выдержит один прыжок, потом сорвётся и улетит'),
    ('Призрачная кочка', 'Пунктирная капсула — только видимость. Не держит и тает от касания'),
    ('Репейник', 'Качается из стороны в сторону. Прыгни сверху — рассыплется. Сбоку и снизу столкнёт вниз'),
    ('Паук', 'Висит на нитке и ходит вверх-вниз. Прыжок сверху рвёт нитку'),
    ('Жук-сторож', 'Охраняет свою кочку и ходит по ней от края до края. Сверху можно, сбоку боднёт'),
    ('Сыч', 'Сидит у края. Глаза вспыхнули — сейчас спикирует через экран. Уклонись или прыгни на него сверху'),
    ('Звёздная медуза', 'Прыгни на колокол — подбросит очень высоко. Щупальца жалят'),
    ('Крылья', 'Запасной прыжок в воздухе. Заряд восстанавливается сам. У каждого облика свой взмах'),
    ('Множитель светлячков', 'Новые кочки подряд разгоняют его до ×5 — он горит рядом со счётчиком светлячков. Каждый пойманный светлячок считается за столько. На высоту не влияет. Прыжок на ту же кочку снижает множитель, удар ворчуна сбрасывает'),
]
OLD_WORDS = ['Следы', 'ветк', 'стайк', 'Светик', 'Грибок', 'Капля', 'Лягух', 'Лунный кот', 'Дух-лис', 'Зайка-призрак', 'Желейка', 'Мотылёк', 'Кристаллик', 'Звездочёт', 'Хранитель']


async def t_texts(b):
    print('Тексты (раздел 12)')
    ctx, pg = await page(b)
    src = await pg.evaluate('() => fetch(location.href).then((r) => r.text())')
    flat = ' '.join(src.split())
    for s in TEXTS_SRC: check(f'строка «{s[:46]}…»', s in flat)
    gift = await pg.evaluate('''() => { const b = document.getElementById('bGift'); return { t: b.textContent.replace(/\\s+/g, ' ').trim(), ic: !!b.querySelector('use[href="#i-fly"]') }; }''')
    check('кнопка меню: «Подарок леса» + значок светлячка + «100»', gift['t'].startswith('Подарок леса') and gift['t'].endswith('100') and gift['ic'], str(gift))
    pl = await pg.evaluate('() => [1, 3, 5, 10, 21, 24, 25].map((n) => window.__tl.MDEF.puffs.text(n))')
    want = ['Сорви 1 сухой лист', 'Сорви 3 сухих листа', 'Сорви 5 сухих листьев', 'Сорви 10 сухих листьев', 'Сорви 21 сухой лист', 'Сорви 24 сухих листа', 'Сорви 25 сухих листьев']
    check('задание «Сорви N сухих листьев» с правильными окончаниями', pl == want, str(pl))
    other = await pg.evaluate('() => [window.__tl.MDEF.stomps.text(5)]')
    check('задание про ворчунов без изменений', other == ['Приземлись сверху на 5 ворчунов'], str(other))
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('() => document.getElementById("bHelp").click()'); await pg.wait_for_timeout(300)
    help_txt = ' '.join((await pg.evaluate('() => document.getElementById("helpBody").innerText')).split())
    for name, d in TEXTS_HELP: check(f'памятка: {name}', name in help_txt and d in help_txt, '')
    i1, i2, i3 = help_txt.find('Находки'), help_txt.find('Ворчуны'), help_txt.find('Остальное')
    check('памятка: раздел «Ворчуны» между «Находками» и «Остальным»', 0 <= i1 < i2 < i3, f'{i1} {i2} {i3}')
    await pg.evaluate('() => { document.getElementById("help").hidden = true; document.getElementById("settings").hidden = true; document.getElementById("bShop").click(); }'); await pg.wait_for_timeout(200)
    shop_txt = ' '.join((await pg.evaluate('() => document.getElementById("shop").innerText')).split())
    seen = [w for w in OLD_WORDS if w in help_txt or w in shop_txt]
    check('в лавке и памятке нет старых слов (следы отдельно, ветка, стайки, прежние облики)', not seen, str(seen))
    names = await pg.evaluate('() => window.__tl.SKINS.map((s) => s.name)')
    check('в лавке все 12 новых имён', all(n in shop_txt for n in names), str([n for n in names if n not in shop_txt]))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


TESTS = [('gift', t_gift), ('coins', t_coins), ('ghost', t_ghost), ('leaf', t_leaf), ('beasts', t_beasts), ('migration', t_migration), ('skins', t_skins), ('texts', t_texts)]


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
