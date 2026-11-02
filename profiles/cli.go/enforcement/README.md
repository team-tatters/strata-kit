# cli.go enforcement

- `.golangci.yml.template`: depguard rules for the cmd → app → domain/ports ← adapters shape. Replace `{{MODULE}}` with the module path.
- CI: `go vet ./... && golangci-lint run ./... && go test ./...`.
- Hook fast path: strata's `check-layer-violation.py` reads Go imports as a warning-level heuristic; CI is the verdict.
