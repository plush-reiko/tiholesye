"""Автопроверки «Тихолесья» (раздел 13.2 ТЗ 21.11 и раздел 9 ТЗ 24.11).

Запуск: python3 -m http.server 8765 --bind 127.0.0.1 --directory <папка репозитория>   # в отдельном окне
        python3 tests.py [только_эти_разделы через запятую]
Разделы: gift coins ghost leaf beasts migration skins texts bot lite speed offline.
Для speed и части migration нужна старая версия (index.html из коммита 8fd511c), раздайте её на другом порту
и передайте адрес: TL_OLD_URL=http://127.0.0.1:8766/index.html python3 tests.py speed
Нужен Playwright: pip install playwright && python3 -m playwright install chromium
Каждая проверка печатает «ок» или «ОШИБКА» с пояснением; в конце — итог. Ошибки консоли браузера считаются провалом.
"""
import asyncio, base64, json, os, sys
from playwright.async_api import async_playwright

URL = os.environ.get('TL_URL', 'http://127.0.0.1:8765/index.html')
OLD_URL = os.environ.get('TL_OLD_URL', '')           # старая версия игры (8fd511c: облики 21.11, схема v2), если раздаётся
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
# Сохранение v2 (облики 21.11, версия 8fd511c): 500 светлячков, рекорд 3 100 м, 4 задания, облики ёжик, лис, сова, шмель, рысь, надет шмель.
# Перенос в v3 по таблице 7.1 ТЗ 24.11: облики на той же ступени лавки, светлячки не меняются, один тост «Облики теперь новые…»
V2_JSON = json.dumps({'v': 2, 'coins': 500, 'best': 3100, 'bestZen': 0, 'runs': 12, 'totalCoins': 1900, 'totalHeight': 21000, 'skin': 'shmel',
    'skins': ['ezhik', 'lis', 'sova', 'shmel', 'rys'], 'refund': 0, 'up': {'wings': 2, 'dandelion': 1, 'comet': 0, 'magnet': 0, 'luck': 1, 'bubble': 0},
    'missions': [{'type': 'height', 'n': 800, 'rw': 70, 'p': 0, 'done': False}], 'mTier': {'height': 2}, 'mDone': 4,
    'stats': {'stomps': 3, 'bouncy': 9, 'puffs': 4, 'flights': 1, 'wings': 20, 'maxMult': 3},
    'set': {'music': False, 'sfx': True, 'control': 'sides', 'fx': 'high', 'musicVol': 0.8, 'sfxVol': 1},
    'tut': True, 'zen': False, 'gift': '2026-11-23', 'multTip': True, 'recent': [3100, 900], 'playTime': 1200})
V2_SKINS = ['tihohodka', 'rosyanka', 'baranets', 'rybaluna', 'aspid']
RENEW = 'Облики теперь новые'
SKIN_IDS = ['tihohodka', 'opyata', 'rosyanka', 'baranets', 'beresten', 'zheoda', 'udilshchik', 'rybaluna', 'zvezdoryl', 'zmey', 'aspid', 'izbushka']


async def menu(pg):
    await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"'); await pg.wait_for_timeout(300)


async def toasts(pg):
    return await pg.evaluate('() => [...document.querySelectorAll("#toasts .toast")].map((t) => t.textContent.replace(/\\s+/g, " ")).join(" | ")')


def digits(s):
    return ''.join(ch for ch in s if ch.isdigit())


