# MJONAI Runtime Flow

> This document explains the runtime execution flow from system startup through observation, analysis, decision making, execution, monitoring, and shutdown.

## System Startup Flow

MJONAI startup currently follows a scheduler-driven orchestration model.

Primary startup sequence:

1. Runtime logger initialization
2. Environment and dependency loading
3. Database initialization
4. Broker connectivity initialization
5. Health checks and validation
6. Market regime analysis
7. MQI and macro condition evaluation
8. Scheduler initialization
9. Background monitoring loop startup
10. Runtime orchestration activation

Current runtime is heavily coordinated through:
- main.py
- scheduled jobs
- periodic monitoring loops
- orchestration handlers

Startup responsibilities currently include:
- validating market readiness
- preparing signal scanning
- preparing execution environment
- preparing monitoring systems
- enabling analytics and reporting jobs

Current startup architecture is centralized and orchestration-heavy.

## Runtime Orchestration Flow

MJONAI currently operates through a centralized orchestration model primarily controlled from main.py.

Main orchestration responsibilities include:
- scheduler coordination
- scan cycle management
- risk gate enforcement
- AI validation triggering
- execution coordination
- monitoring jobs
- analytics jobs
- reporting jobs

The orchestration system currently coordinates:

### Market Intelligence Layer
- market regime analysis
- MQI evaluation
- macro condition checks
- volatility state analysis

### Signal Intelligence Layer
- multi-strategy scanning
- confidence filtering
- signal ranking
- sector filtering
- earnings filtering
- signal approval workflows

### AI Validation Layer
- bullish validation agent
- supervisory review agent
- AI reasoning collection
- signal approval/rejection logic

### Execution Layer
- paper trade creation
- trade lifecycle handling
- risk monitoring
- stop loss handling
- target handling
- trailing stop handling

### Research Intelligence Layer
- signal intelligence logging
- forward return tracking
- outcome analytics
- performance tracking
- pattern intelligence persistence

### Communication Layer
- Telegram alerts
- runtime notifications
- reporting communication

Current orchestration architecture is functional but highly centralized.

Large portions of runtime dependency flow currently pass through main.py.

## Market Open Flow

## Signal Scanning Flow

MJONAI signal generation currently follows a layered multi-stage scanning architecture.

Primary signal flow:

Market Data
→ Strategy Evaluation
→ Signal Generation
→ Confidence Filtering
→ Sector Filtering
→ Earnings Filtering
→ Trade Construction
→ Risk Validation
→ AI Validation
→ Supervisor Approval
→ Execution Eligibility
→ Research Logging

### Strategy Layer
Signal generation is handled through:
- strategy registry architecture
- multiple independent strategies
- strategy-specific signal logic
- confidence scoring systems

Current strategy types include:
- momentum systems
- mean reversion systems
- breakout systems
- price action systems
- volatility-based systems

### Filtering Layer
Signals currently pass through multiple filters:
- confidence filters
- market regime filters
- sector filters
- earnings-event filters
- volatility filters
- risk checks

### AI Validation Layer
Approved candidate signals may pass through:
- bullish validation agent
- supervisory review layer
- AI reasoning workflows

AI systems currently contribute:
- qualitative reasoning
- approval/rejection opinions
- confidence interpretation
- concern identification

### Risk Validation Layer
Signals are checked for:
- risk-reward viability
- exposure control
- market condition alignment
- execution eligibility

### Research Intelligence Logging
Signal lifecycle information is logged for:
- future analytics
- forward return analysis
- signal quality evaluation
- pattern intelligence
- AI verdict tracking
- research persistence

Current signal architecture is one of the strongest and most mature parts of MJONAI.

## AI Validation Flow

MJONAI currently includes an early-stage AI-assisted signal validation architecture.

The AI layer currently operates as:
- assistive intelligence
- validation layer
- supervisory reasoning system

It does not yet operate as:
- autonomous trading intelligence
- self-learning execution intelligence
- fully adaptive decision-making system

### Current AI Flow

Candidate Signal
→ Bull Agent Review
→ AI Reasoning Generation
→ Concern Identification
→ Confidence Interpretation
→ Supervisor Review
→ Final Approval/Rejection Decision

### Bull Agent Responsibilities
The bullish validation agent currently contributes:
- signal interpretation
- reasoning generation
- confidence evaluation
- trade concern identification
- directional opinion

### Supervisor Agent Responsibilities
The supervisor layer currently contributes:
- final approval/rejection
- supervisory reasoning
- final decision enforcement
- trade quality oversight

### AI Integration Purpose
Current AI integration primarily exists to:
- improve signal interpretation
- provide qualitative reasoning
- create explainable signal workflows
- experiment with AI-assisted trading operations
- build foundations for future intelligence systems

### Current AI Limitations
The AI system currently has major limitations:
- no persistent long-term memory
- no repo-wide cognition
- no autonomous debugging
- limited contextual awareness
- inconsistent reasoning quality
- no true adaptive learning loop

