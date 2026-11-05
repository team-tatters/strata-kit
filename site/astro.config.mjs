// @ts-check
// The strata-kit documentation site. The pages are the Markdown in ../docs (English) and ../docs/ko (Korean);
// scripts/sync-docs.mjs copies them into src/content/docs before every build, so the same files read correctly
// on the GitHub repository page and on this site.
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { unified } from '@astrojs/markdown-remark';
import starlightLinksValidator from 'starlight-links-validator';
import { fileURLToPath } from 'node:url';
import remarkDocLinks from './src/plugins/remark-doc-links.mjs';

const REPO = 'https://github.com/n0roo/strata-kit';
// Provisional address (DEC-2026-11-03-01): tatters.io/products/strata-kit/docs/. REPO stays until the public repository is chosen.
const BASE = '/products/strata-kit/docs';
const CONTENT = fileURLToPath(new URL('./src/content/docs', import.meta.url));

/** A sidebar group per folder; Starlight fills it from the same folder in each locale. */
const group = (label, ko, directory) => ({ label, translations: { ko }, items: [{ autogenerate: { directory } }] });

export default defineConfig({
  site: 'https://tatters.io',
  base: BASE,
  markdown: {
    // Astro 7's default processor runs no remark plugins; the link rewrite needs the unified one.
    processor: unified({ remarkPlugins: [[remarkDocLinks, { contentDir: CONTENT, base: BASE, repo: REPO }]] }),
  },
  integrations: [
    starlight({
      title: 'strata-kit',
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
        ko: { label: '한국어', lang: 'ko' },
      },
      social: [{ icon: 'github', label: 'GitHub', href: REPO }],
      lastUpdated: true,
      customCss: [
        'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css',
        './src/styles/theme.css',
      ],
      sidebar: [
        group('Getting started', '시작하기', 'getting-started'),
        group('Concepts', '개념', 'concepts'),
        group('Guides', '방법', 'guides'),
        group('Reference', '참조', 'reference'),
        // faq.md and glossary.md sit at the top of docs/ and are reached from the index page. A sidebar entry by slug
        // fails the build while a page exists in only one language, so they join the sidebar once both are ready.
      ],
      plugins: [starlightLinksValidator()],
    }),
  ],
});