async def t_migration(b):
    print('Миграция сохранений v1 → v2 → v3')
    old = json.loads(OLD_JSON)
    # 1. сохранение v1 в хранилище: облики v1 → v2 → v3, возврат светлячков за убранные облики и следы
    ctx, pg = await page(b, storage=OLD_JSON)
    s = await pg.evaluate('() => window.__tl.save')
    tt = await toasts(pg)
    check('v1 из хранилища: облики tihohodka и opyata, надета tihohodka', s['skins'] == ['tihohodka', 'opyata'] and s['skin'] == 'tihohodka', f"{s['skins']} / {s['skin']}")
    check('v1: светлячков больше на 6 550', s['coins'] == old['coins'] + OLD_REFUND, f"было {old['coins']}, стало {s['coins']}")
    check('v1: тост о возврате с суммой, тоста «Облики теперь новые» нет', 'Облики обновились' in tt and '6550' in digits(tt) and RENEW not in tt, tt)
    check('v1: схема v3, refund 0, renew false, без следов, прочее на месте', s['v'] == 3 and s['refund'] == 0 and s['renew'] is False and 'trail' not in s and 'trails' not in s
          and s['best'] == old['best'] and s['mDone'] == old['mDone'] and s['up']['wings'] == 2 and s['set']['music'] is False and s['set']['control'] == 'sides',
          json.dumps({k: s.get(k) for k in ['v', 'refund', 'renew', 'best', 'mDone']}))
    stored = await pg.evaluate('() => JSON.parse(localStorage.getItem("tiholesye.save.v1"))')
    check('v1: в хранилище уже v3 (refund 0, renew false)', stored['v'] == 3 and stored['refund'] == 0 and stored['renew'] is False and stored['coins'] == s['coins'])
    await pg.reload(); await menu(pg)
    s2 = await pg.evaluate('() => window.__tl.save'); tt2 = await toasts(pg)
    check('v1: повторная загрузка — без тостов и начислений', s2['coins'] == s['coins'] and 'Облики обновились' not in tt2 and RENEW not in tt2, f"{s2['coins']} {tt2}")
    errs = list(pg.errors); await ctx.close()
    # 2. код переноса v1 — через поле в настройках
    ctx, pg = await page(b)
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('(code) => { document.getElementById("saveIn").value = code; }', OLD_CODE)
    await pg.evaluate('() => document.getElementById("bImport").click()'); await pg.wait_for_timeout(400)
    s3 = await pg.evaluate('() => window.__tl.save'); tt3 = await toasts(pg)
    check('код v1 через поле настроек: облики, светлячки с возвратом, тост возврата', s3['skins'] == ['tihohodka', 'opyata'] and s3['skin'] == 'tihohodka'
          and s3['coins'] == old['coins'] + OLD_REFUND and 'Облики обновились' in tt3 and RENEW not in tt3 and s3['renew'] is False, f"{s3['skins']} {s3['coins']} | {tt3}")
    code2 = await pg.evaluate('() => window.__tl.exportCode()')
    data2 = await pg.evaluate('(c) => JSON.parse(decodeURIComponent(escape(atob(c.slice(4)))))', code2)
    check('новый код: префикс TL1. и v 3', code2.startswith('TL1.') and data2['v'] == 3)
    ok = await pg.evaluate('(c) => window.__tl.importCode(c)', code2)
    s4 = await pg.evaluate('() => window.__tl.save')
    check('код v3 загружается обратно без второго возврата', ok and s4['coins'] == s3['coins'] and s4['skins'] == s3['skins'], f"{s4['coins']}")
    errs += pg.errors; await ctx.close()
    # 3. сохранение v2 в хранилище: облики один к одному на той же ступени, светлячки не меняются
    v2 = json.loads(V2_JSON)
    ctx, pg = await page(b, storage=V2_JSON)
    s5 = await pg.evaluate('() => window.__tl.save'); tt5 = await toasts(pg)
    check('v2 из хранилища: облики по таблице 7.1, надета Рыба-луна', s5['skins'] == V2_SKINS and s5['skin'] == 'rybaluna', f"{s5['skins']} / {s5['skin']}")
    check('v2: ровно 500 светлячков; рекорд, задания, улучшения, статистика, настройки и подарок прежние', s5['coins'] == 500 and s5['best'] == 3100 and s5['mDone'] == 4
          and s5['up'] == v2['up'] and s5['stats'] == v2['stats'] and s5['set']['control'] == 'sides' and s5['set']['music'] is False and s5['gift'] == '2026-11-23',
          json.dumps({k: s5.get(k) for k in ['coins', 'best', 'mDone', 'up', 'gift']}))
    check('v2: один тост «Облики теперь новые…», тоста возврата и «Новый облик» нет', tt5.count(RENEW) == 1 and 'Облики обновились' not in tt5 and 'Новый облик' not in tt5, tt5)
    stored = await pg.evaluate('() => JSON.parse(localStorage.getItem("tiholesye.save.v1"))')
    check('v2: схема v3, renew false — и в хранилище', s5['v'] == 3 and s5['renew'] is False and stored['v'] == 3 and stored['renew'] is False and stored['skins'] == V2_SKINS)
    await pg.reload(); await menu(pg)
    s6 = await pg.evaluate('() => window.__tl.save'); tt6 = await toasts(pg)
    check('v2: после перезагрузки тостов нет', RENEW not in tt6 and 'Облики обновились' not in tt6 and s6['coins'] == 500 and s6['skins'] == V2_SKINS, f"{s6['coins']} {tt6}")
    errs += pg.errors; await ctx.close()
    # 4. код v2 (собран в странице так же, как exportCode) — через поле в настройках
    ctx, pg = await page(b)
    code_v2 = await pg.evaluate('(j) => "TL1." + btoa(unescape(encodeURIComponent(j)))', V2_JSON)
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('(code) => { document.getElementById("saveIn").value = code; }', code_v2)
    await pg.evaluate('() => document.getElementById("bImport").click()'); await pg.wait_for_timeout(400)
    s7 = await pg.evaluate('() => window.__tl.save'); tt7 = await toasts(pg)
    check('код v2 через поле настроек: облики по таблице, 500 светлячков, тосты «Сохранение загружено» и «Облики теперь новые…»',
          s7['skins'] == V2_SKINS and s7['skin'] == 'rybaluna' and s7['coins'] == 500 and s7['best'] == 3100 and 'Сохранение загружено' in tt7 and RENEW in tt7 and 'Облики обновились' not in tt7,
          f"{s7['skins']} {s7['coins']} | {tt7}")
    errs += pg.errors; await ctx.close()
    # 5. рекорд 3 200 м и 12 заданий до обновления: Аспид и Избушка сразу после загрузки
    rich = dict(old, best=3200, mDone=12)
    ctx, pg = await page(b, storage=json.dumps(rich))
    s8 = await pg.evaluate('() => window.__tl.save'); tt8 = await toasts(pg)
    check('рекорд 3 200 м: Аспид сразу; 12 заданий: Избушка сразу; тост «Новый облик: Аспид»', 'aspid' in s8['skins'] and 'izbushka' in s8['skins'] and 'Аспид' in tt8, f"{s8['skins']} | {tt8}")
    # 6. сброс прогресса: чистое v3 с одной Тихоходкой, настройки и отметка подарка остаются
    await pg.evaluate('() => { const s = window.__tl.save; s.gift = "2026-11-21"; s.set.sfx = false; window.__tl.persist(); }')
    await pg.evaluate('() => document.getElementById("bSet").click()'); await pg.wait_for_timeout(150)
    await pg.evaluate('() => { const b = document.getElementById("bReset"); b.click(); b.click(); }'); await pg.wait_for_timeout(300)
    s9 = await pg.evaluate('() => window.__tl.save')
    check('«Сбросить прогресс»: v3, только Тихоходка, 0 светлячков, renew false; настройки и подарок на месте', s9['v'] == 3 and s9['skins'] == ['tihohodka'] and s9['skin'] == 'tihohodka'
          and s9['coins'] == 0 and s9['renew'] is False and s9['set']['sfx'] is False and s9['set']['music'] is False and s9['gift'] == '2026-11-21',
          json.dumps({k: s9.get(k) for k in ['v', 'skins', 'coins', 'renew', 'gift']}))
    errs += pg.errors; await ctx.close()
    # 7. если раздаётся версия 8fd511c (TL_OLD_URL): свежий код прямо из неё
    if OLD_URL:
        ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
        po = await ctx.new_page(); await po.goto(OLD_URL); await po.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
        code_old = await po.evaluate('''() => { const s = window.__tl.save; s.coins = 77; s.skins = ['ezhik', 'lis', 'sova', 'shmel', 'rys']; s.skin = 'shmel';
          return 'TL1.' + btoa(unescape(encodeURIComponent(JSON.stringify(s)))); }''')
        await ctx.close()
        ctx, pg = await page(b)
        ok = await pg.evaluate('(c) => window.__tl.importCode(c)', code_old)
        await pg.evaluate('() => window.__tl.afterLoad()')
        s10 = await pg.evaluate('() => window.__tl.save')
        check('свежий код из версии 8fd511c: облики по таблице 7.1, надета Рыба-луна, ровно 77 светлячков',
              ok and s10['skins'] == V2_SKINS and s10['skin'] == 'rybaluna' and s10['coins'] == 77, f"{s10['skins']} {s10['skin']} {s10['coins']}")
        errs += pg.errors; await ctx.close()
    check('ошибок в консоли нет', not errs, '; '.join(errs[:3]))