### Long-Term AI Direction
Long-term vision includes:
- repo-aware AI cognition
- architecture-aware AI assistants
- persistent project memory
- autonomous operational analysis
- AI-assisted debugging
- AI-assisted research intelligence
- eventually adaptive trading intelligence

Current AI systems should be viewed as:
- foundational intelligence experiments
rather than:
- mature autonomous AI systems

## Trade Execution Flow

MJONAI currently uses a paper-trading-based execution architecture.

Current execution flow:

Approved Signal
→ Trade Construction
→ Risk Validation
→ Paper Trade Creation
→ Position Persistence
→ Monitoring Activation
→ Stop Loss / Target Tracking
→ Trailing Logic
→ Position Exit
→ Outcome Logging
→ Analytics Persistence

### Execution Responsibilities

Current execution system handles:
- paper trade lifecycle management
- trade persistence
- target tracking
- stop loss handling
- trailing stop handling
- tranche handling
- portfolio tracking
- position state management

### Trade State Tracking

Execution layer currently tracks:
- entry price
- stop loss
- targets
- trade direction
- position size
- unrealized PnL
- realized PnL
- MAE/MFE metrics
- trade duration
- exit reasons
- execution outcomes

### Research Context Persistence

Execution flow also stores:
- market context
- strategy identity
- AI verdicts
- confidence values
- pattern information
- signal quality information
- trade outcome intelligence

This creates a research-oriented trade memory system.

### Current Execution Reality

Current execution architecture is:
- paper-trading focused
- research-oriented
- experimentation-driven

It is not yet:
- production-grade
- broker-grade
- latency-optimized
- institutionally hardened

### Long-Term Execution Direction

Long-term goals include:
- broker-integrated execution
- improved realism
- advanced portfolio handling
- production-grade order management
- institutional execution workflows

## Position Monitoring Flow

MJONAI currently includes an active position monitoring architecture for paper-traded positions.

Primary monitoring flow:

Open Positions
→ Market Price Updates
→ Stop Loss Checks
→ Target Checks
→ Trailing Stop Evaluation
→ Risk Monitoring
→ Exit Decision
→ Position Closure
→ Outcome Persistence

### Monitoring Responsibilities

Current monitoring system handles:
- open position tracking
- unrealized PnL updates
- stop loss monitoring
- target monitoring
- trailing stop management
- tranche-level management
- exposure observation
- trade duration tracking

### Risk Monitoring

The monitoring system currently evaluates:
- drawdown exposure
- stop-loss breach conditions
- target achievement
- trailing stop activation
- abnormal trade behavior

### Outcome Intelligence

Position closure workflows currently persist:
- exit reasons
- realized PnL
- trade duration
- MAE/MFE behavior
- pattern outcome data
- AI outcome tracking
- signal quality results

### Research Importance

The monitoring and exit system is critical because it transforms:
- raw signals
into:
- measurable research outcomes

This enables:
- strategy evaluation
- signal quality analysis
- future edge discovery
- pattern intelligence research

### Current Monitoring Reality

Current monitoring architecture is:
- functional for paper trading
- research-oriented
- lifecycle-aware

However:
- realtime production monitoring is not yet mature
- institutional-grade observability does not yet exist
- distributed monitoring architecture is not implemented

## Research Logging Flow

MJONAI currently includes a research-oriented intelligence persistence architecture.

Research logging exists to transform:
- signals
- trades
- AI decisions
- market context
into:
- structured research intelligence

### Current Research Logging Flow

Signal Generated
→ Signal Context Collection
→ AI Verdict Collection
→ Trade Lifecycle Tracking
→ Outcome Persistence
→ Analytics Processing
→ Research Intelligence Storage

### Logged Research Context

Current system stores information including:
- strategy identity
- market regime
- volatility conditions
- confidence scores
- AI reasoning
- supervisor decisions
- signal quality
- entry and exit information
- stop loss and target behavior
- trade outcomes
- MAE/MFE statistics
- pattern information

### Purpose of Research Persistence

Research persistence currently supports:
- forward return analysis
- signal quality evaluation
- strategy comparison
- trade behavior analysis
- pattern intelligence research
- AI decision tracking
- future edge discovery

### Current Research Architecture

Research infrastructure currently includes:
- signal intelligence logging
- trade lifecycle analytics
- forward returns analysis
- analytics workflows
- pattern outcome persistence
- portfolio analytics foundations

### Current Strength

Research intelligence persistence is one of the strongest architectural areas currently present in MJONAI.

The project already behaves more like:
- a research intelligence system

than:
- a simple trading bot

### Current Limitations

Current limitations include:
- limited automated insight extraction
- minimal adaptive learning
- incomplete pattern intelligence systems
- limited automated research workflows
- no advanced factor modeling yet

### Long-Term Direction

Long-term research direction includes:
- automated edge discovery
- adaptive research intelligence
- AI-assisted market analysis
- advanced probabilistic modeling
- self-improving signal intelligence

## Analytics and Reporting Flow

MJONAI currently includes an evolving analytics and reporting architecture.

The analytics layer exists to transform:
- raw trades
- signal behavior
- AI decisions
- market outcomes
into:
- measurable research intelligence

