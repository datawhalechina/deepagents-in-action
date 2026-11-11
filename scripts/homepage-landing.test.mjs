import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import test, { before } from 'node:test';

let homepage;
const root = new URL('../', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('./chapters.json', import.meta.url), 'utf8'));
before(() => {
  const result = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], {
    cwd: root, encoding: 'utf8',
  });
  assert.equal(result.status, 0, `site build failed:\n${result.stdout}\n${result.stderr}`);
  homepage = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
});

test('beginner route links to three published chapters in learning order', () => {
  const route = homepage.match(/<ol\b[^>]*class="learning-route__steps"[^>]*>([\s\S]*?)<\/ol>/)?.[1];
  assert.ok(route, 'an ordered learning route is visible');
  const ids = [...route.matchAll(/href="\/deepagents-in-action\/chapters\/([^/]+)\/"/g)].map(match => match[1]);
  assert.deepEqual(ids, ['pre01-agentseek-create', 'ch01-agent-harness', 'ch02-quickstart']);
  for (const id of ids) assert.equal(manifest[id]?.published, true);
});

test('homepage provides a keyboard skip target and a course-directory anchor', () => {
  assert.match(homepage, /class="landing-skip-link"[^>]*href="#main-content"|href="#main-content"[^>]*class="landing-skip-link"/);
  assert.match(homepage, /<main[^>]*id="main-content"[^>]*tabindex="-1"/);
  assert.match(homepage, /href="#course-chapters"/);
  assert.match(homepage, /id="course-chapters"/);
});

test('polished hero preserves course identity, version, author and resource destinations', () => {
  const hero = homepage.match(/<section\b[^>]*class="course-hero"[^>]*>([\s\S]*?)<\/section>/)?.[1];
  assert.ok(hero, 'the course hero is rendered');
  assert.equal((homepage.match(/<h1\b/g) ?? []).length, 1);
  for (const copy of ['Deep Agents', '实战', '0.5 起步 · 当前基线 0.7', '沧海九粟', 'LangChain 官方大使', 'SiliconFlow', '开始阅读']) {
    assert.ok(hero.includes(copy), `${copy} remains available`);
  }
  for (const url of ['https://space.bilibili.com/28357052/lists/7757577?type=season', 'https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001', 'https://github.com/datawhalechina/deepagents-in-action', 'https://cloud.siliconflow.cn/i/Fq9zUwPf']) {
    assert.ok(hero.includes(url), `${url} remains available`);
  }
  assert.match(hero, /id="gh-star-count"/);
  assert.match(hero, /href="\/deepagents-in-action\/chapters\/ch01-agent-harness\/"/);
});

test('hero images reserve space and decorative icons are hidden from assistive technology', () => {
  const hero = homepage.match(/<section\b[^>]*class="course-hero"[^>]*>([\s\S]*?)<\/section>/)?.[1];
  assert.ok(hero);
  for (const tag of hero.match(/<img\b[^>]*>/g) ?? []) {
    assert.match(tag, /\bwidth="\d+"/);
    assert.match(tag, /\bheight="\d+"/);
    assert.match(tag, /\balt="[^"]*"/);
  }
  for (const tag of hero.match(/<svg\b[^>]*>/g) ?? []) assert.match(tag, /aria-hidden="true"/);
});

test('beginner route offers the published FAQ when setup or learning order is unclear', () => {
  const route = homepage.match(/<aside\b[^>]*class="learning-route"[^>]*>([\s\S]*?)<\/aside>/)?.[1];
  assert.ok(route);
  assert.match(route, /href="\/deepagents-in-action\/chapters\/pre03-task1-faq\/"/);
  assert.match(route, /叶静的 FAQ/);
  assert.equal(manifest['pre03-task1-faq']?.published, true);
});


test('shared header uses the course logo without repeating its accessible link name', () => {
  for (const path of ['index.html', 'chapters/pre03-task1-faq/index.html']) {
    const page = readFileSync(new URL(`../dist/${path}`, import.meta.url), 'utf8');
    const header = page.match(/<header[^>]*>[\s\S]*?<\/header>/)?.[0];
    assert.ok(header);
    const logo = header.match(/<img[^>]*src="\/deepagents-in-action\/imgs\/course-logo\.svg"[^>]*>/)?.[0];
    assert.ok(logo, `${path} uses the original course mark`);
    assert.match(logo, /alt=""/);
    assert.match(logo, /width="32"/);
    assert.match(logo, /height="32"/);
    assert.ok(header.includes('Deep Agents 实战'));
  }
});

test('standalone SVG and favicon share a self-contained accessible vector mark', () => {
  assert.ok(existsSync(new URL('../public/imgs/course-logo.svg', import.meta.url)), 'standalone course logo exists');
  const logo = readFileSync(new URL('../public/imgs/course-logo.svg', import.meta.url), 'utf8');
  const favicon = readFileSync(new URL('../public/favicon.svg', import.meta.url), 'utf8');
  assert.equal(logo, favicon);
  assert.match(logo, /viewBox="0 0 64 64"/);
  assert.match(logo, /role="img"/);
  assert.match(logo, /aria-labelledby="course-logo-title course-logo-desc"/);
  assert.match(logo, /<title id="course-logo-title">Deep Agents 实战<\/title>/);
  assert.match(logo, /<desc id="course-logo-desc">[^<]+<\/desc>/);
  assert.doesNotMatch(logo, /<(?:image|script|foreignObject)\b|(?:href|src)="https?:/);
  assert.ok(Buffer.byteLength(logo) < 3000, 'the mark stays lightweight');
});
