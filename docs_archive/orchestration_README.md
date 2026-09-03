# Orchestration Layer

Purpose:
Coordinate runtime lifecycle and system operations for MJONAI.

The orchestration layer is responsible for:
- startup sequencing
- scheduler wiring
- runtime monitoring
- process lifecycle handling
- health telemetry
- graceful shutdown coordination

The orchestration layer is NOT responsible for:
- strategy logic
- signal generation
- market analysis
- portfolio analytics
- AI reasoning
- research calculations
- execution decision logic

Design philosophy:
- orchestration should remain thin
- business logic belongs in domain modules
- extractions should be incremental and validated
- avoid aggressive refactors
- avoid circular dependencies

Current orchestration modules:
- startup.py
- health_monitor.py
- runtime_guard.py
- scheduler_setup.py