### Current Analytics Flow

Signals and Trades
→ Outcome Tracking
→ Forward Return Analysis
→ Performance Aggregation
→ Pattern Analysis
→ Reporting Workflows
→ Research Evaluation

### Current Analytics Responsibilities

The analytics system currently supports:
- strategy performance analysis
- signal quality evaluation
- forward return analysis
- trade outcome analysis
- portfolio performance tracking
- AI verdict evaluation
- pattern outcome tracking

### Reporting Responsibilities

Current reporting workflows include:
- runtime summaries
- trade summaries
- research analytics outputs
- monitoring notifications
- Telegram reporting

### Existing Research Utilities

The project currently contains multiple analytics and research utilities including:
- forward return analysis
- deep analysis workflows
- grid testing systems
- strategy comparison workflows
- cost modeling
- portfolio analysis utilities

### Current Reporting Reality

Reporting infrastructure currently exists primarily for:
- experimentation
- research evaluation
- operational visibility

It is not yet:
- institution-grade reporting infrastructure
- centralized analytics architecture
- production observability platform

### Current Limitations

Current limitations include:
- fragmented analytics workflows
- no unified research dashboard
- manual analysis dependence
- incomplete visualization systems
- limited automated insight generation

### Long-Term Direction

Long-term analytics goals include:
- centralized research intelligence
- adaptive analytics systems
- AI-assisted insight generation
- automated pattern discovery
- advanced portfolio intelligence
- institutional-grade observability

## Scheduler Architecture

MJONAI currently operates using a scheduler-driven orchestration architecture.

The scheduler acts as the central operational coordination layer for:
- scan cycles
- monitoring cycles
- analytics jobs
- reporting workflows
- runtime maintenance tasks

### Current Scheduler Responsibilities

The scheduler currently coordinates:

#### Market Preparation
- morning startup routines
- market regime analysis
- MQI evaluation
- macro checks

#### Signal Operations
- periodic signal scans
- strategy evaluation cycles
- signal filtering workflows
- AI validation triggering

#### Execution Monitoring
- open position monitoring
- stop loss checks
- target monitoring
- trailing stop evaluation

#### Research and Analytics
- forward return analysis
- research intelligence updates
- analytics processing
- reporting workflows

#### Communication Tasks
- Telegram notifications
- runtime alerts
- operational summaries

### Current Architecture Characteristics

The scheduler architecture is currently:
- centralized
- orchestration-heavy
- sequentially coordinated
- runtime-state dependent

Large portions of operational control currently flow through:
- main.py
- scheduled jobs
- periodic runtime loops

### Current Strengths

Current strengths include:
- structured runtime coordination
- operational automation
- lifecycle-driven orchestration
- clear operational sequencing

### Current Weaknesses

Current weaknesses include:
- orchestration concentration
- oversized runtime coordination file
- limited modular scheduler separation
- limited distributed execution capability

### Long-Term Direction

Future scheduler direction may include:
- modular orchestration services
- distributed runtime coordination
- event-driven workflows
- AI-assisted operational control
- autonomous runtime management

## Runtime Dependencies

## Current Runtime Risks

MJONAI currently contains several architectural and operational risks due to rapid evolution, experimental development patterns, and centralized orchestration design.

### Centralized Runtime Dependency Risk

A large portion of operational coordination currently flows through:
- main.py
- centralized scheduler logic
- tightly coupled orchestration flows

This creates risks including:
- scaling difficulty
- orchestration complexity
- debugging complexity
- future maintainability challenges

### Experimental System Mixing

The repository currently contains a mix of:
- operational systems
- research systems
- experimental systems
- partially-completed systems

This increases:
- architectural ambiguity
- maintenance overhead
- cognitive load
- future cleanup complexity

### AI Dependency and Context Risk

Current development process still depends heavily on:
- AI-assisted coding
- evolving documentation
- session-based context

Risks include:
- context fragmentation
- inconsistent implementation direction
- architectural drift
- documentation lag

### Oversized Runtime Components

Some runtime components are currently too large and multi-responsibility heavy.

Examples include:
- main.py
- orchestration-heavy runtime logic
- broad execution coordination layers

This increases:
- refactor difficulty
- onboarding difficulty
- runtime coupling risk

### Limited Production Hardening

Current system is still primarily:
- research-oriented
- experimentation-driven
- paper-trading focused

The project does not yet have:
- production-grade observability
- institutional deployment practices
- advanced fault tolerance
- robust operational recovery systems

### Documentation Evolution Risk

Project direction has evolved significantly beyond the original master planning documents.

Without continuous documentation maintenance:
- AI cognition quality may degrade
- onboarding complexity may increase
- architecture understanding may fragment again

### Current Overall Risk Reality

The largest current risk is not trading logic itself.

The largest risk is:
- architecture complexity growth
combined with:
- evolving project direction
and:
- fragmented operational memory

### Mitigation Direction

Current mitigation approach includes:
- structured documentation
- runtime cognition mapping
- project inventory systems
- reality-based architecture tracking
- gradual stabilization before major restructuring

## Future Runtime Refactor Direction