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
