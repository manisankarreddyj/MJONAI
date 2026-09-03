# MJONAI Refactor Boundaries

> This document defines the architectural boundaries and refactoring constraints that must be respected while evolving the MJONAI codebase.

## Current Stable Systems

The following systems currently appear structurally stable and directionally correct based on current project architecture.

### Research Persistence Layer
Current repository and persistence architecture is one of the strongest systems in MJONAI.

Strengths include:
- centralized data access layer
- structured research persistence
- signal lifecycle storage
- trade lifecycle analytics
- pattern memory architecture
- AI verdict persistence
- portfolio analytics foundations

Current stability level:
HIGH

### Signal Intelligence Architecture
Current signal flow architecture is structurally strong.

Strengths include:
- layered filtering
- multi-stage validation
- strategy registry structure
- AI-assisted validation
- research-oriented signal lifecycle tracking

Current stability level:
HIGH

### Trade Lifecycle Tracking
Current paper execution and monitoring flow is directionally strong.

Strengths include:
- trade lifecycle persistence
- stop-loss handling
- trailing logic
- outcome intelligence
- MAE/MFE tracking
- research-aware execution flow

Current stability level:
MEDIUM-HIGH

### Scheduler-Driven Runtime Model
Current scheduler model is structurally correct for current project maturity.

Strengths include:
- operational automation
- periodic orchestration
- lifecycle coordination
- runtime sequencing

Current stability level:
MEDIUM

### Research-Oriented Project Direction
The strategic shift toward:
- research first
- edge validation first
- paper trading before live trading

is currently the correct direction for MJONAI.

Current stability level:
HIGH

### Documentation and Cognition Layer
The new project cognition system is now becoming a foundational stability layer.

Includes:
- inventory documentation
- runtime cognition
- operational reality tracking
- architecture mapping

Current stability level:
HIGH

## Oversized Runtime Components

The following components currently contain too many responsibilities and may become future architectural bottlenecks if not gradually stabilized.

### main.py

Current responsibilities include:
- startup orchestration
- scheduler coordination
- market initialization
- monitoring loop activation
- analytics job coordination
- reporting coordination
- runtime sequencing
- execution coordination

Current risks:
- orchestration concentration
- difficult debugging
- increasing dependency coupling
- future scaling difficulty

Future direction:
- gradual orchestration separation
- service-oriented coordination
- modular runtime handlers

Current priority:
VERY HIGH

### strategy/signal_scanner.py

Current responsibilities include:
- multi-strategy orchestration
- strategy execution coordination
- signal filtering
- AI validation triggering
- ranking workflows
- scan management

Current risks:
- signal pipeline complexity growth
- strategy coupling risk
- scan orchestration concentration

Future direction:
- modular signal pipeline stages
- separated validation layers
- independent scan processors

Current priority:
HIGH

### execution/paper.py

Current responsibilities include:
- trade lifecycle handling
- stop-loss handling
- target management
- trailing logic
- tranche handling
- position monitoring
- portfolio tracking
- trade persistence coordination

Current risks:
- execution complexity growth
- monitoring coupling
- future broker integration difficulty

Future direction:
- execution engine separation
- monitoring service separation
- portfolio management modularization

Current priority:
HIGH

### db/repository.py

Current responsibilities include:
- all persistence access
- research logging
- analytics persistence
- trade persistence
- telemetry persistence
- pattern memory persistence

Current risks:
- repository growth over time
- query concentration
- future analytics scaling challenges

However:
centralized repository architecture is currently still the correct design choice.

Future direction:
- eventual repository segmentation by domain
- analytics repository separation
- research repository separation
- execution repository separation

Current priority:
MEDIUM

### research Utilities

Current state:
- many standalone scripts
- duplicated logic
- inconsistent methodology
- fragmented research workflows

Current risks:
- research inconsistency
- false conclusions
- duplicated experimentation
- edge validation instability

Future direction:
- centralized Research Engine V2
- standardized research methodology
- reusable research framework

Current priority:
VERY HIGH

## Current Coupling Risks

MJONAI currently contains several areas of increasing architectural coupling risk due to rapid feature evolution and centralized orchestration growth.

### Orchestration Coupling

