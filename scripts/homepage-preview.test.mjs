import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const manifest = JSON.parse(
  await readFile(new URL('./chapters.json', import.meta.url), 'utf8'),
);
const indexSource = await readFile(new URL('../src/pages/index.astro', import.meta.url), 'utf8');
const cardSource = await readFile(new URL('../src/components/ChapterCard.astro', import.meta.url), 'utf8');
const contentConfigSource = await readFile(new URL('../src/content.config.ts', import.meta.url), 'utf8');
const chapterLayoutSource = await readFile(
  new URL('../src/layouts/ChapterLayout.astro', import.meta.url),
  'utf8',
);
const headingSource = await readFile(new URL('../src/components/PreviewSectionHeading.astro', import.meta.url), 'utf8')
  .catch(() => '');
const chapterExperimentSource = await readFile(
  new URL('../src/data/chapter-experiments.mjs', import.meta.url),
  'utf8',
);
const streamingChapterSource = await readFile(
  new URL('../content/ch14-streaming.md', import.meta.url),
  'utf8',
);
const readmeSource = await readFile(new URL('../README.md', import.meta.url), 'utf8');

test('Chapters 13 through 16 share the preview-feature row', () => {
  assert.equal(manifest['ch13-grading-rubrics'].section, '前沿预览');
  assert.equal(manifest['ch14-streaming'].section, '前沿预览');
  assert.equal(manifest['ch15-interpreters'].section, '前沿预览');
  assert.equal(manifest['ch16-dynamic-subagents'].section, '前沿预览');
  assert.equal(
    manifest['ch14-streaming'].order,
    manifest['ch13-grading-rubrics'].order + 1,
  );
  assert.equal(
    manifest['ch15-interpreters'].order,
    manifest['ch14-streaming'].order + 1,
  );
  assert.equal(
    manifest['ch16-dynamic-subagents'].order,
    manifest['ch15-interpreters'].order + 1,
  );
});

