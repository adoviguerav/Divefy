// Frame-by-frame capture of showreel.html with headless Chromium.
//   node render.mjs stills 1.8 5.3 12.4      -> stills/t_<t>.png
//   node render.mjs video out.mp4 [fps] [first last]  -> silent H.264 via ffmpeg (stdin pipe);
//                                                        first/last re-render only a frame range
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium';
const [mode, ...args] = process.argv.slice(2);

const browser = await chromium.launch({ executablePath: CHROME, args: ['--font-render-hinting=none', '--disable-lcd-text'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('pageerror:', e.message));
await page.goto('file://' + path.join(here, 'showreel.html') + '?render=1');
await page.waitForFunction(() => window.READY === true);

if (mode === 'stills') {
  mkdirSync(path.join(here, 'stills'), { recursive: true });
  for (const t of args.map(Number)) {
    await page.evaluate((tt) => window.renderFrame(tt), t);
    await page.screenshot({ path: path.join(here, 'stills', `t_${t.toFixed(2)}.png`) });
  }
} else if (mode === 'video') {
  const out = args[0] || 'silent.mp4', fps = Number(args[1] || 60), dur = 20;
  const ff = spawn(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-pix_fmt', 'yuv420p', '-tune', 'animation', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round(fps * dur), t0 = Date.now();
  const first = Number(args[2] || 0), last = Number(args[3] || n);
  for (let i = first; i < last; i++) {
    await page.evaluate((tt) => window.renderFrame(tt), i / fps);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await once(ff.stdin, 'drain');
    if (i % 120 === 0) console.log(`frame ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await once(ff, 'close');
  console.log('done', out);
}
await browser.close();
