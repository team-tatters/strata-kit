---
title: 프로필
status: ready
generated: true
---

# 프로필

> 이 문서는 원천에서 생성된다 — 손으로 고치지 않는다.

스택별 묶음. active 는 실제 프로젝트에서 검사기가 돈 기록이 있는 프로필이다.

| 프로필 | 상태 | 레이어 | 검사기 |
|---|---|---|---|
| `backend.go-service` | draft | feature packages (internal/<domain>) with role files — store.go (L2 data access), command.go·query.go (L2 services), usecase.go (L3), http.go (Route) | depguard, go vet, staticcheck, go test ./... |
| `backend.kotlin-spring-cqrs` | active | L1 → LM1 → L2 → LM2 → L3 → Route | archunit |
| `backend.typescript-nest` | draft | Nest modules per domain — data/ (L2 repository·template·command·query services), coordinate/ (LM2), *.composite-service.ts·listener·task (L3), *.controller.ts (Route); module exports publish use cases only | dependency-cruiser, tsc --noEmit |
| `cli.go` | draft | cmd → internal (ports/adapters by package) | depguard, go vet |
| `core.generic` | active | none declared; rec.architecture.no-layer-violation is explained and marked not applicable | - |
| `frontend.next-web` | active | Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell | dependency-cruiser |
| `frontend.swiftui` | draft | Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell | swift-format, swiftlint, check-swift-layers |
| `service.rust` | draft | Cargo workspace crates — kit (L1), domain (L1 domain + ports), infra (LM1 + L2 data access), app (L2 services, LM2, L3), api (Route); app must not depend on infra | cargo fmt --check, cargo clippy -D warnings, cargo test |
