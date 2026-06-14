import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { buildWall } from './contributor-wall.mjs';

const rootDir = resolve(import.meta.dirname, '..');
const readmePath = resolve(rootDir, 'README.md');
const markerStart = '<!-- contributors:start -->';
const markerEnd = '<!-- contributors:end -->';

function resolveRepoSlug() {
  if (process.env.GITHUB_REPOSITORY) {
    return process.env.GITHUB_REPOSITORY;
  }

  const remote = execFileSync('git', ['remote', 'get-url', 'origin'], {
    cwd: rootDir,
    encoding: 'utf8',
  }).trim();

  const match = remote.match(/github\.com[:/](.+?)(?:\.git)?$/);
  if (!match) {
    throw new Error(`Unable to infer GitHub repository from remote: ${remote}`);
  }

  return match[1];
}

async function fetchContributors(repoSlug) {
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'deepagents-in-action-contributor-wall',
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const contributors = [];
  let page = 1;

  while (true) {
    const url = `https://api.github.com/repos/${repoSlug}/contributors?per_page=100&page=${page}`;
    const response = await fetch(url, { headers });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`GitHub API ${response.status} ${response.statusText}: ${body}`);
    }

    const pageItems = await response.json();
    if (!Array.isArray(pageItems) || pageItems.length === 0) {
      break;
    }

    contributors.push(...pageItems);
    page += 1;
  }

  return contributors
    .filter((item) => item?.type === 'User' && item?.login)
    .map((item) => ({
      login: item.login,
      profileUrl: item.html_url,
      avatarUrl: `${item.avatar_url}&s=144`,
      contributions: item.contributions ?? 0,
    }))
    .sort((a, b) => b.contributions - a.contributions || a.login.localeCompare(b.login));
}

function updateReadme(wallMarkup) {
  const readme = readFileSync(readmePath, 'utf8');
  const pattern = new RegExp(`${markerStart}[\\s\\S]*?${markerEnd}`);

  if (!pattern.test(readme)) {
    throw new Error('Contributor wall markers were not found in README.md');
  }

  const next = readme.replace(pattern, wallMarkup);
  if (next !== readme) {
    writeFileSync(readmePath, next);
  }
}

const repoSlug = resolveRepoSlug();
const contributors = await fetchContributors(repoSlug);
const wallMarkup = buildWall(contributors);
updateReadme(wallMarkup);