Large portions of runtime coordination currently depend on:
- main.py
- scheduler-driven sequencing
- centralized runtime orchestration

This creates:
- hidden dependencies
- sequencing fragility
- debugging complexity
- scaling difficulty

### Signal-to-Execution Coupling

Current signal generation and execution flows are still relatively tightly connected.

Risks include:
- difficult simulation separation
- harder portfolio experimentation
- limited execution abstraction
- future live trading complexity

Future direction:
- cleaner signal abstraction
- execution engine isolation
- portfolio simulation independence

### Research-to-Production Mixing

The repository currently mixes:
- experimental research scripts
- operational runtime systems
- prototype testing workflows
- production-intent components

This creates:
- inconsistent standards
- research contamination risk
- operational ambiguity
- future deployment complexity

### AI Integration Coupling

Current AI systems are partially embedded into:
- signal workflows
- approval workflows
- orchestration logic

Risks include:
- difficult AI replacement
- model-provider lock-in risk
- inconsistent reasoning dependencies
- future scaling complexity

Future direction:
- standardized AI interfaces
- model abstraction layers
- independent reasoning services

### Persistence Coupling

Repository architecture is centralized and structurally strong, but growing persistence responsibilities may eventually create:
- oversized repository logic
- analytics coupling
- execution coupling
- research query concentration

Current design remains correct for current maturity level, but future segmentation will eventually become necessary.

### Runtime State Coupling

Several runtime systems currently depend on:
- shared runtime state
- sequential coordination
- scheduler timing assumptions

This creates:
- runtime fragility
- hidden operational assumptions
- future concurrency limitations

### Research Methodology Coupling

Current research workflows depend heavily on:
- standalone scripts
- duplicated backtest logic
- inconsistent testing assumptions

This creates:
- unreliable comparisons
- methodology drift
- edge validation inconsistency

This is currently one of the highest-priority future stabilization areas.

## Safe Future Split Candidates

The following systems are strong candidates for future modular separation once MJONAI reaches higher operational maturity.

These separations should happen gradually and only after sufficient stabilization.

### Runtime Orchestration Service

Current source:
- main.py

Future split direction:
- startup coordinator
- scheduler coordinator
- monitoring coordinator
- analytics coordinator
- runtime health coordinator

Goal:
reduce orchestration concentration and improve maintainability.

### Signal Pipeline Engine

Current source:
- strategy/signal_scanner.py

Future split direction:
- strategy execution engine
- filtering engine
- ranking engine
- AI validation engine
- signal persistence engine

Goal:
create a modular research-grade signal pipeline.

### Execution Engine

Current source:
- execution/paper.py

Future split direction:
- order simulation engine
- portfolio manager
- stop-loss manager
- trailing manager
- monitoring engine
- execution analytics layer

Goal:
enable cleaner broker integration and portfolio simulation.

### Research Engine V2

Current source:
- fragmented research scripts

Future split direction:
- standardized backtest engine
- portfolio simulator
- walk-forward framework
- statistical validation framework
- regime segmentation engine
- analytics framework

Goal:
create institution-style research infrastructure.

### AI Intelligence Layer

Current source:
- agents/
- ask.py
- ask_ai.py

Future split direction:
- reasoning service
- signal interpretation engine
- research intelligence assistant
- architecture cognition assistant
- operational analysis assistant

Goal:
enable repo-aware AI cognition and cleaner model abstraction.

### Persistence Layer Segmentation

Current source:
- db/repository.py

Future split direction:
- execution repository
- research repository
- analytics repository
- telemetry repository
- AI memory repository

Goal:
prevent oversized persistence concentration over time.

### Monitoring and Observability Layer

Current state:
- logs + Telegram notifications

Future split direction:
- runtime monitoring dashboard
- execution monitoring
- research observability
- operational health tracking
- incident detection

Goal:
improve operational visibility and production readiness.

### Important Constraint

These future splits should happen:
- gradually
- only when operational pain becomes real
- only after sufficient stabilization
- without premature microservice complexity

Premature splitting may create:
- unnecessary complexity
- coordination overhead
- debugging difficulty
- architecture fragmentation

## Systems That Should Remain Centralized

