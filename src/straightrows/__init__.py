"""Straight Rows detection pipeline.

Stages (one module each):
  io          load raw files, timezone-aware UTC
  features    per-tractor, per-minute features + SDA context
  candidates  cause-agnostic anomaly flags per tractor-minute
  attribution map flags + context to zero or more causes per tractor-minute
  assembly    turn per-minute causes into detection intervals
  evidence    measurement-based evidence strings for each detection
  export      submission.json
Parameters and their rationale live in config.py.
"""
