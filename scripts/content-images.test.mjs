import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  extractContentImageReferences,
  rewriteContentImagePaths,
  validateContentImageReferences,
} from './content-images.mjs';

test('rewriteContentImagePaths adds the site base and preserves image titles', () => {
  const markdown = [
    '![架构图](../public/imgs/architecture.png "架构")',
    '![外部图片](https://example.com/image.png)',
  ].join('\n');

  assert.equal(
    rewriteContentImagePaths(markdown, '/deepagents-in-action'),
    [
      '![架构图](/deepagents-in-action/imgs/architecture.png "架构")',
      '![外部图片](https://example.com/image.png)',
    ].join('\n'),
  );
});

test('extractContentImageReferences returns authored public image paths', () => {
  const markdown = [
    '![第一张](../public/imgs/first.png)',
    '![第二张](../public/imgs/diagrams/second.jpg)',
    '![外部图片](https://example.com/image.png)',
  ].join('\n');

  assert.deepEqual(extractContentImageReferences(markdown), [
    { sourcePath: '../public/imgs/first.png', publicRelativePath: 'imgs/first.png' },
    { sourcePath: '../public/imgs/diagrams/second.jpg', publicRelativePath: 'imgs/diagrams/second.jpg' },
  ]);
});

test('validateContentImageReferences reports the markdown file and missing asset', async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'content-images-'));
  t.after(() => rm(root, { recursive: true, force: true }));

  const contentDir = path.join(root, 'content');
  const publicDir = path.join(root, 'public');
  await mkdir(path.join(contentDir, 'nested'), { recursive: true });
  await mkdir(path.join(publicDir, 'imgs'), { recursive: true });
  await writeFile(path.join(publicDir, 'imgs', 'exists.png'), 'fixture');
  await writeFile(
    path.join(contentDir, 'nested', 'chapter.md'),
    [
      '![存在](../public/imgs/exists.png)',
      '![缺失](../public/imgs/missing.png)',
    ].join('\n'),
  );

  assert.deepEqual(await validateContentImageReferences({ contentDir, publicDir }), {
    referenceCount: 2,
    errors: [
      `${path.join('nested', 'chapter.md')}: ../public/imgs/missing.png points to missing public/imgs/missing.png`,
    ],
  });
});