Certain systems inside MJONAI should remain centralized for a long time because centralization currently provides:
- architectural clarity
- consistency
- lower operational complexity
- easier debugging
- faster iteration

Premature decentralization would likely damage project stability.

### Repository Persistence Layer

Current source:
- db/repository.py

Reason to remain centralized:
- unified data access patterns
- consistent persistence logic
- simplified debugging
- reduced query fragmentation
- easier analytics consistency

Future segmentation should only occur after:
- major scaling requirements
- analytics bottlenecks
- operational pain becomes significant

### Strategy Registry Architecture

Current source:
- strategy/registry/

Reason to remain centralized:
- standardized strategy interfaces
- easier strategy comparison
- consistent signal lifecycle handling
- simpler research coordination

Maintaining a unified strategy registry is currently the correct design choice.

### Runtime Configuration and Constants

Current source:
- core/constants.py
- shared runtime configuration

Reason to remain centralized:
- operational consistency
- easier runtime coordination
- simpler environment management
- reduced configuration drift

### Risk Governance Layer

Current source:
- risk/

Reason to remain centralized:
- unified risk enforcement
- consistent safety rules
- centralized emergency controls
- portfolio-wide protection logic

Risk fragmentation would create dangerous inconsistencies.

### Research Result Persistence

Research persistence should remain centralized because:
- research comparability matters
- analytics consistency matters
- signal lifecycle continuity matters
- future AI learning requires unified datasets

Fragmented research storage would weaken future intelligence systems.

### Project Cognition Documentation

Current source:
- docs/current_state/

Reason to remain centralized:
- single source of truth
- AI cognition consistency
- onboarding consistency
- architecture clarity

This documentation layer is now becoming operational infrastructure itself.

### Important Principle

MJONAI should avoid premature:
- microservice fragmentation
- distributed complexity
- unnecessary orchestration layers
- infrastructure overengineering

Current project maturity still benefits heavily from:
- centralized cognition
- centralized governance
- centralized operational visibility

## Systems That Should Become Modular

Certain MJONAI systems will benefit significantly from gradual modularization as the project matures.

These systems are likely to experience:
- complexity growth
- scaling pressure
- increasing orchestration burden
- expanding research requirements

### Runtime Orchestration Layer

Current source:
- main.py

Reason for modularization:
- orchestration concentration is already high
- runtime responsibilities continue growing
- debugging complexity will increase over time

Future modular areas:
- startup orchestration
- scheduler coordination
- monitoring coordination
- analytics coordination
- runtime health management

### Signal Processing Pipeline

Current source:
- strategy/signal_scanner.py

Reason for modularization:
- increasing strategy count
- growing filtering complexity
- expanding validation logic
- AI integration growth

Future modular areas:
- signal generation
- filtering stages
- ranking systems
- AI validation stages
- persistence coordination

### Research Infrastructure

Current state:
- fragmented standalone scripts

Reason for modularization:
- duplicated methodology
- inconsistent assumptions
- growing research complexity
- unreliable comparison risk

Future modular areas:
- standardized backtest engine
- walk-forward framework
- portfolio simulator
- regime segmentation engine
- analytics engine

### Execution and Monitoring Layer

Current source:
- execution/paper.py

Reason for modularization:
- trade lifecycle complexity
- portfolio handling growth
- monitoring expansion
- future broker integration

Future modular areas:
- execution engine
- portfolio manager
- stop-loss engine
- monitoring engine
- execution analytics

### AI Intelligence Layer

Current source:
- agents/
- ask.py
- ask_ai.py

Reason for modularization:
- evolving AI responsibilities
- future multi-model integration
- repo cognition requirements
- operational analysis expansion

Future modular areas:
- reasoning engine
- signal interpretation service
- architecture cognition assistant
- research assistant
- operational intelligence assistant

### Analytics and Reporting Layer

Current state:
- partially fragmented utilities

Reason for modularization:
- growing analytics requirements
- reporting complexity growth
- future dashboard requirements
- observability expansion

Future modular areas:
- analytics engine
- reporting engine
- visualization systems
- telemetry processing
- observability services

### Important Principle

Modularization should happen:
- gradually
- based on operational pain
- after stabilization
- with strong interface boundaries