test('README places Chapters 13 through 16 together in the preview section', () => {
  let currentSection = '';
  const chapters = [];

  for (const line of readmeSource.split(/\r?\n/)) {
    const sectionMatch = line.match(/^### (.+)$/);
    if (sectionMatch) currentSection = sectionMatch[1];

    const chapterMatch = line.match(/^#### 第 (\d+) 章：/);
    if (chapterMatch) {
      chapters.push({ chapter: Number(chapterMatch[1]), section: currentSection });
    }
  }

  assert.deepEqual(
    chapters.filter(({ section }) => section === '前沿预览').map(({ chapter }) => chapter),
    [13, 14, 15, 16],
  );
  assert.equal(chapters.filter(({ chapter }) => chapter === 14).length, 1);
  assert.equal(chapters.filter(({ chapter }) => chapter === 15).length, 1);
  assert.equal(chapters.filter(({ chapter }) => chapter === 16).length, 1);
});

test('Chapter 13 publishes its video resource links', () => {
  assert.deepEqual(manifest['ch13-grading-rubrics'].slides[0], {
    id: 'ch13',
    title: 'Lec 17: Grading Rubrics — 让 Agent 按验收标准自我迭代',
    bilibili: 'https://www.bilibili.com/video/BV1t8bR6GEeU/',
    xhs: 'https://xhslink.cn/o/1JLNjLjjvpn',
  });
});

test('Chapter 14 publishes its video resource links', () => {
  assert.deepEqual(manifest['ch14-streaming'].slides[0], {
    id: 'ch14',
    title: 'Lec 18: Streaming — 实时观察智能体和工具',
    bilibili: 'https://www.bilibili.com/video/BV1qt8A61ELE/',
    xhs: 'https://xhslink.cn/o/6uKY9nP8GLk',
  });
  assert.match(chapterLayoutSource, /bilibili \|\| xhs \|\| slides\.some/);
  assert.match(cardSource, /slides && slides\.length > 0 && \(/);
});

test('Chapter 15 publishes its video resource links', () => {
  assert.deepEqual(manifest['ch15-interpreters'].slides[0], {
    id: 'ch15',
    title: 'Lec 19: Interpreters — 让 Agent 用代码编排工具与数据',
    bilibili: 'https://www.bilibili.com/video/BV1DAh36fEWJ/',
    xhs: 'https://xhslink.cn/o/7nkz9WmQ00W',
  });
});

test('Chapter 14 keeps recommended v3 projections separate from v2 protocol streaming', () => {
  assert.match(streamingChapterSource, /stream_events\(request, version="v3"\)/);
  assert.match(streamingChapterSource, /stream\.subagents/);
  assert.match(streamingChapterSource, /stream\.tool_calls/);
  assert.match(streamingChapterSource, /stream\.interleave/);
  for (const field of [
    'name',
    'path',
    'status',
    'messages',
    'tool_calls',
    'values',
    'subagents',
    'output',
    'tool_name',
    'output_deltas',
    'completed',
    'error',
  ]) {
    assert.match(streamingChapterSource, new RegExp(`\\| \\\`${field}\\\` \\|`));
  }
  assert.match(streamingChapterSource, /stream_mode=\["updates", "messages", "custom"\]/);
  assert.match(streamingChapterSource, /subgraphs=True/);
  assert.match(streamingChapterSource, /version="v2"/);
});

test('Chapter 14 points readers to the dedicated streaming template', async () => {
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');

  assert.deepEqual(chapterExperiments['ch14-streaming'], {
    template: 'deepagents/streaming',
    note: '运行 Streaming 模板，观察 Agent 与工具事件流。',
    command: 'agentseek create deepagents/streaming --checkout main --no-input',
    source: 'https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/streaming',
  });
});

test('Chapter 15 publishes its PDF without invented experiment metadata', async () => {
  const chapter = manifest['ch15-interpreters'];
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');

  assert.equal(chapter.chapter, 15);
  assert.equal(chapter.section, '前沿预览');
  assert.equal(chapter.published, true);
  assert.equal(chapterExperiments['ch15-interpreters'], undefined);
});

test('Chapter 16 publishes its PDF and uses the dynamic subagents template', async () => {
  const chapter = manifest['ch16-dynamic-subagents'];
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');

  assert.equal(chapter.chapter, 16);
  assert.equal(chapter.section, '前沿预览');
  assert.deepEqual(chapter.slides, [{
    id: 'ch16',
    title: 'Lec 20: Dynamic Subagents — 用代码编排多个 Agent',
  }]);
  assert.equal(chapter.published, true);
  assert.deepEqual(chapterExperiments['ch16-dynamic-subagents'], {
    template: 'deepagents/subagents-dynamic',
    note: '运行六种 Dynamic Subagents 编排模式。',
    command: 'agentseek create deepagents/subagents-dynamic --checkout main --no-input',
    source: 'https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/subagents-dynamic',
  });

  const readmeBlock = readmeSource.slice(
    readmeSource.indexOf('#### 第 16 章：'),
    readmeSource.indexOf('后续课程内容将根据'),
  );
  assert.match(readmeBlock, /templates\/deepagents\/subagents-dynamic/);
  assert.match(readmeBlock, /agentseek create deepagents\/subagents-dynamic --checkout main --no-input/);
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

test('homepage experiment descriptions stay concise', async () => {
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');

  for (const [chapterId, experiment] of Object.entries(chapterExperiments)) {
    assert.ok(
      [...experiment.note].length <= 36,
      `${chapterId} experiment note exceeds 36 characters`,
    );
    assert.doesNotMatch(experiment.note, /[\r\n]/);
  }
});

test('every declared chapter experiment targets a published numbered chapter', async () => {
  const { chapterExperiments } = await import('../src/data/chapter-experiments.mjs');
  const publishedNumberedChapters = new Set(Object.entries(manifest)
    .filter(([id, chapter]) => id.startsWith('ch') && chapter.published)
    .map(([id]) => id));

  for (const [chapterId, experiment] of Object.entries(chapterExperiments)) {
    assert.equal(publishedNumberedChapters.has(chapterId), true);
    assert.match(experiment.command, /^agentseek create \S+ --checkout main --no-input$/);
    assert.match(experiment.source, /^https:\/\/github\.com\/agentseek-ai\/agentseek-templates\/tree\/main\/templates\//);
  }
  assert.match(chapterExperimentSource, /deepagents\/content-builder/);
  assert.match(chapterExperimentSource, /langchain\/rubric/);
  assert.match(chapterExperimentSource, /ch14-streaming/);
});
