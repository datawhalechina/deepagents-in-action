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
  ...Array.from({ length: 4 }, (_, index) => ({
    login: `user${index}`,
    profileUrl: `https://github.com/user${index}`,
    avatarUrl: `https://avatars.githubusercontent.com/u/${index}?v=4&s=144`,
    contributions: 1,
  })),
];

test('builds a four-column contributor wall with breakable long names', () => {
  const wall = buildWall(contributors);

  assert.equal((wall.match(/<tr>/g) ?? []).length, 2);
  assert.equal((wall.match(/width="25%"/g) ?? []).length, contributors.length);
  assert.match(wall, /code<wbr>Monkey<wbr>Wang/);
});
