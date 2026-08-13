import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const workflowPath = fileURLToPath(
  new URL('../.github/workflows/cross-platform-install.yml', import.meta.url),
);
const workflow = existsSync(workflowPath)
  ? readFileSync(workflowPath, 'utf8')
  : '';
const contributingPath = fileURLToPath(
  new URL('../CONTRIBUTING.md', import.meta.url),
);
const contributing = readFileSync(contributingPath, 'utf8');

test('cross-platform installation workflow is manual-only', () => {
  assert.match(workflow, /^on:\n\s+workflow_dispatch:\s*$/m);
  assert.doesNotMatch(workflow, /^\s+(push|pull_request|schedule):/m);
  assert.match(workflow, /contents: read/);
});

test('workflow keeps all three platform runs independent', () => {
  for (const runner of ['ubuntu-latest', 'macos-latest', 'windows-latest']) {
    assert.match(workflow, new RegExp(`os: ${runner}`));
  }
  assert.match(workflow, /WSL2 equivalent/);
  assert.match(workflow, /fail-fast: false/);
  assert.match(workflow, /timeout-minutes: 30/);
});

test('workflow installs and verifies the official uv and LangSmith CLIs', () => {
  for (const expected of [
    'https://astral.sh/uv/install.sh',
    'https://astral.sh/uv/install.ps1',
    'https://cli.langsmith.com/install.sh',
    'https://cli.langsmith.com/install.ps1',
    'shell: powershell',
    'uv --version',
    'uvx --version',
    'langsmith --version',
  ]) {
    assert.match(workflow, new RegExp(expected.replaceAll('.', '\\.')));
  }
});

test('every platform installs and validates the course site', () => {
  for (const expected of [
    "node-version: '22.12.0'",
    'npm ci',
    'npm run ci:test',
    'npm run docs:test',
    'npm run assets:test',
    'npm run assets:check',
    'npm run build',
  ]) {
    assert.match(workflow, new RegExp(expected.replaceAll('.', '\\.')));
  }
});

test('maintainers are told how and when to run cross-platform installation checks', () => {
  for (const expected of [
    'Cross-platform installation',
    'workflow_dispatch',
    '默认分支',
    'WSL2',
    'ubuntu-latest',
  ]) {
    assert.match(contributing, new RegExp(expected));
  }
});