MJONAI should avoid:
- premature distributed architecture
- unnecessary infrastructure complexity
- artificial modularization without operational need

## Experimental vs Stable Boundaries

MJONAI currently contains both:
- stable operational systems
and:
- rapidly evolving experimental systems

Maintaining clear separation between these areas is critical for long-term project stability.

### Stable Operational Areas

The following systems are currently relatively stable and should evolve cautiously:

#### Persistence Architecture
- db/repository.py
- structured research persistence
- trade lifecycle persistence
- analytics persistence

These systems form the core memory infrastructure of MJONAI.

#### Risk Governance
- risk/
- emergency controls
- exposure logic
- deterministic veto systems

Risk systems should remain conservative and carefully controlled.

#### Strategy Registry Structure
- strategy/registry/
- standardized strategy interfaces
- signal lifecycle coordination

The registry architecture itself is structurally strong even if strategies evolve.

#### Runtime Cognition Documentation
- docs/current_state/
- architecture cognition
- runtime cognition
- stabilization cognition

This documentation layer now acts as operational infrastructure.

### Experimental Areas

The following systems are intentionally experimental and expected to evolve rapidly:

#### AI Intelligence Layer
- agents/
- ask.py
- ask_ai.py

AI cognition architecture is still highly experimental.

Expected future evolution includes:
- repo-aware cognition
- architecture-aware assistants
- persistent AI memory
- research intelligence assistants

#### Research Methodology
- standalone research scripts
- experimental backtests
- strategy experimentation

Research infrastructure is still transitioning toward:
- standardized methodology
- reusable research engines
- institutional validation workflows

#### Strategy Evolution
Individual strategies are expected to evolve continuously through:
- parameter refinement
- filtering improvements
- regime adaptation
- research discoveries

#### Analytics Intelligence
Current analytics workflows remain experimental and fragmented.

Future analytics direction is still evolving significantly.

### Important Operational Principle

Stable systems should protect:
- operational consistency
- persistence integrity
- risk governance
- runtime safety

Experimental systems should remain:
- isolated
- replaceable
- iteration-friendly
- loosely coupled

### Critical Risk

One of the biggest long-term risks is:
- experimental logic contaminating stable operational infrastructure

Especially:
- unstable AI reasoning
- unreliable research conclusions
- experimental execution logic

must not compromise:
- persistence integrity
- risk governance
- operational safety

## Research vs Production Boundaries

MJONAI is currently primarily a research-oriented quantitative intelligence system.

Maintaining clear separation between:
- research systems
and:
- production-intent systems

is critical for long-term reliability and safety.

### Current Reality

Most of the current project should still be considered:
- research infrastructure
- experimentation infrastructure
- edge discovery infrastructure
- paper-trading infrastructure

It should not yet be treated as:
- production-grade trading infrastructure
- institutionally hardened execution infrastructure
- fully autonomous trading infrastructure

### Research-Oriented Areas

The following systems are primarily research-oriented:

#### Backtesting Infrastructure
Current backtesting systems are:
- experimental
- methodology-evolving
- not fully standardized
- not yet institution-grade

#### Strategy Development
Strategies are still undergoing:
- edge validation
- parameter evolution
- robustness testing
- regime testing

#### AI-Assisted Reasoning
Current AI systems are:
- assistive
- experimental
- inconsistent
- non-deterministic

They should not yet be trusted with:
- autonomous capital deployment
- unsupervised execution decisions
- production governance authority

#### Analytics and Pattern Discovery
Current analytics systems are still evolving and primarily exist for:
- experimentation
- insight generation
- exploratory analysis

### Production-Oriented Areas

The following areas already require production-style discipline:

#### Risk Governance
Risk systems should already behave conservatively and deterministically.

Includes:
- emergency controls
- exposure limits
- kill switches
- portfolio protection logic

#### Persistence Integrity
Research memory integrity is critical because future:
- analytics
- AI learning
- edge validation
depends on reliable historical data.

#### Runtime Stability
Even during research phases:
- runtime orchestration
- scheduler coordination
- persistence workflows
should remain operationally stable.

### Important Principle

