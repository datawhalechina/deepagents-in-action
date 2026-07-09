#!/usr/bin/env node
import sharp from 'sharp';

const [, , input, output] = process.argv;
const maxDim = Number(process.env.MAX_DIM || 1600);

const LIMIT_INPUT_PIXELS = 100_000_000;

if (!input || !output) {
  console.error('Usage: optimize-images.mjs <input> <output>');
  process.exit(1);
}

await sharp(input, { limitInputPixels: LIMIT_INPUT_PIXELS })
  .resize({ width: maxDim, height: maxDim, fit: 'inside', withoutEnlargement: true })
  .png({ compressionLevel: 9, effort: 10, quality: 90 })
  .toFile(output);
