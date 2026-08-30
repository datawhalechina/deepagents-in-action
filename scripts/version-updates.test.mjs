import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import test, { before } from 'node:test';

const root = new URL('../', import.meta.url);
const chapters = JSON.parse(
  readFileSync(new URL('./chapters.json', import.meta.url), 'utf8'),
);
const publishedCourseChapterCount = Object.entries(chapters).filter(
  ([id, chapter]) => id.startsWith('ch') && chapter.published,
).length;
const releaseGuide = readFileSync(
  new URL('../content/release-v0-7.md', import.meta.url),
  'utf8',
);
const mcpChapter = readFileSync(
  new URL('../content/ch12-mcp.md', import.meta.url),
  'utf8',
);

before(() => {
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const result = spawnSync(npmCommand, ['run', 'build'], {
    cwd: root,
    encoding: 'utf8',
  });

  assert.equal(
    result.status,
    0,
    `site build failed:\n${result.stdout}\n${result.stderr}`,
  );
});

test('homepage renders v0.7 in a dedicated release section without changing the course count', () => {
  const homepage = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

  assert.match(homepage, /id="sec-版本更新"/);
  assert.match(homepage, />版本更新</);
  assert.match(homepage, /href="\/deepagents-in-action\/chapters\/release-v0-7\/"/);
  assert.match(homepage, /chapter-num--release[^>]*>v0\.7</);
  assert.match(
    homepage,
    new RegExp(`已发布 ${publishedCourseChapterCount} 章`),
  );
});

test('homepage positions 0.5 as the course origin and 0.7 as the current baseline', () => {
  const homepage = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');

  assert.match(homepage, /0\.5 起步 · 当前基线 0\.7/);
  assert.match(homepage, /从 0\.5 \/ 0\.6 迁移到当前 0\.7 基线/);
  assert.doesNotMatch(homepage, /Deep Agents SDK ≥ 0\.5/);
  assert.match(chapters['release-v0-7'].description, /从 0\.5、0\.6 一路跟学/);
  assert.match(chapters['ch03-virtual-filesystem'].description, /v0\.7 的七个文件工具/);
  assert.match(chapters['ch04-task-planning'].description, /按需启用 TodoListMiddleware/);
});

test('v0.7 release page uses release metadata instead of numbered-chapter metadata', () => {
  const page = readFileSync(
    new URL('../dist/chapters/release-v0-7/index.html', import.meta.url),
    'utf8',
  );

  assert.match(page, /Deep Agents v0\.7：更轻、更透明、更可配置的 Harness/);
  assert.match(page, />\s*版本更新\s*</);
  assert.match(page, />\s*v0\.7\s*</);
  assert.doesNotMatch(page, /第 0 章/);
  assert.doesNotMatch(page, /EP\.00/);
});

test('general v0.7 install guidance follows current patches within the minor release', () => {
  assert.match(releaseGuide, /uv add --upgrade "deepagents>=0\.7,<0\.8"/);
  assert.match(releaseGuide, /uv add "deepagents==0\.7\.0"/);
  assert.match(mcpChapter, /deepagents>=0\.7,<0\.8/);
  assert.doesNotMatch(mcpChapter, /deepagents==0\.7\.8/);
});

test('v0.7 update card publishes the PDF and reserves future social links', () => {
  const slide = chapters['release-v0-7'].slides[0];

  assert.deepEqual(slide, {
    id: 'release-v0-7',
    title: 'Deep Agents v0.7 版本更新',
  });
  assert.equal(existsSync(new URL('../public/pdfs/release-v0-7.pdf', import.meta.url)), true);

  const homepage = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
  const releaseCard = homepage.slice(
    homepage.indexOf('Deep Agents v0.7 版本更新'),
    homepage.indexOf('id="sec-认知篇"'),
  );

  assert.match(releaseCard, /href="\/deepagents-in-action\/pdfs\/release-v0-7\.pdf"/);
  assert.match(releaseCard, /<span[^>]*>[\s\S]*?B站[\s\S]*?<\/span>/);
  assert.match(releaseCard, /<span[^>]*>[\s\S]*?小红书[\s\S]*?<\/span>/);
  assert.doesNotMatch(releaseCard, /href="[^"]*(?:bilibili|xiaohongshu|xhslink)/);
});
