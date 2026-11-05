# Kotlin/Spring layer enforcement templates (ArchUnit)

ArchUnit test templates that **read `layer-rules.yaml` (the Core SoT) directly at runtime** to check the
direction of layer dependencies. There is no code generation, so a rule change takes effect at once without
regenerating anything (One Fact in One File).

## Enforcement tiers

| Tier | Covers | Strength |
|---|---|---|
| Gradle multi-module | module (domain) boundaries — a compile error when a dependency is not declared | enforced by the compiler |
| ArchUnit (these templates) | layer direction inside a module, isolation between domain slices | failing gate in CI by default (source of truth); warning mode is an opt-in for brownfield adoption, with a ratchet and a way back to the gate |
| Hook (check-layer-violation.py) | live feedback while editing | heuristic, warning |

Background in detail: `profiles/backend.kotlin-spring-cqrs/docs/en/backend-kotlin-spring.md`

## Choosing a mode: greenfield or brownfield

| Mode | How layers are identified | Test template | For |
|---|---|---|---|
| Greenfield | `package_identifier` (package segments such as `..data..`) | `StrataLayerRulesTest.kt.template` | new projects with the Strata standard package structure |
| Brownfield | the layer map (`.strata/layer-map.yaml` or `archunit/layer-map.yaml`, path → layer, same semantics as check-layer-violation.py) | `StrataLayerMapTest.kt.template` | projects that keep their existing package structure |

The packages of an existing project do not follow the Strata segments (for example `com.example.rest`,
`com.example.domain.{x}.services`), so package_identifier does not match — use brownfield mode.
This was confirmed by a real run on a backend project (14 modules, 1,417 classes) on 2026-07-06.

**Introducing brownfield mode**: first run `layer classification summary` to check how well the layer-map
matches (the unmapped ratio, and misclassification caused by the top-down substring order); then run
`violation tally` to see how much existing debt there is. With few violations, fix them and keep the failing gate. With
many, adopt in warning mode (below): the same rule writes its violations to a file and fails only when a count rises
above a frozen baseline; once the baseline reaches zero, switch back to the failing gate.

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
   opt-in/StrataBoundaryRulesTest.kt.template → 〃 /StrataBoundaryRulesTest.kt (the three boundaries, see below)
   opt-in/StrataWarnings.kt.template           → 〃 /StrataWarnings.kt            (warning mode only, see below)
   opt-in/StrataLayerWarningsTest.kt.template  → 〃 /StrataLayerWarningsTest.kt   (warning mode for StrataLayerMapTest)
   opt-in/StrataBoundaryWarningsTest.kt.template → 〃 /StrataBoundaryWarningsTest.kt (warning mode for StrataBoundaryRulesTest)
   ```
   Files under `opt-in/` are not install targets (doctor counts only the top-level templates); copy them when the
   project chooses them.
2. Replace the placeholders:
   - `{{BASE_PACKAGE}}` — the project's root package (for example `com.example.order`)
3. Add the dependencies from `build.gradle.kts.snippet` to the test scope.
4. `./gradlew test` — it is part of Gradle `check`, so it blocks in CI automatically. This is the default.

## Warning mode (opt-in, brownfield adoption)

The default stays the failing gate. Warning mode is for a project that cannot fix its existing violations first: it
evaluates **the same rules** (`StrataLayerMapTest.layerDirectionRule()`, `StrataBoundaryRulesTest.directDatasourceRule()`
and `feignWriteRule()`), records what they find, and fails only when things get worse.

| Piece | What it does |
|---|---|
| `-Dstrata.warningMode=true` | the one switch: the warning tests run and the failing tests (layer direction, the two boundary rules) are skipped. Without it the warning tests are skipped, so the two never gate at once |
| `violations/warnings.yaml` | every violation of the run — rule id, class, module, ArchUnit message — and a summary per rule and module. Rewritten on every run; add it to `.gitignore` |
| `violations/frozen/baseline.yaml` | the count per rule id, frozen. **Tracked.** The run fails only when a count is above it (a ratchet); fewer is always fine, and a rule id it does not name has baseline 0 |
| the excluded scope | classes under the layer map's `excluded:` (code that is being replaced) are not listed one by one, for the layer rule and the boundary rules alike; their violation count per module is stored in the baseline next to the checked counts. **Decision (2026-11-05): by default it is only recorded and printed**; it fails the run only with `-Dstrata.ratchetExcluded=true` |

Both files live in `-Dstrata.violationsDir`, else in `violations/` next to the layer map (`archunit/violations/` for
`archunit/layer-map.yaml`, `.strata/violations/` for `.strata/layer-map.yaml`). The `layers` and `boundaries` families
each own a section of both files. Boundary exemptions keep applying in warning mode. The layer map's `excluded:` applies to
the boundaries too (decision 2026-11-05), in both modes: the failing gate leaves those classes out and warning mode counts
them per module. That is separate from exemptions — an exemption waives a violation someone decided to allow, `excluded:`
sets aside code that is being replaced. `kb boundaries check` treats `excluded:` the same way (`excluded_by_module` in its
report, not a finding, not in the exit code).

Rewriting the baseline is always explicit:

- `-Dstrata.rebaseline=reset` writes today's counts as they are — the first adoption (a run without a baseline fails
  and says so), or after the layer map changed. Say why in the commit.
- `-Dstrata.rebaseline=tighten` lowers each count to today's and never raises one — run it when the run reports
  `below baseline`, so the debt paid stays paid.

**Leaving warning mode**: when a family's baseline is 0 for every rule and nothing is excluded, the run prints
`baseline is 0 — leave warning mode`. Drop `-Dstrata.warningMode` (and the warning tests if you like); the failing tests
gate again. Promote the `kb enforce` grade at the same time if you wrapped the run (below).

### Option: one central check over every module

A multi-module project can run the check once over all compiled modules, outside the team build (pre-commit, deploy
builds and `./gradlew test` do not run it), from a source set of the root project. This is how a 14-module project
adopted it (`./gradlew archCheck`). Copy the templates into `archunit/kotlin/{{BASE_PACKAGE_PATH}}/architecture/`, keep
the map in `archunit/layer-map.yaml`, and add to the root `build.gradle.kts` (the root must apply `kotlin("jvm")`):

```kotlin
// A root source set that is not in settings.gradle.kts: not part of any module's test task
val archunit: SourceSet by sourceSets.creating {
    kotlin.srcDir("archunit/kotlin")
}

