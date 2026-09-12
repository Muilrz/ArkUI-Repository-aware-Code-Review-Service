"""Platform-neutral foundations for the Code Review Service.

The package is organized as inward-pointing layers:

``domain <- ports <- application`` and ``domain/ports <- adapters``.

Concrete GitCode, knowledge-provider, review-engine, MCP, and scheduler behavior
belongs to later milestones and is intentionally absent from R0-A.
"""
