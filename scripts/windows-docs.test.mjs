import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

async function readMarkdown(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), 'utf8');
}

function assertContainsAll(markdown, snippets) {
  for (const snippet of snippets) {
    assert.ok(markdown.includes(snippet), `Expected document to include: ${snippet}`);
  }
}

test('pre01 documents the WSL2-first and PowerShell fallback paths', async () => {
  const markdown = await readMarkdown('../content/pre01-agentseek-create.md');

  assertContainsAll(markdown, [
    'WSL2',
    'wsl --install',
    'wsl -l -v',
    'wsl -d Ubuntu',
    '~/projects/',
    '/mnt/c/',
    'uv tool update-shell',
    '$env:Path = "$(uv tool dir --bin);$env:Path"',
    '$env:UV_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple"',
  ]);
});

test('pre02 documents LangSmith CLI and dotenv steps for both shells', async () => {
  const markdown = await readMarkdown('../content/pre02-agentseek-skills.md');

  assertContainsAll(markdown, [
    'WSL2 用户',
    'command -v langsmith',
    'Get-Command langsmith -ErrorAction SilentlyContinue',
    'https://cli.langsmith.com/install.sh',
    'https://cli.langsmith.com/install.ps1',
    'set -a',
    'source .env',
    'Get-Content .env | ForEach-Object',
    'Set-Item -Path "Env:$($matches[1])" -Value $value',
    '不要使用 `uv tool install langsmith`',
  ]);
});
