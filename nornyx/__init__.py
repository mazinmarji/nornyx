"""Nornyx stable generalized agentic contract language."""

__version__ = "1.5.1"

from .governed_package import (
    GovernedPackage,
    GovernedPackageGenerator,
    GovernedPackageValidator,
    generate_governed_package,
    validate_governed_package,
)
from .package_scanner import scan_package

__all__ = [
    "GovernedPackage",
    "GovernedPackageGenerator",
    "GovernedPackageValidator",
    "__version__",
    "generate_governed_package",
    "scan_package",
    "validate_governed_package",
]
