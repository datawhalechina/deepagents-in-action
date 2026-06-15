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
  {
    login: 'xschen-beb',
    profileUrl: 'https://github.com/xschen-beb',
    avatarUrl: 'https://avatars.githubusercontent.com/u/61721839?v=4&s=144',
    contributions: 1,
  },
  ...Array.from({ length: 6 }, (_, index) => ({
    login: `user${index}`,
    profileUrl: `https://github.com/user${index}`,
    avatarUrl: `https://avatars.githubusercontent.com/u/${index}?v=4&s=144`,
    contributions: 1,
  })),
];

test('builds eight equal columns with abbreviated clickable keycap names', () => {
  const wall = buildWall(contributors);

  assert.equal((wall.match(/<tr>/g) ?? []).length, 1);
  assert.equal((wall.match(/width="104"/g) ?? []).length, contributors.length);
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/codeMonkeyWang" title="codeMonkeyWang">\s+<img[^>]+>\s+<\/a><br \/>\s+<a href="https:\/\/github\.com\/codeMonkeyWang" title="打开 codeMonkeyWang 的 GitHub 主页"><kbd><strong>codeMonkeyW…<\/strong><\/kbd><\/a>/,
  );
  assert.match(
    wall,
    /<a href="https:\/\/github\.com\/user0" title="user0">\s+<img[^>]+>\s+<\/a><br \/>\s+<a href="https:\/\/github\.com\/user0" title="打开 user0 的 GitHub 主页"><kbd><strong>user0<\/strong><\/kbd><\/a>/,
  );
  assert.doesNotMatch(wall, /主页 ↗/);
  assert.doesNotMatch(wall, /<samp>|&#160;/);
});

test('keeps hyphenated names on one line via a non-breaking hyphen', () => {
  const wall = buildWall(contributors);

  // Displayed keycap uses U+2011 (non-breaking hyphen), not ASCII "-".
  assert.match(wall, /<kbd><strong>xschen‑beb<\/strong><\/kbd>/);
  // ...while the title/href/alt keep the real ASCII login intact.
  assert.match(wall, /title="xschen-beb"/);
  assert.match(wall, /href="https:\/\/github\.com\/xschen-beb"/);
});
