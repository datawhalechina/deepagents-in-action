import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const chapters = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/chapters' }),
  schema: z.object({
    title: z.string(),
    chapter: z.number(),
    section: z.enum(['认知篇', '核心篇', '进阶篇', '实战篇']),
    order: z.number(),
    description: z.string(),
    slides: z.array(z.object({
      id: z.string(),
      title: z.string(),
      bilibili: z.string().optional(),
      xhs: z.string().optional(),
    })).default([]),
    bilibili: z.string().optional(),
    xhs: z.string().optional(),
    published: z.boolean().default(false),
    pubDate: z.coerce.date().optional(),
  }),
});

export const collections = { chapters };