Research systems should optimize for:
- exploration
- iteration speed
- experimentation
- edge discovery

Production systems should optimize for:
- reliability
- determinism
- auditability
- operational safety

Confusing these priorities creates major long-term risk.

### Long-Term Direction

Over time, MJONAI should evolve toward:
- production-grade execution
- institution-style observability
- hardened runtime orchestration
- safer AI integration
- validated research pipelines

But:
research correctness must come before production scaling.

## AI System Boundaries

MJONAI currently includes early-stage AI-assisted operational intelligence systems.

Clear architectural boundaries around AI systems are critical because AI behavior is:
- probabilistic
- evolving
- non-deterministic
- model-dependent

AI systems must remain carefully isolated from critical deterministic infrastructure.

### Current AI Role

AI currently acts primarily as:
- assistive intelligence
- qualitative reasoning layer
- signal interpretation layer
- supervisory analysis layer

AI does not currently operate as:
- autonomous trading authority
- autonomous risk controller
- autonomous execution controller

### Areas AI Should Influence

AI systems may assist with:
- signal interpretation
- trade reasoning
- market commentary
- qualitative validation
- research assistance
- architecture cognition
- onboarding support
- operational analysis

These are appropriate areas for probabilistic reasoning systems.

### Areas AI Should NOT Control

AI systems should not directly control:
- persistence integrity
- portfolio kill switches
- deterministic risk governance
- emergency shutdown systems
- core execution safety logic
- capital protection systems

These systems must remain deterministic and auditable.

### Current AI Limitations

Current AI systems still suffer from:
- context loss
- inconsistent reasoning
- hallucinations
- weak long-term memory
- architecture misunderstanding
- provider dependency

These limitations make strong isolation boundaries essential.

### Future AI Direction

Future AI evolution may include:
- repo-aware cognition
- architecture-aware assistants
- persistent project memory
- research intelligence assistants
- operational analysis assistants
- debugging assistants

However:
future AI systems should still remain:
- supervised
- auditable
- sandboxed from critical infrastructure

### Important Architectural Principle

AI systems should operate as:
- advisory intelligence
rather than:
- uncontrolled autonomous authority

Especially during current project maturity stages.

### Critical Long-Term Risk

One of the biggest future risks is:
- over-trusting probabilistic AI reasoning in deterministic operational domains

Especially:
- risk management
- execution safety
- capital protection
must remain governed by deterministic systems first.

## Persistence Layer Boundaries

The persistence architecture is currently one of the strongest and most important systems inside MJONAI.

It acts as:
- research memory
- trade lifecycle memory
- analytics memory
- AI verdict memory
- operational telemetry memory

Protecting persistence integrity is critical for long-term project success.

### Current Architecture

Current persistence architecture is centralized through:
- db/repository.py

This is currently the correct architectural choice because it provides:
- unified data access
- consistency
- auditability
- easier debugging
- controlled persistence behavior

### Persistence Responsibilities

Current persistence layer stores:
- signal intelligence
- trade lifecycle information
- AI reasoning
- pattern memory
- analytics outputs
- forward returns
- runtime telemetry
- portfolio snapshots
- scan history
- operational health data

This persistence layer already behaves more like:
- a research intelligence datastore
than:
- a simple trading database.

### Systems That Must Remain Deterministic

The following persistence areas must remain deterministic and carefully controlled:
- trade persistence
- portfolio state
- risk state
- execution outcomes
- analytics truth data

Experimental logic should never corrupt these systems.

### Experimental Data Isolation

Experimental systems including:
- AI reasoning
- experimental analytics
- prototype research workflows

should remain isolated from:
- core persistence integrity
- production-truth datasets
- operational safety systems

### Future Segmentation Direction

Future segmentation may eventually include:
- execution repository
- analytics repository
- research repository
- telemetry repository
- AI memory repository

However:
premature persistence fragmentation would currently create:
- coordination complexity
- debugging difficulty
- inconsistent data governance

### Important Principle

Persistence architecture should prioritize:
- consistency
- auditability
- deterministic behavior
- research integrity

over:
- premature scaling complexity
- unnecessary infrastructure sophistication

### Long-Term Importance

