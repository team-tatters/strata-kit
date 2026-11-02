# Kotlin/Spring layer enforcement templates (ArchUnit)

ArchUnit test templates that **read `layer-rules.yaml` (the Core SoT) directly at runtime** to check the
direction of layer dependencies. There is no code generation, so a rule change takes effect at once without
regenerating anything (One Fact in One File).

## Enforcement tiers

| Tier | Covers | Strength |
|---|---|---|
| Gradle multi-module | module (domain) boundaries — a compile error when a dependency is not declared | enforced by the compiler |
| ArchUnit (these templates) | layer direction inside a module, isolation between domain slices | CI blocking (source of truth) |
| Hook (check-layer-violation.py) | live feedback while editing | heuristic, warning |

Background in detail: `profiles/backend.kotlin-spring-cqrs/docs/en/backend-kotlin-spring.md`

## Choosing a mode: greenfield or brownfield

| Mode | How layers are identified | Test template | For |
|---|---|---|---|
| Greenfield | `package_identifier` (package segments such as `..data..`) | `StrataLayerRulesTest.kt.template` | new projects with the Strata standard package structure |
| Brownfield | `.strata/layer-map.yaml` (path → layer, same semantics as check-layer-violation.py) | `StrataLayerMapTest.kt.template` | projects that keep their existing package structure |

The packages of an existing project do not follow the Strata segments (for example `com.example.rest`,
`com.example.domain.{x}.services`), so package_identifier does not match — use brownfield mode.
This was confirmed by a real run on a backend project (14 modules, 1,417 classes) on 2026-07-06.

**Introducing brownfield mode**: first run `layer classification summary` to check how well the layer-map
matches (the unmapped ratio, and misclassification caused by the top-down substring order); then run
`violation tally` to see how much existing debt there is; if there are many violations, freeze the existing ones
with ArchUnit `FreezingArchRule` and block only new ones; once the debt is paid down, switch to hard-fail.

**Exceptions (waivers)**: declare a violation you allow on purpose in the `exceptions:` block of layer-map.yaml.
It must reference a decision id in decisions.yaml, and the test leaves that (from_path → to_layer) dependency
out of the check. Setting `status: retired` expires the exception.

```yaml
exceptions:
  - id: "EX-2026-07-07-01"
    decision: "DEC-2026-07-07-01"    # must reference decisions.yaml
    from_path: "service/user-api/"
    to_layer: "LM1_Inherite"
    reason: "legacy maintenance scope"
    status: "active"
```

## How to apply

1. Copy the files (into the target project's test sources):
   ```
   StrataRules.kt.template          → src/test/kotlin/{{BASE_PACKAGE_PATH}}/architecture/StrataRules.kt
   StrataLayerRulesTest.kt.template → 〃 /StrataLayerRulesTest.kt   (greenfield)
   StrataLayerMapTest.kt.template   → 〃 /StrataLayerMapTest.kt     (brownfield)
   ```
2. Replace the placeholders:
   - `{{BASE_PACKAGE}}` — the project's root package (for example `com.example.order`)
3. Add the dependencies from `build.gradle.kts.snippet` to the test scope.
4. `./gradlew test` — it is part of Gradle `check`, so it blocks in CI automatically.

## Where layer-rules.yaml is looked up

`StrataRules.load()` looks for the rules file in this order:

1. The system property `-Dstrata.layerRules=/path/to/layer-rules.yaml`
2. The project-local `.strata/layer-rules.yaml` (when the project pins or overrides the rules)
3. `$STRATA_KIT/core/rules/layer-rules.yaml`

In CI, option 2 (a local copy) or option 1 (inject the path of a strata checkout) is recommended.
Option 3, which depends on `STRATA_KIT`, is a convenience for local development.

## Multi-module projects

- Put the layer check in **each module's test sources** and limit `importPackages` to that module's package, or
  import every package from one root integration-test module (recommended: the latter — the rules file is loaded once).
- Module boundaries themselves (isolation between domains) are enforced before ArchUnit, by the dependency
  declarations in `build.gradle.kts`. Use `implementation` instead of `api` to stop transitive dependencies leaking.

## What is checked

- `layer dependency direction`: `backend.layers.*.can_reference` — only layers that define a kotlin
  `package_identifier` are checked (all 6 current layers define one).
- `domain slice isolation`: no cross-references between domains in layers that set `cross_reference: false`
  and define `domain_slice` (L2/LM2/L3).
- `no bean lookup by string name`: `BeanFactory.getBean("...")` — blocks the one realistic path that
  bypasses static analysis.