dependencies {
    "archunitImplementation"("com.tngtech.archunit:archunit:1.4.1")
    "archunitImplementation"("org.yaml:snakeyaml:2.2")
    "archunitImplementation"("org.junit.jupiter:junit-jupiter:5.10.2")
    "archunitRuntimeOnly"("org.junit.platform:junit-platform-launcher:1.10.2")
}

tasks.register<Test>("archCheck") {
    description = "Strata layer and boundary rules over every module (warning mode: archunit/violations/warnings.yaml)"
    group = "verification"
    testClassesDirs = archunit.output.classesDirs
    // StrataLayerMapTest reads the compiled dirs itself; the boundary rules import by package from the classpath
    classpath = archunit.runtimeClasspath + files(subprojects.map { it.layout.buildDirectory.dir("classes/kotlin/main") })
    useJUnitPlatform()
    maxHeapSize = "3g"                                     // all modules' classes are read at once
    dependsOn(subprojects.map { "${it.path}:classes" })
    systemProperty("strata.warningMode", "true")           // remove to make archCheck the failing gate
    listOf("strata.layerRules", "strata.rebaseline", "strata.ratchetExcluded")
        .forEach { p -> System.getProperty(p)?.let { systemProperty(p, it) } }
    testLogging { showStandardStreams = true }             // the [strata-arch] lines are what kb enforce reads
    outputs.upToDateWhen { false }
}
```

Then `./gradlew archCheck`, `./gradlew archCheck -Dstrata.rebaseline=reset`, and `archunit/violations/warnings.yaml` in
`.gitignore`. Each run prints lines that start with `[strata-arch] <family>`:

```
[strata-arch] layers warnings 12 (baseline 15) · excluded 101 (baseline 101)
[strata-arch]   layers.direction 12 / 15
[strata-arch] layers below baseline (layers.direction) — lock it in with -Dstrata.rebaseline=tighten
[strata-arch] layers ratchet exceeded: layers.direction 16 > 15        (only when it fails)
[strata-arch] layers coverage: 82.4% of classes mapped (unmapped 731 of 4150, excluded 120)
```

The coverage line says how much of the code the rule sees: classes outside `excluded:` that a mapping places. An
unmapped class is not direction-checked at all, so "0 warnings" over 40% of the classes is not the same as over 95%.
`kb enforce run` keeps it on the ledger entry (`coverage: {percent, unmapped}`); `layer classification summary` prints
it in the failing-gate mode too. The source-file counterpart is `python3 -m kb check-layer --audit`
("레이어 맵이 덮는 비율 82% (미대응 41파일 …)"), and `kb boundaries check` prints the share of modules with a changelog that
`boundaries.modules` names.

### Wrapping it for an enforcement grade

`python3 -m kb enforce run` records every run in the vault ledger and lets the project's grade decide what a violation
does (`layers` blocks until the manifest names a grade; `boundaries` starts advisory). The commands below count a run as
a violation only when the ratchet fails — a count above the baseline (Gradle exits 1 and prints `ratchet exceeded`).
Warnings within the baseline are the accepted debt and count as clean. Use these at every grade, and in particular at
`default` and `block`:

```
python3 -m kb enforce run --family layers --violation-exit 1 \
  --violation-pattern '\[strata-arch\] layers ratchet exceeded' \
  --count-regex '\[strata-arch\] layers warnings (\d+)' \
  --expect-pattern '\[strata-arch\] layers warnings' \
  -- ./gradlew archCheck --tests '*StrataLayerWarningsTest'

