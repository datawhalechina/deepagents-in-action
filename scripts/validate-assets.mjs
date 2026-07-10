import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const MAX_DIM = Number(process.env.MAX_DIM || 1600);
const MAX_PDF_BYTES = 8 * 1024 * 1024;
const publicDir = path.resolve('public');
const imageExtensions = new Set(['.png', '.jpg', '.jpeg']);

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? filesIn(target) : [target];
  }));
  return nested.flat();
}

const files = await filesIn(publicDir);
const errors = [];
let imageCount = 0;
let pdfCount = 0;

for (const file of files) {
  const extension = path.extname(file).toLowerCase();
  const relativePath = path.relative(process.cwd(), file);

  if (imageExtensions.has(extension)) {
    imageCount += 1;
    try {
      const metadata = await sharp(file, { limitInputPixels: 100_000_000 }).metadata();
      if (!metadata.width || !metadata.height) {
        errors.push(`${relativePath}: missing image dimensions`);
      } else if (metadata.width > MAX_DIM || metadata.height > MAX_DIM) {
        errors.push(`${relativePath}: ${metadata.width}×${metadata.height} exceeds ${MAX_DIM}px`);
      }
    } catch (error) {
      errors.push(`${relativePath}: invalid raster image (${error.message})`);
    }
  }

  if (extension === '.pdf') {
    pdfCount += 1;
    const [header, metadata] = await Promise.all([
      readFile(file, { encoding: null }).then((contents) => contents.subarray(0, 5).toString()),
      stat(file),
    ]);

    if (header !== '%PDF-') {
      errors.push(`${relativePath}: invalid PDF header`);
    }
    if (metadata.size > MAX_PDF_BYTES) {
      errors.push(`${relativePath}: ${(metadata.size / 1024 / 1024).toFixed(1)} MB exceeds 8 MB`);
    }
  }
}

if (errors.length > 0) {
  console.error(`Asset validation failed:\n${errors.map((error) => `- ${error}`).join('\n')}`);
  process.exit(1);
}

console.log(`Validated ${imageCount} raster images and ${pdfCount} PDFs (max image edge: ${MAX_DIM}px).`);
