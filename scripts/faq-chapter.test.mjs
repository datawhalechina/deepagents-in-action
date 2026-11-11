import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import test, { before } from 'node:test';

const root = new URL('../', import.meta.url);
const faqPath = new URL('../dist/chapters/pre03-task1-faq/index.html', import.meta.url);
const readBuilt = (path) => readFileSync(new URL(`../dist/${path}`, import.meta.url), 'utf8');

before(() => {
  const command = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const result = spawnSync(command, ['run', 'build'], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, `site build failed:\n${result.stdout}\n${result.stderr}`);
});

test('FAQ is published as an unnumbered preparation chapter', () => {
  assert.equal(existsSync(faqPath), true, 'The FAQ route must be generated');
  const page = readFileSync(faqPath, 'utf8');
  assert.match(page, /<h1[^>]*>\s*叶静的学习笔记\s*<\/h1>/);
  assert.doesNotMatch(page, /EP\.00|第 0 章|\/pdfs\/pre03-task1-faq/);
});

test('FAQ is reachable from the homepage card and mobile directory without changing the course count', () => {
  const page = readBuilt('index.html');
  assert.match(page, /id="ch-pre03-task1-faq"/);
  assert.match(page, /href="\/deepagents-in-action\/chapters\/pre03-task1-faq\/"/);
  assert.match(page, /data-rail-target="ch-pre03-task1-faq"/);
  assert.match(page, /已发布 17 章/);
});

test('FAQ participates in previous and next chapter navigation', () => {
  assert.equal(existsSync(faqPath), true, 'The FAQ route must be generated');
  const faq = readFileSync(faqPath, 'utf8');
  for (const id of ['pre02-agentseek-skills', 'ch07-skills']) {
    assert.ok(faq.includes(`/deepagents-in-action/chapters/${id}/`));
    assert.ok(readBuilt(`chapters/${id}/index.html`).includes('/deepagents-in-action/chapters/pre03-task1-faq/'));
  }
});

test('every FAQ contents link and authored fragment resolves to a unique heading', () => {
  assert.equal(existsSync(faqPath), true, 'The FAQ route must be generated');
  const page = readFileSync(faqPath, 'utf8');
  const headings = [...page.matchAll(/<h[23]\s+[^>]*id="([^"]+)"/g)].map(match => match[1]);
  assert.ok(headings.length > 15, 'Grouped FAQ questions must be visible in the contents');
  assert.equal(new Set(headings).size, headings.length);
  const fragments = [...page.matchAll(/href="#([^"]+)"/g)].map(match => decodeURIComponent(match[1]));
  assert.ok(fragments.length > 0);
  const ids = [...page.matchAll(/\sid="([^"]+)"/g)].map(match => match[1]);
  for (const fragment of fragments) assert.ok(ids.includes(fragment), `Missing FAQ target: ${fragment}`);
});


test('FAQ is named for Ye Jing throughout page metadata, directory cards and adjacent navigation', () => {
  const manifest = JSON.parse(readFileSync(new URL('./chapters.json', import.meta.url), 'utf8'));
  assert.equal(manifest['pre03-task1-faq'].title, '叶静的学习笔记');
  const faq = readFileSync(faqPath, 'utf8');
  assert.match(faq, /<title>叶静的学习笔记 — Deep Agents 实战<\/title>/);
  for (const path of ['index.html', 'chapters/pre01-agentseek-create/index.html', 'chapters/pre02-agentseek-skills/index.html', 'chapters/ch07-skills/index.html']) {
    const page = readBuilt(path);
    assert.ok(page.includes('叶静的学习笔记'), `${path} shows the course-wide title`);
    assert.ok(!page.includes('Task1 常见问题与排障'), `${path} must not scope the FAQ title to Task1`);
  }
  const source = readFileSync(new URL('../content/pre03-task1-faq.md', import.meta.url), 'utf8');
  assert.match(source, /^# 叶静的学习笔记/);
  assert.match(source, /Q1：Task1 到底要完成什么/);
  assert.match(readFileSync(new URL('../README.md', import.meta.url), 'utf8'), /\[叶静的学习笔记\]/);
});


test('FAQ visibly credits Ye Jing and yejing8011 as its content contributor', () => {
  const faq = readFileSync(faqPath, 'utf8');
  assert.match(faq, /本章 FAQ 内容由\s*<strong>叶静（yejing8011）<\/strong>\s*贡献/);
  const readme = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
  assert.ok(readme.includes('由叶静（yejing8011）贡献'));
  const manifest = JSON.parse(readFileSync(new URL('./chapters.json', import.meta.url), 'utf8'));
  assert.ok(manifest['pre03-task1-faq'].description.includes('叶静（yejing8011）'));
});