# рисунок облика на отдельном холсте: позы против покоя, рамка 3.7, силуэты попарно (раздел 9.2 ТЗ 24.11)
DRAWN = r"""() => { const T = window.__tl, A = T.Art, W = 300, H = 300, OX = 150, OY = 200, S = 2;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H; const x = cv.getContext('2d', { willReadFrequently: true });
  const shot = (sk, a) => { x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, W, H); x.setTransform(S, 0, 0, S, OX, OY); A.char(x, sk, a); x.setTransform(1, 0, 0, 1, 0, 0); return x.getImageData(0, 0, W, H).data; };
  // доля отличающихся пикселей от площади объединения: непрозрачен только в одном или |ΔR|+|ΔG|+|ΔB| > 60
  const diff = (p, q) => { let uni = 0, d = 0; for (let i = 0; i < p.length; i += 4) { const ap = p[i + 3] > 127, aq = q[i + 3] > 127; if (!ap && !aq) continue; uni++;
    if (ap !== aq || Math.abs(p[i] - q[i]) + Math.abs(p[i + 1] - q[i + 1]) + Math.abs(p[i + 2] - q[i + 2]) > 60) d++; } return uni ? d / uni : 0; };
  const grow = (bx, d) => { for (let py = 0; py < H; py++) for (let px = 0; px < W; px++) if (d[(py * W + px) * 4 + 3] > 127) {
    const ux = (px + 0.5 - OX) / S, uy = (py + 0.5 - OY) / S; if (ux < bx[0]) bx[0] = ux; if (ux > bx[1]) bx[1] = ux; if (uy < bx[2]) bx[2] = uy; if (uy > bx[3]) bx[3] = uy; } };
  const out = {}, masks = {};
  for (const sk of T.SKINS) {
    const rest = shot(sk, { t: 0.873, wing: 1 });
    const m = new Uint8Array(W * H); for (let i = 0; i < m.length; i++) m[i] = rest[i * 4 + 3] > 127 ? 1 : 0; masks[sk.id] = m;
    const r = { rise: diff(rest, shot(sk, { t: 0.873, wing: 1, ly: -1, ear: -1 })), fall: diff(rest, shot(sk, { t: 0.873, wing: 1, ly: 1, ear: 1 })),
      flap: diff(rest, shot(sk, { t: 0.873, wing: 1, flap: 0.6 })), empty: diff(rest, shot(sk, { t: 0.873, wing: 0 })) };
    const bRest = [1e9, -1e9, 1e9, -1e9], bFly = [1e9, -1e9, 1e9, -1e9];
    for (let i = 0; i <= 60; i++) for (const w of [1, 0]) grow(bRest, shot(sk, { t: i / 10, wing: w }));
    for (const ly of [-1, 1]) for (const f of [0, 0.25, 0.5, 0.75, 1]) grow(bFly, shot(sk, { t: 0.873, wing: 1, ly, ear: ly, flap: f }));
    r.rest = bRest.map((v) => Math.round(v * 10) / 10); r.fly = bFly.map((v) => Math.round(v * 10) / 10);
    for (const k of ['rise', 'fall', 'flap', 'empty']) r[k] = Math.round(r[k] * 1000) / 1000;
    out[sk.id] = r;
  }
  const ids = T.SKINS.map((s) => s.id), iou = [];
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) { const a = masks[ids[i]], b = masks[ids[j]]; let n = 0, u = 0;
    for (let k = 0; k < a.length; k++) { if (a[k] && b[k]) n++; if (a[k] || b[k]) u++; } iou.push([ids[i], ids[j], Math.round(n / (u || 1) * 1000) / 1000]); }
  return { out, iou };
}"""


