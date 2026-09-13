"""Platform-neutral foundations for the Code Review Service.

The package is organized as inward-pointing layers:

``domain <- ports <- application`` and ``domain/ports <- adapters``.

R0 provides contracts only. Concrete GitCode, knowledge-provider, review-engine,
telemetry, MCP, and scheduler behavior belongs to later milestones.
"""
