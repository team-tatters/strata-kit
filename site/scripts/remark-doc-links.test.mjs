import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rewrite } from '../src/plugins/remark-doc-links.mjs';

const opts = { contentDir: '/s/src/content/docs', base: '/strata-kit', repo: 'https://github.com/example/shop-docs' };
const ko = '/s/src/content/docs/ko/index.md';
const en = '/s/src/content/docs/index.md';

test('a page link becomes the page address, keeping the anchor', () => {
  assert.equal(rewrite('concepts/overview.md', ko, opts), '/strata-kit/ko/concepts/overview/');
  assert.equal(rewrite('../concepts/overview.md#why', '/s/src/content/docs/guides/a.md', opts), '/strata-kit/concepts/overview/#why');
  assert.equal(rewrite('getting-started/01-install.md', en, opts), '/strata-kit/getting-started/01-install/');
});

test('an index page becomes its folder', () => {
  assert.equal(rewrite('index.md', '/s/src/content/docs/ko/faq.md', opts), '/strata-kit/ko/');
  assert.equal(rewrite('../index.md', '/s/src/content/docs/ko/faq.md', opts), '/strata-kit/');
});

test('a file outside docs becomes its GitHub address', () => {
  assert.equal(rewrite('../../CONTRIBUTING.md', ko, opts), 'https://github.com/example/shop-docs/blob/main/CONTRIBUTING.md');
  assert.equal(rewrite('../CONTRIBUTING.md', en, opts), 'https://github.com/example/shop-docs/blob/main/CONTRIBUTING.md');
  assert.equal(rewrite('../../core/docs/ko/', ko, opts), 'https://github.com/example/shop-docs/tree/main/core/docs/ko/');
});

test('external links, anchors and images are left alone', () => {
  for (const url of ['https://example.com', '#참조', '/abs', 'mailto:a@b.c', 'images/strata-loop-ko.svg']) {
    assert.equal(rewrite(url, ko, opts), null, url);
  }
});

test('the leading # title is dropped, since the site already shows the page title', async () => {
  const { default: plugin } = await import('../src/plugins/remark-doc-links.mjs');
  const tree = { type: 'root', children: [
    { type: 'heading', depth: 1, children: [{ type: 'text', value: 'T' }] },
    { type: 'paragraph', children: [{ type: 'link', url: 'faq.md', children: [] }] },
    { type: 'heading', depth: 1, children: [{ type: 'text', value: 'later' }] },
  ] };
  plugin(opts)(tree, { path: ko });
  assert.deepEqual(tree.children.map((n) => n.type), ['paragraph', 'heading']);
  assert.equal(tree.children[0].children[0].url, '/strata-kit/ko/faq/');
});