The persistence layer is likely to become one of the most valuable long-term assets inside MJONAI because future:
- analytics
- edge discovery
- AI-assisted research
- adaptive intelligence
will depend heavily on high-quality historical research memory.

## Runtime Orchestration Boundaries

Runtime orchestration is currently one of the most centralized and operationally important layers inside MJONAI.

Large portions of system coordination currently flow through:
- main.py
- scheduler-driven workflows
- sequential runtime coordination

Maintaining strong orchestration boundaries is critical to prevent uncontrolled complexity growth.

### Current Orchestration Responsibilities

Current orchestration handles:
- startup sequencing
- scheduler coordination
- signal scan triggering
- AI validation coordination
- execution triggering
- monitoring activation
- analytics workflows
- reporting workflows
- runtime health handling

This creates significant orchestration concentration.

### What Orchestration SHOULD Control

The orchestration layer should coordinate:
- lifecycle sequencing
- runtime scheduling
- operational state transitions
- service coordination
- runtime visibility

Orchestration should act as:
- coordinator
rather than:
- business logic owner

### What Orchestration SHOULD NOT Own

The orchestration layer should gradually avoid directly owning:
- signal generation logic
- execution logic
- analytics calculations
- persistence rules
- risk logic
- AI reasoning logic

These systems should eventually remain independently testable and modular.

### Current Architectural Risk

The biggest orchestration risks currently include:
- growing runtime coupling
- hidden dependency chains
- sequencing fragility
- oversized orchestration responsibilities
- difficult debugging paths

As MJONAI grows, orchestration complexity may increase faster than expected.

### Future Direction

Future orchestration evolution may gradually move toward:
- modular runtime coordinators
- event-driven coordination
- clearer service boundaries
- runtime health orchestration
- independent workflow handlers

However:
premature orchestration fragmentation should be avoided.

### Important Principle

Orchestration should focus on:
- coordination
- sequencing
- operational flow management

NOT:
- deep business logic ownership

This separation is important for:
- maintainability
- debuggability
- scalability
- research correctness

### Long-Term Goal

The long-term goal is:
- thin orchestration
combined with:
- strong modular services
and:
- deterministic governance boundaries

without introducing unnecessary distributed complexity too early.

## Future Refactor Principles

Future MJONAI refactors should follow strict architectural principles to avoid accidental complexity, instability, and research degradation.

### Refactor Only When Operational Pain Is Real

Systems should only be split or redesigned when:
- complexity becomes measurable
- debugging becomes painful
- scaling limitations become real
- operational friction becomes significant

Premature refactoring creates unnecessary instability.

### Protect Stable Infrastructure

Stable systems including:
- persistence
- risk governance
- runtime safety
- deterministic controls

should evolve cautiously and conservatively.

Experimental systems should never destabilize core operational infrastructure.

### Prefer Clear Boundaries Over Clever Architecture

MJONAI should prioritize:
- understandable systems
- auditable systems
- debuggable systems
- deterministic workflows

over:
- overly abstract architectures
- unnecessary framework complexity
- premature distributed systems

### Centralization Is Acceptable at Current Scale

At current project maturity:
- centralized orchestration
- centralized persistence
- centralized governance

remain correct architectural choices.

Premature microservice-style splitting would likely create:
- debugging difficulty
- coordination overhead
- operational fragility

### Research Integrity Comes First

Refactors must preserve:
- historical consistency
- research comparability
- analytics integrity
- signal lifecycle continuity

Breaking research continuity would damage long-term intelligence quality.

### Refactor Gradually

Major architecture changes should happen:
- incrementally
- with rollback safety
- with operational verification
- with research validation

Large uncontrolled rewrites create major project risk.

### Maintain Strong Operational Visibility

Refactors should improve:
- runtime visibility
- debugging clarity
- operational observability
- architectural understanding

Not reduce them.

### AI Systems Must Remain Sandboxed

AI-related refactors should maintain:
- deterministic governance
- persistence safety
- execution safety
- operational auditability

AI should remain advisory rather than authoritative.

### Documentation Is Operational Infrastructure

Documentation should be treated as:
- architecture memory
- operational cognition
- onboarding infrastructure
- AI context infrastructure

Major refactors should update documentation continuously.

