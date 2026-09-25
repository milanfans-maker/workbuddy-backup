#!/usr/bin/env node
/**
 * 扫描棋谱库，为软著说明书挑选一份「干净」的示例棋谱。
 *
 * 为什么要挑：页面「对局信息」区会显示**来源文件名**，玩家卡片显示四个玩家网名。
 * 若文件名或玩家网名里出现第三方姓名（如「姜朕熙」），会直接印进说明书截图 ——
 * 而本次登记为「独立开发」，材料里不应出现无关第三方姓名。
 *
 * 用法：node scan_replays_for_manual.js [最多扫描份数，默认 60]
 */
const puppeteer = require('/Users/wangjian/.workbuddy/binaries/node/workspace/node_modules/puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = '/Volumes/me/ai学习/四国军棋/qq军棋复盘分析';
const LIB = '/Users/wangjian/Documents/布局库';
const PAGE = path.join(ROOT, process.argv[3] || 'index_task2.html');
const LIMIT = parseInt(process.argv[2] || '60', 10);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 不宜出现在登记材料里的字样：第三方姓名 + 敏感/不雅用词
const BAD = ['姜朕熙', '老姜甄鉴', '朕熙', '习', '毛泽东', '共产党', '法轮', '傻', '狗', '畜生', '死全家', '妓', '色情', '赌博', '政治'];

(async () => {
  const files = fs.readdirSync(LIB).filter(x => /\.jgs$/i.test(x))
    .map(x => ({ x, sz: fs.statSync(path.join(LIB, x)).size }))
    .filter(o => o.sz >= 2000)
    .sort((a, b) => b.sz - a.sz)
    .slice(0, LIMIT);

  const b = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new', args: ['--no-sandbox', '--allow-file-access-from-files']
  });
  const p = await b.newPage();
  await p.setViewport({ width: 1500, height: 1050, deviceScaleFactor: 1 });
  await p.goto('file://' + encodeURI(PAGE), { waitUntil: 'load' });
  await sleep(600);

  const rows = [];
  for (const { x, sz } of files) {
    const b64 = fs.readFileSync(path.join(LIB, x)).toString('base64');
    let r;
    try {
      r = await p.evaluate((b64, nm) => {
        const bin = atob(b64), by = new Uint8Array(bin.length);
        for (let i = 0; i < by.length; i++) by[i] = bin.charCodeAt(i);
        try { startAnalyze(jgsToText(by, nm)); } catch (e) { return { err: String(e.message).slice(0, 60) }; }
        stopPlay();
        const names = [...document.querySelectorAll('.player .pname')].map(e => e.textContent.trim());
        const fileItem = [...document.querySelectorAll('.meta-item')]
          .filter(e => (e.querySelector('.k') || {}).textContent === '来源文件')
          .map(e => e.querySelector('.v').textContent.trim())[0] || '';
        return { names, fileItem, steps: (window.replay && replay.moves ? replay.moves.length : -1) };
      }, b64, x);
    } catch (e) { r = { err: String(e.message).slice(0, 60) }; }
    rows.push({ file: x, kb: Math.round(sz / 1024), ...r });
  }
  await b.close();

  const bad = s => BAD.some(w => (s || '').includes(w));
  const ok = rows.filter(r => !r.err && r.steps >= 80 && !bad(r.file) && !r.names.some(bad));
  console.log('扫描 ' + rows.length + ' 份，其中干净且步数≥80 的 ' + ok.length + ' 份：\n');
  ok.sort((a, b) => b.steps - a.steps).slice(0, 12).forEach(r => {
    console.log('  ' + String(r.steps).padStart(4) + ' 步  ' + (r.kb + 'KB').padEnd(7) +
      r.names.join(' / ') + '\n        ' + r.file);
  });
  const rejected = rows.filter(r => r.err || bad(r.file) || r.names.some(bad));
  if (rejected.length) {
    console.log('\n剔掉的 ' + rejected.length + ' 份（含敏感字或被拒）：');
    rejected.slice(0, 15).forEach(r => {
      const why = r.err || (bad(r.file) ? '文件名' : '') + (r.names.some(bad) ? ' 玩家名:' + r.names.filter(bad) + '' : '');
      console.log('  ' + r.file.slice(0, 58) + '  →  ' + why);
    });
  }
})();
