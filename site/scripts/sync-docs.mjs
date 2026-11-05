// Copies the repository's docs/ (English pages at the top, Korean under ko/) into src/content/docs, replacing what
// was there. The copy is a build input only: it is ignored by git, and the pages are edited in docs/.
import { cpSync, existsSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const from = fileURLToPath(new URL('../../docs', import.meta.url));
const to = fileURLToPath(new URL('../src/content/docs', import.meta.url));

if (!existsSync(from)) {
  console.error(`sync-docs: ${from} does not exist. The site is built from a public projection, where docs/ sits next to site/.`);
  process.exit(1);
}
rmSync(to, { recursive: true, force: true });
cpSync(from, to, { recursive: true });
console.log(`sync-docs: copied ${from} -> ${to}`);
