"""MJONAI kernel — the single import namespace for the trading system.

ADR-0008: kernel packages (core, data, strategy, risk, execution, db, agents,
options, intelligence, communication, analytics, research, storage, configs)
import ONLY each other. Apps, tools and infra live outside this package.
"""