python3 -m kb enforce run --family boundaries --violation-exit 1 \
  --violation-pattern '\[strata-arch\] boundaries ratchet exceeded' \
  --count-regex '\[strata-arch\] boundaries warnings (\d+)' \
  --expect-pattern '\[strata-arch\] boundaries warnings' \
  -- ./gradlew archCheck --tests '*StrataBoundaryWarningsTest'
```

- A run above the baseline is a violation with its count; any other run that passes is clean.
- A run that fails any other way (compile error, missing baseline, bad map) does not print `ratchet exceeded` and is a
  checker error at every grade — advisory never hides a broken check.
- At `advisory` the wrapper returns 0 even when the ratchet fails; run the Gradle task directly in CI if the ratchet
  itself should stop the build.
- Do not pass `-q` to Gradle: it hides the test output. `--expect-pattern` is there for that case: a run that exits 0
  without the `[strata-arch] <family> warnings` line evaluated nothing the wrapper can see, and is recorded as
  indeterminate (a checker_error marked `indeterminate`), not clean.
- A rule that checked no class, or a layer-map mapping that matches no class, prints
  `[strata-arch] <family> indeterminate: …`. The wrapper records that run as indeterminate — "judgement impossible, the
  declaration does not match the code" — and the grade decides what it returns (advisory passes with a warning).
- A count is one ArchUnit violation — one dependency (a call, a field access, a return type), not one class.

For reference only — at `advisory`, to have the ledger record the remaining debt on every run, count warnings within the
baseline too: `--violation-exit 0,1 --violation-pattern '\[strata-arch\] layers (warnings [1-9]|ratchet exceeded)'`.
Do not use it at `default` or `block`: any warning left within the baseline would block.

## Empty rules are not clean

A rule whose `that()` matches no class — a scope or a layer-map path that names nothing in the code, or an import that
found no class at all (a wrong `{{BASE_PACKAGE}}`) — says nothing about the code. It must not read as a pass
(MB-strata-kit-2026-057).

- ArchUnit's `archRule.failOnEmptyShould` is `true` by default (since 0.23; checked on 1.4.1): such a rule fails with
  "failed to check any classes". Keep it that way. Do not set `archRule.failOnEmptyShould=false` in
  `src/test/resources/archunit.properties`, and do not add `.allowEmptyShould(true)` to a rule — the kit templates use
  neither. If a project really has an optional scope, leave that check out of its test instead of letting it pass empty.
- `layeredArchitecture()` fails on an empty layer unless the layers are optional. `StrataLayerMapTest` sets
  `withOptionalLayers(true)` (a project need not use every layer), so it checks the map itself instead: the test
  `layer map mappings - every mapping matches a compiled class` fails on a mapping that matches no class, and
  `layer classification summary` fails when no class is mapped at all.
- In warning mode the same cases are printed as `[strata-arch] <family> indeterminate: …` and the run goes on with the
  other rules; `kb enforce run` records it as indeterminate (see above).
- The edit-time side: `python3 -m kb check-layer --audit` lists mappings that match no source file and source files no
  mapping places; the edit hook says "판정 불가" for a code file no mapping places.

## Where layer-rules.yaml is looked up

`StrataRules.load()` looks for the rules file in this order:

1. The system property `-Dstrata.layerRules=/path/to/layer-rules.yaml`
2. The project-local `.strata/layer-rules.yaml` (when the project pins or overrides the rules)
3. `$STRATA_KIT/core/rules/layer-rules.yaml`

In CI, option 2 (a local copy) or option 1 (inject the path of a strata checkout) is recommended.
Option 3, which depends on `STRATA_KIT`, is a convenience for local development.

## Where the edit hook finds the layer map

The edit hook (check-layer-violation.py, and the naming hook with it) reads the first of:

1. `.strata/layer-map.yaml` in the repository
2. `archunit/layer-map.yaml` in the repository — for a project whose CI check keeps the map next to its ArchUnit code
3. the Tier P copy (`$STRATA_VAULT/projects/<p>/strata/layer-map.yaml` for a detached project)

So a detached project whose CI needs the map keeps it in the repository, and the hook and CI read the same file.
`StrataLayerMapTest` looks the map up in the same order (`-Dstrata.layerMap`, `.strata/`, `archunit/`, walking up from
the working directory) and takes the project root as the map's grandparent directory (`-Dstrata.classesRoot` overrides);
like the hook, it does not direction-check classes under `excluded:`.
Delete the Tier P copy once the repository file exists, or it is silently ignored.

A map may name its layers its own way (for example identifier + level: `component_L1`, `inherit_LM1`, `data_L2`,
`coordinate_LM2`, `composite_L3`, `controller_L4`) if it declares them under `layers:` with the kit `level`. The hook maps
each declared name to the kit layer of the same level and checks with the kit rules; a `can_reference` that differs from
the kit layer's, or a level the kit does not have, is reported to the agent (the edit is not blocked). Names that are not
declared under `layers:` (an `infra` marker) are not checked. `excluded:` paths are treated like `zones.legacy`: not
direction-checked.

```yaml
layers:
  data_L2: { level: 2, can_reference: [component_L1, inherit_LM1] }   # a projection of backend.layers.L2_DataLayer
