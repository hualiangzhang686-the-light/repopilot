"""Tool definitions and dispatch registry.

Keep package import side-effect free so model types and tool types can refer to
each other through their concrete modules without an initialization cycle.
"""
