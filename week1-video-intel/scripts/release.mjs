import { access, copyFile, cp, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { build } from 'vite';

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const stageRoot = join(appRoot, '.release-dist');
process.env.NFL_VIDEO_INTEL_RELEASE = '1';

await build({ configFile: join(appRoot, 'vite.config.mjs') });

for (const required of ['index.html', 'assets/app.js', 'assets/app.css', 'data/manifest.json', 'data/2026/week-01.json']) {
  await access(join(stageRoot, required));
}

await mkdir(join(appRoot, 'assets'), { recursive: true });
await mkdir(join(appRoot, 'data'), { recursive: true });
await copyFile(join(stageRoot, 'index.html'), join(appRoot, 'index.html'));
await cp(join(stageRoot, 'assets'), join(appRoot, 'assets'), { recursive: true, force: true });
await cp(join(stageRoot, 'data'), join(appRoot, 'data'), { recursive: true, force: true });

process.stdout.write('Released index.html, assets/, and production data/ from an isolated staging build.\n');
