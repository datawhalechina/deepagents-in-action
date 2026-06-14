import assert from 'node:assert/strict';
import test from 'node:test';

import { buildWall } from './contributor-wall.mjs';

const contributors = [
  {
    login: 'codeMonkeyWang',
    profileUrl: 'https://github.com/codeMonkeyWang',
    avatarUrl: 'https://avatars.githubusercontent.com/u/3906539?v=4&s=144',
    contributions: 1,
  },
  ...Array.from({ length: 7 }, (_, index) => ({
    login: `user${index}`,
    profileUrl: `https://github.com/user${index}`,
    avatarUrl: `https://avatars.githubusercontent.com/u/${index}?v=4&s=144`,
    contributions: 1,
  })),
];

test('builds eight equal columns with abbreviated names and profile key links', () => {
  const wall = buildWall(contributors);

  assert.equal((wall.match(/<tr>/g) ?? []).length, 1);
  assert.equal((wall.match(/width="104"/g) ?? []).length, contributors.length);
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/codeMonkeyWang" title="codeMonkeyWang">\s+<img[^>]+>\s+<\/a><br \/>\s+<sub><strong title="codeMonkeyWang">codeMon…<\/strong><\/sub><br \/>\s+<a href="https:\/\/github\.com\/codeMonkeyWang" title="打开 codeMonkeyWang 的 GitHub 主页"><kbd>主页 ↗<\/kbd><\/a>/,
  );
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/user0" title="user0">\s+<img[^>]+>\s+<\/a><br \/>\s+<sub><strong title="user0">user0<\/strong><\/sub><br \/>\s+<a href="https:\/\/github\.com\/user0" title="打开 user0 的 GitHub 主页"><kbd>主页 ↗<\/kbd><\/a>/,
  );
  assert.doesNotMatch(wall, /<samp>|&#160;/);
});
