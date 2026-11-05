// Drops the leading "# Title" and rewrites the relative links the docs are written with, so one Markdown file works on GitHub and on this site.
//   ../concepts/overview.md#why  ->  /strata-kit/concepts/overview/#why     (a page in the docs)
//   ../../CONTRIBUTING.md        ->  https://github.com/<repo>/blob/main/CONTRIBUTING.md   (a file outside docs/)
//   ../../core/docs/ko/          ->  https://github.com/<repo>/tree/main/core/docs/ko/
// src/content/docs is a copy of the repository's docs/ folder, so a path outside it is a repository path.
import path from 'node:path';

const EXTERNAL = /^([a-z][a-z0-9+.-]*:|\/|#)/i;

/** Pure: the new URL for `url` written in the page at `file`, or null to leave it. */
export function rewrite(url, file, { contentDir, base, repo }) {
  if (!url || EXTERNAL.test(url)) return null;
  const [target, hash = ''] = url.split(/(?=#)/);
  const abs = path.resolve(path.dirname(file), target);
  const rel = path.relative(contentDir, abs).split(path.sep).join('/');
  const trailing = target.endsWith('/');
  if (rel.startsWith('..')) {
    const repoPath = path.posix.normalize(`docs/${rel}`);
    if (repoPath.startsWith('..')) return null;
    return `${repo}/${trailing ? 'tree' : 'blob'}/main/${repoPath}${trailing && !repoPath.endsWith('/') ? '/' : ''}${hash}`;
  }
  if (!/\.mdx?$/.test(rel)) return null;
  let slug = rel.replace(/\.mdx?$/, '').toLowerCase();
  if (slug === 'index') slug = '';
  else if (slug.endsWith('/index')) slug = slug.slice(0, -'/index'.length);
  return `${base.replace(/\/$/, '')}/${slug ? `${slug}/` : ''}${hash}`;
}

export default function remarkDocLinks(options) {
  return (tree, vfile) => {
    // The pages open with "# Title" for the GitHub view; the site draws the frontmatter title, so drop the copy.
    const first = tree.children?.[0];
    if (first?.type === 'heading' && first.depth === 1) tree.children.shift();
    const file = vfile.path ?? vfile.history?.[0];
    if (!file) return;
    const walk = (node) => {
      if (node.type === 'link' || node.type === 'definition') {
        const next = rewrite(node.url, file, options);
        if (next) node.url = next;
      }
      for (const child of node.children ?? []) walk(child);
    };
    walk(tree);
  };
}
