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

test('Chapter 13 starts the preview-feature section', () => {
  assert.equal(manifest['ch13-grading-rubrics'].section, '前沿预览');
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

test('preview chapter cards carry a text status badge', () => {
  assert.match(cardSource, /section === '前沿预览'/);
  assert.match(cardSource, /预览特性/);
});
