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

// Aggregate contributors from the commits API rather than the /contributors
// stats endpoint. The latter is cached/eventually-consistent: after pushes it
// can return a transitional snapshot that omits real contributors or surfaces
// bots, which would silently drop people from the wall. Tallying commit authors
// is authoritative and real-time.
async function fetchContributors(repoSlug) {
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'deepagents-in-action-contributor-wall',
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const byLogin = new Map();
  let page = 1;

  while (true) {
    const url = `https://api.github.com/repos/${repoSlug}/commits?per_page=100&page=${page}`;
    const response = await fetch(url, { headers });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`GitHub API ${response.status} ${response.statusText}: ${body}`);
    }

    const pageItems = await response.json();
    if (!Array.isArray(pageItems) || pageItems.length === 0) {
      break;
    }

    for (const commit of pageItems) {
      const author = commit?.author;
      // Skip commits with no linked GitHub user (e.g. unmatched email) and bots.
      if (!author?.login || author.type !== 'User') {
        continue;
      }

      const existing = byLogin.get(author.login);
      if (existing) {
        existing.contributions += 1;
      } else {
        byLogin.set(author.login, {
          login: author.login,
          profileUrl: author.html_url,
          avatarUrl: `${author.avatar_url}&s=144`,
          contributions: 1,
        });
      }
    }

    page += 1;
  }

  return [...byLogin.values()].sort(
    (a, b) => b.contributions - a.contributions || a.login.localeCompare(b.login),
  );
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