### Long-Term Principle

MJONAI should evolve through:
- controlled stabilization
- research rigor
- operational clarity
- gradual sophistication

not through:
- uncontrolled feature growth
- AI hype cycles
- random architectural experimentation

## Important Refactor Warnings

MJONAI should avoid several high-risk architectural mistakes that commonly damage evolving research and trading systems.

### Avoid Large Uncontrolled Rewrites

Large rewrite attempts often create:
- hidden regressions
- research inconsistency
- architecture drift
- operational instability
- lost institutional memory

MJONAI should evolve incrementally rather than through massive rewrites.

### Avoid Premature Microservices

At current project maturity, premature distributed architecture would likely create:
- debugging difficulty
- operational fragmentation
- deployment complexity
- runtime coordination problems

Current architecture still benefits heavily from:
- centralized cognition
- centralized governance
- centralized observability

### Avoid AI-Driven Architecture Decisions

AI-generated suggestions should never replace:
- operational reasoning
- research rigor
- deterministic governance
- architectural judgment

AI systems currently lack sufficient:
- repo-wide understanding
- operational reliability
- long-term architectural reasoning

Human-guided architectural control remains essential.

### Avoid Research Methodology Drift

One of the biggest long-term risks is:
- inconsistent backtesting assumptions
- duplicated research logic
- changing evaluation criteria
- curve-fitting pressure

Research methodology must gradually become:
- standardized
- reproducible
- auditable
- statistically rigorous

### Avoid Mixing Experimental and Stable Logic

Experimental systems including:
- AI reasoning
- prototype strategies
- experimental analytics

must remain isolated from:
- persistence integrity
- risk governance
- operational safety systems

Experimental contamination of stable infrastructure creates major long-term instability risk.

### Avoid Over-Optimizing Win Rate

High win rate alone does not imply:
- positive expectancy
- robustness
- scalability
- survivability

Research should prioritize:
- expectancy
- robustness
- drawdown behavior
- regime consistency
- risk-adjusted performance

over raw win percentage.

### Avoid Overengineering Too Early

MJONAI does not yet need:
- Kubernetes-scale infrastructure
- complex distributed systems
- advanced deployment orchestration
- enterprise-scale observability stacks

Premature infrastructure sophistication creates:
- maintenance burden
- cognitive overload
- slower iteration
- architectural fragility

### Avoid Treating AI as Trusted Authority

Current AI systems remain:
- probabilistic
- inconsistent
- context-limited
- hallucination-prone

AI should remain:
- advisory
- supervised
- sandboxed

especially around:
- execution safety
- risk governance
- persistence integrity

### Avoid Losing Research Memory Integrity

Historical research memory is becoming one of MJONAI’s most valuable assets.

Corrupted or inconsistent historical datasets would damage:
- analytics quality
- edge discovery
- future adaptive intelligence
- AI-assisted research

Persistence integrity must remain a top priority.

### Long-Term Warning

The biggest long-term risk is not:
- lack of AI
- lack of strategies
- lack of automation

The biggest risk is:
- uncontrolled complexity growth
combined with:
- fragmented operational cognition

Controlled stabilization must remain a permanent architectural principle.

## Orchestration Boundary

main.py should gradually evolve toward:
- thin orchestration shell

Future orchestration responsibilities may gradually move into:
- orchestration/
modules

Examples:
- scheduler coordination
- runtime health monitoring
- startup sequencing
- runtime guardrails

main.py should avoid becoming:
- business logic container
- strategy engine
- analytics processor
- AI reasoning layer

## Safe Orchestration Extraction Rules

The following types of logic are safe candidates for gradual extraction from main.py into orchestration/ modules:

- health monitoring
- startup checks
- scheduler coordination
- runtime guardrails
- process lifecycle handling
- telemetry aggregation

The following should NOT move into orchestration/:

- strategy logic
- research logic
- AI reasoning
- portfolio analytics
- market analysis
- execution calculations

main.py should gradually evolve toward:
- startup coordination
- runtime scheduling
- orchestration wiring
- graceful shutdown coordination

Refactoring philosophy:
- small extractions only
- runtime validation after every extraction
- no mass rewrites
- no aggressive restructuring