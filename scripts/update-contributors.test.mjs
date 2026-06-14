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

test('builds eight equal columns with abbreviated clickable names', () => {
  const wall = buildWall(contributors);

  assert.equal((wall.match(/<tr>/g) ?? []).length, 1);
  assert.equal((wall.match(/width="12.5%"/g) ?? []).length, contributors.length);
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/codeMonkeyWang" title="codeMonkeyWang">\s+<img[^>]+><br \/>\s+<sub><strong>codeMon…<\/strong><\/sub>\s+<\/a>/,
  );
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/user0" title="user0">\s+<img[^>]+><br \/>\s+<sub><strong>user0<\/strong><\/sub>\s+<\/a>/,
  );
});