async def t_skins(b):
    print('Облики, взмахи, следы, лавка, позы, рамка, силуэты')
    ctx, pg = await page(b)
    sh = await pg.evaluate('''() => { document.getElementById('bShop').click();
      const tabs = [...document.querySelectorAll('#shopTabs button')].map((x) => x.textContent.trim());
      const cards = document.querySelectorAll('#shopBody .card').length, trail = document.getElementById('bbTrail').textContent;
      return { tabs, cards, trail, cur: window.__tl.save.skin }; }''')
    check('пустое сохранение: надета Тихоходка; в лавке вкладки «Облики» и «Усиления», 12 карточек, «След: мох»',
          sh['cur'] == 'tihohodka' and sh['tabs'] == ['Облики', 'Усиления'] and sh['cards'] == 12 and sh['trail'] == 'След: мох', str(sh))
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
    check('каждый облик покупается/открывается и надевается, у каждого строка «След: …» = trailName', not bad, str(bad or [x[3] for x in bought]))
    spent = await pg.evaluate('() => 99999 - window.__tl.save.coins')
    check('потрачено ровно 13 150 (цены таблицы раздела 4)', spent == 150 + 400 + 700 + 1000 + 1300 + 1700 + 2100 + 2600 + 3200, str(spent))
    # 10 с забега на каждом: взмахи, след и всплески вместе — не больше 40 частиц
    r = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P, s = T.save, out = {};
      document.getElementById('shop').hidden = true;
      for (const sk of T.SKINS) {
        s.skin = sk.id; g.zen = true; T.startRun(true);
        let maxTrail = 0, flapSeen = 0, emitted = 0; const seen = new Set();
        for (let i = 0; i < 600; i++) {
          if (P.vy < -150 && P.y < T.run.maxY - 60) P.vy = 850;                // бот-пружина: не даём упасть
          if (i % 90 === 10) { s.up.wings = 3; P.charges = Math.max(P.charges, 1); T.flap(); }
          T.update(1 / 60); if (i % 2 === 0) T.render();
          let n = 0; for (const q of g.parts) if (q.trail) { n++; if (!seen.has(q)) { seen.add(q); emitted++; } }
          maxTrail = Math.max(maxTrail, n); if (P.flap > 0) flapSeen++;
        }
        out[sk.id] = { maxTrail, flapSeen, emitted, dash: sk.trail.k === 'dash' ? P.hist.length : -1 };
      }
      return out; }''')
    over = {k: v for k, v in r.items() if v['maxTrail'] > 40}
    check('10 с забега на каждом облике без ошибок', not pg.errors, '; '.join(pg.errors[:3]))
    check('след вылетает у каждого (у Удильщика — путь лески: P.hist больше 10 точек)', all((v['emitted'] > 5) if v['dash'] < 0 else v['dash'] > 10 for v in r.values()),
          str({k: (v['emitted'], v['dash']) for k, v in r.items()}))
    check('живых частиц следа вместе со всплесками не больше 40', not over, str(over or {k: v['maxTrail'] for k, v in r.items()}))
    check('взмах проигрывается у каждого', all(v['flapSeen'] > 4 for v in r.values()), str({k: v['flapSeen'] for k, v in r.items()}))
    # нагрузка: Росянка (самый большой всплеск) — сплошной выпуск следа и 20 взмахов подряд упираются в 40
    st = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P; T.save.skin = 'rosyanka'; g.zen = true; T.startRun(true); g.parts.length = 0; let mx = 0;
      for (let i = 0; i < 200; i++) { T.emitTrail(0.5); if (i % 10 === 0) { P.charges = 3; P.vy = 0; P.fly = null; T.flap(); }
        let n = 0; for (const q of g.parts) if (q.trail) n++; mx = Math.max(mx, n); }
      return mx; }''')
    check('Росянка: 200 выпусков следа и 20 взмахов подряд — частиц следа не больше 40', st <= 40, str(st))
    fk = await pg.evaluate('() => window.__tl.SKINS.map((s) => s.flapK)')
    check('длительность взмаха задана у каждого облика, разных значений не меньше 6', all(isinstance(x, (int, float)) and x > 0 for x in fk) and len(set(fk)) >= 6, str(fk))
    # разворот: смена направления за ~0,1 с
    fc = await pg.evaluate('''() => { const T = window.__tl, g = T.game, P = T.P, c = T.ctl; T.save.skin = 'rosyanka'; g.zen = true; T.startRun(true);
      const f = []; c.keyL = true; for (let i = 0; i < 12; i++) { if (P.vy < -150) P.vy = 850; T.update(1 / 60); f.push(+P.face.toFixed(2)); }
      c.keyL = false; c.keyR = true; for (let i = 0; i < 12; i++) { if (P.vy < -150) P.vy = 850; T.update(1 / 60); f.push(+P.face.toFixed(2)); }
      c.keyR = false; return f; }''')
    check('при смене направления облик разворачивается за ~0,1 с', min(fc[:12]) <= -0.99 and fc[23] >= 0.99, str(fc))
    # рисунок: позы полёта, «без заряда» и взмах отличаются от покоя; рамка 3.7; силуэты не похожи друг на друга
    d = await pg.evaluate(DRAWN)
    o = d['out']
    for key, lim, name in [('rise', 0.06, 'подъём'), ('fall', 0.06, 'спуск'), ('flap', 0.05, 'взмах'), ('empty', 0.02, 'без заряда')]:
        low = {k: v[key] for k, v in o.items() if v[key] < lim}
        check(f'поза «{name}» отличается от покоя (доля пикселей ≥ {lim})', not low, str(low or {k: v[key] for k, v in o.items()}))
    out_rest = {k: v['rest'] for k, v in o.items() if not (v['rest'][0] >= -32.5 and v['rest'][1] <= 32.5 and v['rest'][2] >= -62.5 and v['rest'][3] <= 4.5)}
    check('рамка в покое (t 0…6 с, с зарядом и без): x ∈ [−32; 32], y ∈ [−62; 4]', not out_rest, str(out_rest or {k: v['rest'] for k, v in o.items()}))
    out_fly = {k: v['fly'] for k, v in o.items() if not (v['fly'][0] >= -34.5 and v['fly'][1] <= 34.5 and v['fly'][2] >= -66.5 and v['fly'][3] <= 28.5)}
    check('рамка в полёте (подъём и спуск, кадры взмаха): x ∈ [−34; 34], y ∈ [−66; 28]', not out_fly, str(out_fly or {k: v['fly'] for k, v in o.items()}))
    close = [x for x in d['iou'] if x[2] >= 0.7]
    check('силуэты различаются: пересечение / объединение < 0,7 для всех 66 пар', len(d['iou']) == 66 and not close,
          str(close or sorted(d['iou'], key=lambda x: -x[2])[:4]))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


