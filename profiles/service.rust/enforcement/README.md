# service.rust enforcement

Rust has no layer checker in the kit yet. The profile's verification is the toolchain gate from DEC-2026-10-22-01 (strata):

    cargo fmt --check && cargo clippy --no-deps -D warnings && cargo test

Module ownership (domain, app, infra) is reviewed; a `cargo-deny`/`cargo-modules` based checker is a pending card.
