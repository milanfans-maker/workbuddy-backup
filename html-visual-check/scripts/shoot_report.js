#!/usr/bin/env node
/**
 * shoot_report.js —— 通用「实拍 + 结构自检」脚本（本地单文件 HTML / 任意网页）
 *
 * 用途：交付任何报告型 HTML 之前，一条命令完成
 *   ① 结构自检（横向溢出 / Markdown 残留 / 标签配平 / 断图 / JS 报错）
 *   ② 关键内容点检（"这句话在不在页面上"）
 *   ③ 实拍（顶部整屏 + 按节标题逐节截图 + 可选整页长图）
 *   ④ 机器可读的 JSON 摘要 + 严格模式退出码（可直接接进回归流程）
 *
 * 用法：
 *   node shoot_report.js <html路径|http(s)://URL> [选项]
 *
 * 选项：
 *   --prefix NAME      截图文件名前缀（默认取文件名主干）
 *   --out DIR          截图输出目录（默认 HTML 所在目录）
 *   --need "a,b,c"     必须出现的关键词（缺失即 ❌）
 *   --sections "x,y"   要逐节截图的节标题关键词（子串匹配）
 *   --heading "h1,h2,h3"  节标题使用的标签（默认自动探测 h1/h2/h3）
 *   --width N          视口宽（默认 1100）
 *   --height N         视口高（默认 1200）
 *   --scale N          设备像素比（默认 1；2 = 高清图，体积 ×4）
 *   --full             额外输出一张整页长图
 *   --wait MS          加载后额外等待毫秒（默认 400）
 *   --list             只列出标题结构，不截图
 *   --json PATH        把摘要写入 JSON
 *   --strict           有任一检查失败则退出码 1
 *   --quiet            只输出结尾一行结论
 *   --help
 *
 * 退出码：0 = 全部通过（或未开 --strict）；1 = 用法错误 / --strict 下有失败；2 = 运行异常
 *
 * 已知局限（不是 bug）：
 *   · 「<b> 配平」读的是解析后的 innerHTML —— 浏览器会自动闭合未闭合的内联标签
 *     （<p><b>x</p> 会被还原成 <p><b>x</b></p>），所以它抓的是**解析器修不好的**
 *     真失衡，抓不到单纯的漏写闭合标签。要查原始源请直接 grep 源文件。
 *   · 「横向溢出」用 documentElement.scrollWidth 判定，只看**整页**有无溢出；
 *     单个元素的溢出若被祖先 overflow:hidden 裁掉则测不到。
 *   · 「JS 报错」只收集 console.error 与未捕获异常；被 try/catch 吞掉的不算。
 *
 * 依赖：本机 Chrome + puppeteer-core（绝对路径 require，见下方常量）
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PUPPETEER = '/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core';

// ---------------------------------------------------------------- 参数解析

function usage(msg) {
  if (msg) console.error('❌ ' + msg);
  const src = fs.readFileSync(__filename, 'utf8');
  const m = src.match(/\/\*\*([\s\S]*?)\*\//);
  console.error(m ? m[1].replace(/^ \* ?/gm, '').trim() : '');
  process.exit(1);
}

const argv = process.argv.slice(2);
if (!argv.length || argv.includes('--help') || argv.includes('-h')) usage(argv.length ? null : '缺少 HTML 路径');

const opt = {
  prefix: '', out: '', need: [], sections: [], heading: '',
  width: 1100, height: 1200, scale: 1, full: false, wait: 400,
  list: false, json: '', strict: false, quiet: false,
};

// 第一个非 -- 开头的参数是目标
const target = argv.find(a => !a.startsWith('--'));
if (!target) usage('缺少 HTML 路径');

for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  const next = () => {
    const v = argv[++i];
    if (v === undefined || v.startsWith('--')) usage(`选项 ${a} 缺少取值`);
    return v;
  };
  switch (a) {
    case '--prefix':   opt.prefix = next(); break;
    case '--out':      opt.out = next(); break;
    case '--need':     opt.need = next().split(',').map(s => s.trim()).filter(Boolean); break;
    case '--sections': opt.sections = next().split(',').map(s => s.trim()).filter(Boolean); break;
    case '--heading':  opt.heading = next(); break;
    case '--width':    opt.width = parseInt(next(), 10); break;
    case '--height':   opt.height = parseInt(next(), 10); break;
    case '--scale':    opt.scale = parseFloat(next()); break;
    case '--wait':     opt.wait = parseInt(next(), 10); break;
    case '--json':     opt.json = next(); break;
    case '--full':     opt.full = true; break;
    case '--list':     opt.list = true; break;
    case '--strict':   opt.strict = true; break;
    case '--quiet':    opt.quiet = true; break;
    default:
      if (a.startsWith('--')) usage('未知选项 ' + a);
  }
}

const isUrl = /^https?:\/\//.test(target);
const absPath = isUrl ? '' : path.resolve(target);
if (!isUrl && !fs.existsSync(absPath)) usage('文件不存在：' + absPath);

const dir = opt.out ? path.resolve(opt.out) : (isUrl ? process.cwd() : path.dirname(absPath));
const sanitize = s => s.replace(/[\\/:*?"<>|\s]+/g, '_');
// ⚠️ 用户传入的 prefix 也要清洗 `/`：否则 path.join(dir, prefix+'.png') 会把它当成
//    子路径折叠（/tmp + /tmp/x → /tmp/tmp/x）并报 ENOENT。要控制输出目录请用 --out。
const prefix = sanitize(opt.prefix || (isUrl ? 'shot' : path.basename(absPath, path.extname(absPath))));

fs.mkdirSync(dir, { recursive: true });

// ---------------------------------------------------------------- 主流程

function log(...a) { if (!opt.quiet) console.log(...a); }
/** --quiet 只压进度噪声，判定结论必须始终可见 */
function always(...a) { console.log(...a); }