TEXTS_SRC = [      # строки раздела 12, которые видны только в забеге (подсказки) или после миграции
    '×2 — теперь каждый пойманный светлячок считается за двух. Новые кочки подряд разгонят множитель до ×5',
    'Прыгай на новые кочки подряд — растёт множитель светлячков, до ×5. Снова на ту же кочку — он падает',
    'Облики обновились: вернули светлячков за прежние облики и следы',
    'Облики теперь новые. Вместо каждого купленного — новый, и он уже твой',
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
OLD_WORDS = ['Следы', 'ветк', 'стайк', 'Светик', 'Грибок', 'Капля', 'Лягух', 'Лунный кот', 'Дух-лис', 'Зайка-призрак', 'Желейка', 'Мотылёк', 'Кристаллик', 'Звездочёт', 'Хранитель',
             'Ёжик', 'Мухомор', 'Лисёнок', 'Совёнок', 'Сорока', 'Заяц-беляк', 'Снегирь', 'Шмель', 'Белка-летяга', 'Летучая мышка', 'Рысь']


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



# бот с идеальным прицелом: падая, встаёт ровно над самой высокой целой кочкой ниже себя (в точку, где над ней больше всего места);
# в подъёме уходит в сторону от ворчуна над головой со скоростью клавиатуры; сам не машет крыльями и не берёт пузырей.
# Лес проходим, если бот доходит до 7 000 м
BOT = r"""([seed, beasts]) => { const T = window.__tl, g = T.game, P = T.P, s = T.save;
  s.up.wings = 0; s.up.bubble = 0; g.seed = seed; g.zen = false; T.startRun(true); P.shield = false; P.charges = 0;
  const H0 = g.startY, goal = H0 + 7000 * 10;
  const solid = (q) => !q.dead && !q.fall && q.type !== 'fake' && q.type !== 'ground' && (q.type !== 'phase' || q.on !== false);
  // куда встать на кочке, чтобы прыжок вверх прошёл мимо ворчунов над ней: точка с наибольшим просветом по x (жук сам на кочке — его можно сбить сверху)
  const spot = (q) => { let best = null;
    for (const k of [-0.42, -0.2, 0, 0.2, 0.42]) { const x = q.x + q.w * k; let gap = 1e9;
      for (const bb of g.beasts) if (!bb.dead && bb.kind !== 'beetle' && bb.y > q.top - 8 && bb.y < q.top + 230) gap = Math.min(gap, Math.abs(bb.x - x));
      if (!best || gap > best.gap) best = { x, gap }; }
    return best; };
  let maxY = P.y, lastGain = 0, t = 0, why = 'ok', hits = 0, wasInv = false, maxGap = 0, prevTop = null;
  for (let i = 0; i < 60 * 1500; i++) {
    if (!beasts) g.beasts.length = 0;
    if (g.state !== 'play') { why = 'упал на ' + Math.round((P.y - H0) / 10) + ' м'; break; }
    if (P.vy <= 0 && !P.fly) {
      let best = null;
      for (const q of g.plats) {
        if (!solid(q) || q.top > P.y - 1 || q.top < P.y - 600) continue;
        const sp = spot(q), sc = q.top - (sp.gap < 16 ? 2000 : 0) + (q.type === 'bouncy' ? 30 : 0) - (q.type === 'puff' ? 60 : 0) - (q.type === 'phase' ? 40 : 0);
        if (!best || sc > best.s) best = { q, s: sc, x: sp.x };
      }
      if (best) P.x = best.x + (best.q.vx || 0) * 0.02;
    }
    if (P.vy > 0 && !P.fly) {             // в подъёме уходит в сторону от ворчуна над головой — не быстрее 560 ед./с, как с клавиатуры
      let near = null;
      for (const bb of g.beasts) { if (bb.dead || bb.kind === 'beetle' || bb.y < P.y - 10 || bb.y > P.y + 260) continue; const dx = bb.x - P.x; if (Math.abs(dx) < 48 && (!near || Math.abs(dx) < Math.abs(near))) near = dx; }
      if (near !== null) P.x = Math.min(395, Math.max(5, P.x + (near > 0 || (near === 0 && P.x > 200) ? -1 : 1) * 560 / 60));
    }
    const top0 = P.lastTop; T.update(1 / 60); t += 1 / 60;
    if (P.lastTop !== top0 && P.lastTop > -1e8) { if (prevTop !== null && P.lastTop > prevTop) maxGap = Math.max(maxGap, P.lastTop - prevTop); prevTop = P.lastTop; }
    if (P.inv > 0 && !wasInv) hits++; wasInv = P.inv > 0;
    if (P.y > maxY + 1) { maxY = P.y; lastGain = t; }
    if (t - lastGain > 25) { why = 'застрял на ' + Math.round((P.y - H0) / 10) + ' м'; break; }
    if (P.y >= goal) { why = 'дошёл'; break; }
  }
  return { why, h: Math.round((maxY - H0) / 10), t: Math.round(t), hits, maxGap: Math.round(maxGap) };
}"""


async def t_bot(b):
    print('Лес проходим: бот до 7 000 м')
    ctx, pg = await page(b)
    for seed, beasts in [(3, True), (11, True), (501, True), (2027, True), (90001, True), (123457, True), (2027, False)]:
        r = await pg.evaluate(BOT, [seed, beasts])
        check(f'сид {seed}, {"с ворчунами" if beasts else "без ворчунов"}: бот дошёл до 7 000 м', r['why'] == 'дошёл', str(r))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


# скорость: средний кадр (update + render) при 4-кратном замедлении процессора, «до» против «после»
SPEED = r"""async ([skin, trail, h, n]) => { const T = window.__tl, g = T.game, P = T.P, s = T.save;
  s.skin = skin; if (trail !== null && 'trail' in s) s.trail = trail; s.set.fx = 'high';
  g.zen = false; T.startRun(true); const y = g.startY + h * 10;
  for (let k = 0; k < 40 && g.plats.length; k++) T.genUpTo(y + 1500);
  P.y = y; P.vy = 500; if (T.run) T.run.maxY = y; g.camY = y - T.view.H * 0.44;
  const step = () => { if (P.vy < -200) P.vy = 760; if (g.state !== 'play') { g.state = 'play'; } T.update(1 / 60); T.render(); };
  for (let i = 0; i < 40; i++) step();                       // разогрев: спрайты, кэши, частицы следа
  const t0 = performance.now(); for (let i = 0; i < n; i++) step(); const ms = (performance.now() - t0) / n;
  return { ms: Math.round(ms * 100) / 100, beasts: (g.beasts || []).length, parts: g.parts.length };
}"""


async def speed_of(b, url, cases):
    ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(url); await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"'); await pg.wait_for_timeout(500)
    cdp = await ctx.new_cdp_session(pg); await cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    out = {}
    for name, args in cases.items():
        rs = [await pg.evaluate(SPEED, args) for _ in range(3)]
        out[name] = sorted(r['ms'] for r in rs)[1]           # медиана трёх замеров
    await ctx.close()
    return out, errs


async def t_speed(b):
    print('Скорость (процессор ×4 медленнее)')
    if not OLD_URL:
        check('скорость: нужна старая версия (TL_OLD_URL)', False, 'раздай index.html из коммита 8fd511c и передай адрес в TL_OLD_URL'); return
    # «до» (облики 21.11): ёжик на поляне, шмель в кронах, светлячок (пунктир и своё свечение) и мухомор (больше всего частиц) в выси;
    # «после»: Тихоходка на поляне, Рыба-луна в кронах и все 12 обликов в выси — каждый сравнивается с худшим из двух «до»
    old, e1 = await speed_of(b, OLD_URL, {'поляна': ['ezhik', None, 350, 120], 'кроны': ['shmel', None, 3600, 120], 'высь': ['svetlyachok', None, 5600, 120], 'высь2': ['mukhomor', None, 5600, 120]})
    cases = {'поляна': ['tihohodka', None, 350, 120], 'кроны': ['rybaluna', None, 3600, 120]}
    for sid in SKIN_IDS: cases[f'высь, {sid}'] = [sid, None, 5600, 120]
    new, e2 = await speed_of(b, URL, cases)
    print('    до:', old, '\n    после:', new)
    for k, v in new.items():
        ref = old['поляна'] if k == 'поляна' else old['кроны'] if k.startswith('кроны') else max(old['высь'], old['высь2'])
        check(f'кадр «{k}» не хуже версии «до» больше чем на 15%', v <= ref * 1.15, f'{v} мс против {ref} мс')
    check('ошибок нет', not e1 and not e2, '; '.join((e1 + e2)[:3]))


async def t_lite(b):
    print('«Экономно»')
    ctx, pg = await page(b)
    r = await pg.evaluate(r"""() => { const T = window.__tl, A = T.Art, g = T.game, P = T.P, s = T.save; let halos = 0; const h0 = A.halo; A.halo = (...a) => { halos++; return h0(...a); };
      s.set.fx = 'low'; const out = [];
      for (const h of [0, 350, 1100, 2100, 3600, 5600]) {
        g.zen = false; T.startRun(true); const y = g.startY + h * 10; for (let k = 0; k < 40 && g.plats.length; k++) T.genUpTo(y + 1500);
        P.y = y + 20; P.vy = 400; g.camY = y - T.view.H * 0.44; for (let i = 0; i < 20; i++) { if (P.vy < -200) P.vy = 700; T.update(1 / 60); } T.render();
        const cv = T.view.cv, x = cv.getContext('2d'), d = x.getImageData(0, 0, cv.width, cv.height).data; let mn = 1e9, mx = -1;
        for (let i = 0; i < d.length; i += 4 * 97) { const v = d[i] + d[i + 1] + d[i + 2]; mn = Math.min(mn, v); mx = Math.max(mx, v); }
        out.push(mx - mn);
      }
      A.halo = h0;
      // своё свечение: в «Экономно» гаснет у пяти (у Жеоды — во взмахе, когда створка раскрыта больше чем наполовину); у семи остальных рисунок прежний
      const GLOW = { tihohodka: { t: 1, wing: 1 }, opyata: { t: 1, wing: 1 }, udilshchik: { t: 1, wing: 1 }, izbushka: { t: 1, wing: 1 }, zheoda: { t: 1, wing: 1, flap: 0.5 } };
      const px = (sk, a, lite) => { A.setLite(lite); const c2 = document.createElement('canvas'); c2.width = c2.height = 160; const y = c2.getContext('2d');
        y.fillStyle = '#000'; y.fillRect(0, 0, 160, 160); y.translate(80, 140); y.scale(2, 2); A.char(y, sk, a); const d = y.getImageData(0, 0, 160, 160).data; let sum = 0; for (let i = 0; i < d.length; i += 4) sum += d[i + 1]; return sum; };
      const own = {}, same = {};
      for (const sk of T.SKINS) { const a = GLOW[sk.id] || { t: 1, wing: 1 }; (GLOW[sk.id] ? own : same)[sk.id] = [px(sk, a, true), px(sk, a, false)]; }
      A.setLite(false); s.set.fx = 'high';
      return { halos, spread: out, own, same }; }""")
    check('в «Экономно» всё рисуется (кадр не пустой во всех зонах и в меню)', all(v > 60 for v in r['spread']), str(r['spread']))
    check('в «Экономно» ореолов нет (Art.halo не вызывается)', r['halos'] == 0, str(r['halos']))
    bad = {k: v for k, v in r['own'].items() if not v[0] < v[1] * 0.97}
    check('в «Экономно» своё свечение гаснет у пяти: Тихоходка, Опята, Жеода, Удильщик, Избушка', len(r['own']) == 5 and not bad,
          str(bad or {k: round(v[0] / v[1], 3) for k, v in r['own'].items()}))
    diff = {k: v for k, v in r['same'].items() if v[0] != v[1]}
    check('у семи остальных «Экономно» рисунок облика не меняет', len(r['same']) == 7 and not diff, str(diff))
    tr = await pg.evaluate(r"""() => { const T = window.__tl, g = T.game, P = T.P, s = T.save, n = {};
      for (const fx of ['high', 'low']) { s.set.fx = fx; s.skin = 'zheoda'; g.zen = true; T.startRun(true); g.parts.length = 0; let made = 0; const seen = new Set();
        for (let i = 0; i < 240; i++) { if (P.vy < -150) P.vy = 850; T.update(1 / 60); T.render(); for (const q of g.parts) if (q.trail && !seen.has(q)) { seen.add(q); made++; } }
        n[fx] = made; }
      s.set.fx = 'high'; return n; }""")
    check('в «Экономно» след выпускается примерно вдвое реже (Жеода)', tr['low'] <= tr['high'] * 0.62, str(tr))
    check('ошибок в консоли нет', not pg.errors, '; '.join(pg.errors[:3]))
    await ctx.close()


def cache_name(repo):
    import hashlib
    h = hashlib.sha256()
    for f in ['icon-180.png', 'icon-192.png', 'icon-512.png', 'index.html', 'manifest.webmanifest']:
        h.update(f.encode()); h.update(open(os.path.join(repo, f), 'rb').read())
    return 'tiholesye-' + h.hexdigest()[:12]


async def t_offline(b):
    print('Офлайн')
    import subprocess, re, socket, time
    repo = os.environ.get('TL_REPO', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sw = open(os.path.join(repo, 'sw.js'), encoding='utf-8').read()
    name = re.search(r"tiholesye-[0-9a-f]{12}", sw).group(0)
    files = re.search(r"const FILES = (\[.*?\]);", sw).group(1)
    check('в sw.js имя кэша = отпечаток файлов игры', name == cache_name(repo), f'{name} / {cache_name(repo)}')
    check('список FILES прежний', files == "['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-192.png', './icon-512.png']", files)
    port = 8790
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', repo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: socket.create_connection(('127.0.0.1', port), 0.2).close(); break
            except OSError: time.sleep(0.1)
        ctx = await b.new_context(viewport={'width': 440, 'height': 956}, device_scale_factor=3, is_mobile=True, has_touch=True)
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        url = f'http://127.0.0.1:{port}/index.html'
        await pg.goto(url); await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"')
        ok = await pg.evaluate("""async (name) => { const reg = await navigator.serviceWorker.ready; for (let i = 0; i < 50; i++) { const keys = await caches.keys(); if (keys.includes(name)) { const c = await caches.open(name); const k = await c.keys(); if (k.length >= 6) return k.length; } await new Promise((r) => setTimeout(r, 200)); } return 0; }""", name)
        check('после первой загрузки все 6 файлов игры в кэше', ok >= 6, str(ok))
    finally:
        srv.terminate(); srv.wait()
    await pg.wait_for_timeout(300)
    try:
        await pg.reload(); await pg.wait_for_function('window.__tl && window.__tl.game.state === "menu"', timeout=10000)
        played = await pg.evaluate("""() => { const T = window.__tl; T.game.zen = true; T.startRun(true); for (let i = 0; i < 120; i++) { if (T.P.vy < -150) T.P.vy = 800; T.update(1 / 60); T.render(); } return T.game.state; }""")
        check('сервер выключен: игра открывается и играется', played == 'play', played)
    except Exception as e:
        check('сервер выключен: игра открывается и играется', False, str(e)[:200])
    check('ошибок в консоли нет', not errs, '; '.join(errs[:3]))
    await ctx.close()


TESTS = [('gift', t_gift), ('coins', t_coins), ('ghost', t_ghost), ('leaf', t_leaf), ('beasts', t_beasts), ('migration', t_migration), ('skins', t_skins), ('texts', t_texts),
         ('bot', t_bot), ('lite', t_lite), ('speed', t_speed), ('offline', t_offline)]


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