excluded:
  - "service/legacy-api/"
mappings:
  - { path: "domain/order-entity/", layer: "data_L2" }
```

## Writing mappings: short paths misclassify

Mappings are substring matches from the top down. A short path such as `components/` also matches a `components`
package inside another module (`order-entity/.../commons/components/`, a service's `io/example/components/`) and puts
those classes in the L1 layer. Write one mapping per module root instead (`components/commons/src/`,
`components/mail-sender/src/`, ...), and put a more specific path above a general one when a module's inner package
would otherwise match an earlier rule.

## Multi-module projects

- Put the layer check in **each module's test sources** and limit `importPackages` to that module's package, or
  import every package from one root integration-test module (recommended: the latter — the rules file is loaded once;
  see "Option: one central check over every module" above).
- Module boundaries themselves (isolation between domains) are enforced before ArchUnit, by the dependency
  declarations in `build.gradle.kts`. Use `implementation` instead of `api` to stop transitive dependencies leaking.

## What is checked

- `layer dependency direction`: `backend.layers.*.can_reference` — only layers that define a kotlin
  `package_identifier` are checked (all 6 current layers define one).
- `domain slice isolation`: no cross-references between domains in layers that set `cross_reference: false`
  and define `domain_slice` (L2/LM2/L3).
- `no bean lookup by string name`: `BeanFactory.getBean("...")` — blocks the one realistic path that
  bypasses static analysis.

## The three boundaries (opt-in)

Layers do not cover data ownership, cross-domain writes or cross-domain reads
(`core/docs/ko/architecture/prepaid-structure.md`, DEC-2026-11-05-02). Their rule ids and check settings are in
`layer-rules.yaml` `boundaries:`; the project states its own facts in the `boundaries:` section of its layer map.

| Check | Runs in | What it reports |
|---|---|---|
| `boundary.data_ownership.changelog` | `python3 -m kb boundaries check` | a table or view created by more than one module of the same database; a changelog altering or writing rows of a table another module of the same database owns |
| `boundary.data_ownership.entity_mapping` | 〃 | an `@Table`/`@Entity` in one module mapping a table another module of the same database owns |
| `boundary.cross_domain_read.fdw_window` | 〃 | foreign tables listed as read windows per consumer → provider database; a finding only when the project chose `feign` for that pair |
| `boundary.data_ownership.direct_datasource` | `opt-in/StrataBoundaryRulesTest.kt.template` | a class in the `service` scope constructing `HikariDataSource`, `JdbcTemplate`, `NamedParameterJdbcTemplate`, `DefaultDSLContext` or calling `DSL.using` |
| `boundary.cross_domain_write.feign_write` | 〃 | a POST·PUT·PATCH·DELETE method of a `@FeignClient` called from outside the `listener` scope |

Tables are compared per database, never by name alone: two modules of different databases may keep tables of the
same name (a 2.0 and a 3.0 line), and that is not a finding.

### The map

Put a `boundaries:` section in the layer map. Both the checker and the template look for it in this order:
`-Dstrata.layerMap` / `--map`, then repo `.strata/layer-map.yaml`, then repo `archunit/layer-map.yaml`
(then Tier P, for the Python checker) — the order the edit hooks use once they read `archunit/` (MB-strata-kit-2026-018).

```yaml
boundaries:
  modules:                          # build module directory (repo-relative, or a unique directory name) → database
    domain/order-entity: orders
    domain/billing-entity: billing
  fdw_servers: { orders_fdw: orders }   # when CREATE SERVER reads dbname from a placeholder
  read_windows:                     # per consumer db → provider db: feign | fdw; absent = undecided (a person decides)
    billing: { orders: null }
  scopes:                           # optional; overrides the kit scopes (layer-rules.yaml boundaries.scopes)
    service: { packages: [], paths: ["service/"] }
  exemptions:
    - id: "BX-2026-11-05-01"
      rule: "boundary.cross_domain_write.feign_write"   # a check id, or a boundary id that covers its checks
      path: "service/mail-api/"     # any of path · module · table, all given must match
      reason: "mail platform: every domain sends through it"
      decision: "DEC-2026-11-05-02" # or sunset: 2026-12-31 (a past date is no longer honoured) or a condition