(async () => {
  let puppeteer;
  try {
    puppeteer = require(PUPPETEER);
  } catch (e) {
    console.error('❌ 无法加载 puppeteer-core：' + PUPPETEER);
    console.error('   修复：cd /Users/wangjian/.workbuddy/binaries/node/workspace && npm install puppeteer-core --registry=https://registry.npmmirror.com');
    process.exit(2);
  }
  if (!fs.existsSync(CHROME)) { console.error('❌ 未找到 Chrome：' + CHROME); process.exit(2); }

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--allow-file-access-from-files', '--no-sandbox', '--hide-scrollbars'],
  });

  const jsErrors = [];
  const shots = [];
  let failed = [];

  try {
    const pg = await browser.newPage();
    await pg.setViewport({ width: opt.width, height: opt.height, deviceScaleFactor: opt.scale });
    pg.on('pageerror', e => jsErrors.push('pageerror: ' + String(e.message || e).slice(0, 160)));
    pg.on('console', m => {
      if (m.type() === 'error') jsErrors.push('console: ' + m.text().slice(0, 160));
    });

    const url = isUrl ? target : pathToFileURL(absPath).href;
    await pg.goto(url, { waitUntil: 'load', timeout: 60000 });
    await new Promise(r => setTimeout(r, opt.wait));

    // ---- 结构自检 ------------------------------------------------------
    const info = await pg.evaluate((sel, need) => {
      const html = document.documentElement.innerHTML;
      const text = document.body.innerText;
      const de = document.documentElement;

      const heads = [...document.querySelectorAll(sel)]
        .map(el => ({ tag: el.tagName.toLowerCase(), text: el.textContent.trim().replace(/\s+/g, ' ') }))
        .filter(h => h.text);

      const broken = [...document.images]
        .filter(im => !im.complete || im.naturalWidth === 0)
        .map(im => im.getAttribute('src'));

      return {
        title: document.title || '',
        // 横向溢出：文档实际宽度超过视口。注意 body 自身高度为 0 的坑，用 documentElement
        overflowX: Math.max(0, de.scrollWidth - de.clientWidth),
        docW: de.scrollWidth,
        viewW: de.clientWidth,
        pageH: document.body.scrollHeight,
        tables: document.querySelectorAll('table').length,
        imgs: document.images.length,
        brokenImgs: broken,
        headings: heads,
        mdResidue: (html.match(/\*\*/g) || []).length,
        bOpen: (html.match(/<b[ >]/g) || []).length,
        bClose: (html.match(/<\/b>/g) || []).length,
        preCount: document.querySelectorAll('pre').length,
        miss: need.filter(k => !text.includes(k)),
      };
    }, opt.heading || 'h1,h2,h3', opt.need);

    // ---- 只列结构 ------------------------------------------------------
    if (opt.list) {
      log(`标题结构（${info.headings.length} 条）:`);
      info.headings.forEach((h, i) => log(`  ${String(i + 1).padStart(2)}. [${h.tag}] ${h.text.slice(0, 60)}`));
      await browser.close();
      process.exit(0);
    }

    // ---- 判定 ----------------------------------------------------------
    const checks = [
      ['关键内容缺失', info.miss.length === 0, info.miss.length ? info.miss.join(' / ') : '无'],
      ['横向溢出',     info.overflowX === 0,  info.overflowX === 0 ? '无' : `❌ ${info.overflowX}px（文档 ${info.docW} > 视口 ${info.viewW}）`],
      ['Markdown ** 残留', info.mdResidue === 0, String(info.mdResidue)],
      ['<b> 配平',     info.bOpen === info.bClose, `${info.bOpen} vs ${info.bClose}`],
      ['断图',         info.brokenImgs.length === 0, info.brokenImgs.length ? info.brokenImgs.join(' / ') : `无（共 ${info.imgs} 张）`],
      ['JS 报错',      jsErrors.length === 0, jsErrors.length ? jsErrors.join(' | ') : '无'],
    ];

    log(`标题: ${info.title || '(无)'}`);
    log(`页高: ${info.pageH}px | 视口: ${info.viewW}×${opt.height} | 表格: ${info.tables} | <pre>: ${info.preCount} | 标题节点: ${info.headings.length}`);
    for (const [name, ok, detail] of checks) {
      if (!ok) failed.push(name);
      always(`  ${ok ? '✓' : '❌'} ${name}: ${detail}`);
    }
    log(`章节（前 12）: ` + info.headings.slice(0, 12).map(h => h.text.slice(0, 16)).join(' | '));

    // ---- 截图 ----------------------------------------------------------
    const snap = async (suffix, opts2 = {}) => {
      const f = path.join(dir, `${prefix}_${suffix}.png`);
      await pg.screenshot(Object.assign({ path: f }, opts2));
      shots.push(f);
      return f;
    };

    await snap('top');
    if (opt.full) await snap('full', { fullPage: true });

    let i = 0;
    for (const kw of opt.sections) {
      i++;
      const found = await pg.evaluate((k, sel) => {
        const hs = [...document.querySelectorAll(sel)];
        const el = hs.find(x => x.textContent.includes(k));
        if (!el) return null;
        window.scrollTo(0, Math.max(0, el.getBoundingClientRect().top + window.scrollY - 12));
        return el.textContent.trim().slice(0, 30);
      }, kw, opt.heading || 'h1,h2,h3');

      await new Promise(r => setTimeout(r, 250));
      if (found) {
        const safe = kw.replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 24);
        await snap(`${i}_${safe}`);
      } else {
        failed.push('节标题:' + kw);
        log(`  ❌ 未找到节标题: ${kw}`);
      }
    }

    // ---- 摘要 ----------------------------------------------------------
    const summary = {
      file: isUrl ? target : absPath,
      title: info.title, pageHeight: info.pageH,
      viewport: { width: opt.width, height: opt.height, scale: opt.scale },
      overflowX: info.overflowX, tables: info.tables,
      headings: info.headings.length,
      markdownResidue: info.mdResidue,
      bBalance: [info.bOpen, info.bClose],
      brokenImages: info.brokenImgs,
      jsErrors,
      missingKeywords: info.miss,
      screenshots: shots,
      failed, pass: failed.length === 0,
    };
    if (opt.json) {
      fs.writeFileSync(path.resolve(opt.json), JSON.stringify(summary, null, 2), 'utf8');
      log(`JSON 摘要: ${path.resolve(opt.json)}`);
    }

    log(`截图（${shots.length} 张）→ ${dir}`);
    shots.forEach(f => log('  ' + path.basename(f)));
    if (failed.length) {
      // ⚠️ 未开 --strict 时仍然 exit 0 —— 明确提示，避免"有红叉却当成通过了"的假安心
      always(`🚨 未通过 ${failed.length} 项: ${failed.join(' / ')}`);
      if (!opt.strict) always('   （未开 --strict，退出码仍为 0；接回归流程请加 --strict）');
    } else {
      always('✅ 全部通过');
    }

    await browser.close();
    process.exit(opt.strict && failed.length ? 1 : 0);

  } catch (e) {
    console.error('❌ 运行异常:', e && e.message ? e.message : e);
    try { await browser.close(); } catch (_) {}
    process.exit(2);
  }
})();
