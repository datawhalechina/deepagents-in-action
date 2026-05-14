import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const OUT_DIR = resolve(ROOT, 'src/content/chapters');

const manifest = JSON.parse(readFileSync(resolve(__dirname, 'chapters.json'), 'utf-8'));

if (!existsSync(OUT_DIR)) {
  mkdirSync(OUT_DIR, { recursive: true });
}

for (const [id, meta] of Object.entries(manifest)) {
  const sourceFile = resolve(ROOT, `content/${id}.md`);

  if (!existsSync(sourceFile)) {
    console.log(`  SKIP ${id}: source file not found`);
    continue;
  }

  let body = readFileSync(sourceFile, 'utf-8');

  // Strip the first H1 heading (layout renders title from frontmatter)
  body = body.replace(/^#\s+.+\n*/, '');

  // Rewrite relative image paths to include base path
  const BASE = '/deepagents-course';
  body = body.replace(/!\[([\s\S]*?)\]\(\.\.\/public\/imgs\//g, `![$1](${BASE}/imgs/`);

  const frontmatter = [
    '---',
    `title: "${meta.title.replace(/"/g, '\\"')}"`,
    `chapter: ${meta.chapter}`,
    `section: "${meta.section}"`,
    `order: ${meta.order}`,
    `description: "${meta.description.replace(/"/g, '\\"')}"`,
    ...(meta.slides && meta.slides.length > 0
      ? [`slides:`, ...meta.slides.map(s => {
          let slideYaml = `  - id: "${s.id}"\n    title: "${s.title}"`;
          if (s.bilibili) slideYaml += `\n    bilibili: "${s.bilibili}"`;
          if (s.xhs) slideYaml += `\n    xhs: "${s.xhs}"`;
          return slideYaml;
        })]
      : [`slides: []`]),
    `published: ${meta.published}`,
  ];

  if (meta.pubDate) frontmatter.push(`pubDate: "${meta.pubDate}"`);
  if (meta.bilibili) frontmatter.push(`bilibili: "${meta.bilibili}"`);
  if (meta.xhs) frontmatter.push(`xhs: "${meta.xhs}"`);

  frontmatter.push('---', '');

  const output = frontmatter.join('\n') + body.trimStart();
  const outPath = resolve(OUT_DIR, `${id}.md`);
  writeFileSync(outPath, output, 'utf-8');
  console.log(`  OK   ${id}`);
}

console.log('\nContent prep done.');
