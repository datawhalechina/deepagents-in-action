import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const manifest = JSON.parse(
  await readFile(new URL('./chapters.json', import.meta.url), 'utf8'),
);
const indexSource = await readFile(new URL('../src/pages/index.astro', import.meta.url), 'utf8');
const cardSource = await readFile(new URL('../src/components/ChapterCard.astro', import.meta.url), 'utf8');
const contentConfigSource = await readFile(new URL('../src/content.config.ts', import.meta.url), 'utf8');
const headingSource = await readFile(new URL('../src/components/PreviewSectionHeading.astro', import.meta.url), 'utf8')
  .catch(() => '');
const chapterExperimentSource = await readFile(
  new URL('../src/data/chapter-experiments.mjs', import.meta.url),
  'utf8',
);

test('Chapter 13 starts the preview-feature section', () => {
  assert.equal(manifest['ch13-grading-rubrics'].section, '前沿预览');
});

test('Chapter 13 publishes its video resource links', () => {
  assert.deepEqual(manifest['ch13-grading-rubrics'].slides[0], {
    id: 'ch13',
    title: 'Lec 17: Grading Rubrics — 让 Agent 按验收标准自我迭代',
    bilibili: 'https://www.bilibili.com/video/BV1t8bR6GEeU/',
    xhs: 'https://xhslink.cn/o/1JLNjLjjvpn',
  });
});

test('content schema accepts the preview-feature section', () => {
  assert.match(contentConfigSource, /'前沿预览'/);
});

test('homepage registers and renders the preview section', () => {
  assert.match(indexSource, /'前沿预览'/);
  assert.match(indexSource, /PreviewSectionHeading/);
  assert.match(headingSource, /PREVIEW · BETA/);
  assert.match(headingSource, /仍处于 Beta 或快速演进阶段的 Deep Agents 能力/);
});

test('preview chapter cards do not repeat the section status', () => {
  assert.doesNotMatch(cardSource, /预览特性/);
});

test('homepage keeps the experiment entry inside each chapter card', () => {
  assert.match(indexSource, /chapterExperiments/);
  assert.match(indexSource, /experiment=\{chapterExperiments\[ch\.id\]\}/);
  assert.match(cardSource, /本章实验/);
  assert.match(cardSource, /data-copy=\{experiment\.command\}/);
  assert.match(cardSource, /复制 AgentSeek 创建命令/);
  assert.doesNotMatch(cardSource, /改造底座/);
  assert.doesNotMatch(cardSource, /创建后/);
  assert.doesNotMatch(cardSource, /运行说明/);
  assert.doesNotMatch(indexSource, /TemplateLab/);
});

test('every published numbered chapter maps to exactly one current template command', async () => {
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');
  const publishedNumberedChapters = Object.entries(manifest)
    .filter(([id, chapter]) => id.startsWith('ch') && chapter.published)
    .map(([id]) => id)
    .sort();

  assert.deepEqual(Object.keys(chapterExperiments).sort(), publishedNumberedChapters);
  assert.equal(new Set(Object.keys(chapterExperiments)).size, 13);
  for (const experiment of Object.values(chapterExperiments)) {
    assert.match(experiment.command, /^agentseek create \S+ --checkout main --no-input$/);
    assert.match(experiment.source, /^https:\/\/github\.com\/agentseek-ai\/agentseek-templates\/tree\/main\/templates\//);
  }
  assert.match(chapterExperimentSource, /deepagents\/content-builder/);
  assert.match(chapterExperimentSource, /langchain\/rubric/);
});
