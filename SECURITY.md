# Security

strata-kit runs locally: hooks and the `kb` engine read your project, your vault and your agent's tool calls, and
the MCP server serves search over your vault to the agent on your machine. It sends nothing anywhere by itself; the
vault sync (`kb/legacy/vault_git.sh`) pushes only to the git remote you configured for your vault, and only when
`STRATA_VAULT` is set.

Please report a vulnerability privately through GitHub's security advisory form ("Report a vulnerability" on the
repository's Security tab) rather than in a public issue. Include the version or commit, what an attacker can do,
and steps to reproduce. You will get an acknowledgement, and a fix or a plan, as soon as the maintainer can look.

Things that are in scope: a hook or checker that runs code from an untrusted file, a command that writes outside the
project, the vault or the kit, a path in a generated file that leaks a secret, the MCP server exposing files outside
the vault.
