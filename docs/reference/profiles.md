---
title: Profiles
status: ready
generated: true
---

# Profiles

> This page is generated from the sources — do not edit it by hand.

Per-stack bundles. Active means a checker for the profile's rules has run on a real project and left a record.

| Profile | Status | Layers | Checkers |
|---|---|---|---|
| `backend.go-service` | draft | feature packages (internal/<domain>) with role files — store.go (L2 data access), command.go·query.go (L2 services), usecase.go (L3), http.go (Route) | depguard, go vet, staticcheck, go test ./... |
| `backend.kotlin-spring-cqrs` | active | L1 → LM1 → L2 → LM2 → L3 → Route | archunit |
| `backend.typescript-nest` | draft | Nest modules per domain — data/ (L2 repository·template·command·query services), coordinate/ (LM2), *.composite-service.ts·listener·task (L3), *.controller.ts (Route); module exports publish use cases only | dependency-cruiser, tsc --noEmit |
| `cli.go` | draft | cmd → internal (ports/adapters by package) | depguard, go vet |
| `core.generic` | active | none declared; rec.architecture.no-layer-violation is explained and marked not applicable | - |
| `frontend.next-web` | active | Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell | dependency-cruiser |
| `frontend.swiftui` | draft | Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell | swift-format, swiftlint, check-swift-layers |
| `service.rust` | draft | Cargo workspace crates — kit (L1), domain (L1 domain + ports), infra (LM1 + L2 data access), app (L2 services, LM2, L3), api (Route); app must not depend on infra | cargo fmt --check, cargo clippy -D warnings, cargo test |
