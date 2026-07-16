import { access, readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

const CONTENT_IMAGE_PATTERN = /!\[([\s\S]*?)\]\((\.\.\/public\/imgs\/([^\s)]+))(\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\)/g;

export function rewriteContentImagePaths(markdown, basePath) {
  const normalizedBase = basePath.replace(/\/+$/, '');

  return markdown.replace(
    CONTENT_IMAGE_PATTERN,
    (_match, alt, _sourcePath, imagePath, title = '') => (
      `![${alt}](${normalizedBase}/imgs/${imagePath}${title})`
    ),
  );
}

export function extractContentImageReferences(markdown) {
  return Array.from(markdown.matchAll(CONTENT_IMAGE_PATTERN), (match) => ({
    sourcePath: match[2],
    publicRelativePath: `imgs/${match[3]}`,
  }));
}

async function markdownFilesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return markdownFilesIn(target);
    return entry.name.endsWith('.md') ? [target] : [];
  }));
  return nested.flat();
}

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

export async function validateContentImageReferences({ contentDir, publicDir }) {
  const files = await markdownFilesIn(contentDir);
  const errors = [];
  let referenceCount = 0;

  for (const file of files) {
    const markdown = await readFile(file, 'utf8');
    const references = extractContentImageReferences(markdown);
    referenceCount += references.length;

    for (const reference of references) {
      const asset = path.resolve(publicDir, reference.publicRelativePath);
      if (!await exists(asset)) {
        errors.push(
          `${path.relative(contentDir, file)}: ${reference.sourcePath} points to missing public/${reference.publicRelativePath}`,
        );
      }
    }
  }

  return { referenceCount, errors };
}
