import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// The pages carry the fields the public projection reads: status (only ready pages are published) and, on English
// pages, translated_from (the fingerprint of the Korean source). A fingerprint can be all digits, so coerce it.
const projection = z.object({
  status: z.enum(['draft', 'ready']).optional(),
  translated_from: z.coerce.string().optional(),
});

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({ extend: projection }),
  }),
};