```

An exemption without a reason, or without a decision or a sunset, is not honoured; both tools list it.
The layer map's top-level `excluded:` (code being replaced) applies to all five checks as well: both tools leave
findings under those paths out and report only their count per module — the template in warning mode, the checker as
`excluded_by_module`. It is not an exemption and needs no decision; it is the same list the layer check uses.
In ArchUnit a `path` matches the compiled class path relative to the project root or the class name written as a
path (`com/example/mail/`); `table` exemptions apply only to the changelog checker.

The checker follows each module's changelog masters (`changelog-master*`, `db.changelog-*`, or the
`changelogs:` list of the module entry) through `include`, `includeAll` and `sqlFile`, in Liquibase order, so renames
and drops are replayed. SQL files under a changelog directory that no master includes are not read and are listed.

### Adopting

The boundary checks start **advisory**. The template is opt-in: copy `opt-in/StrataBoundaryRulesTest.kt.template`
next to `StrataRules.kt` when the project starts on the boundaries; nothing changes for a project that does not.
The `boundaries` family is advisory until the project manifest names a grade:

- run both checkers under the enforcement wrapper:
  ```
  python3 -m kb enforce run --family boundaries -- python3 -m kb boundaries check
  python3 -m kb enforce run --family boundaries -- ./gradlew test --tests '*StrataBoundaryRulesTest'
  ```
- with many existing violations, run the two ArchUnit rules in warning mode instead: copy
  `opt-in/StrataWarnings.kt.template` and `opt-in/StrataBoundaryWarningsTest.kt.template` next to the boundary test and
  set `-Dstrata.warningMode=true` (see Warning mode above — the same files, a `boundaries` section of their own).

Promoting the family (advisory → default → block) is a decision per project once the numbers are known.

### Limits

- The checker reads schema history, not code: a service writing another module's table through raw SQL on a shared
  connection does not show in changelogs. The direct-DataSource rule catches the connections a service opens itself.
- `DataSourceBuilder`-built connections and connections a bean receives by injection are not checked.
- Which window is canonical for a database pair (`read_windows`) is the project's decision; the kit does not choose.
