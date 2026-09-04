"""PlantNexus CNC showcase, isolated under the repository-local demo tree."""

from .assets import BenchmarkProfile, DemoAssets, load_demo_assets
from .composition import create_demo_app, create_demo_runtime
from .generator import DemoGeneratedBatch, DemoPackageGenerator
from .ingress import DemoIngressArtifacts, DemoIngressPipeline
from .replanning import UrgentReplanOrchestrator, UrgentReplanResult
from .presentation import (
    ComparisonPresentationQuery,
    DemoComparisonView,
    DemoFactoryView,
    DemoPresentationService,
    DemoScheduleView,
    SchedulePresentationQuery,
)
from .urgent import UrgentOrderCommand

__all__ = [
    "BenchmarkProfile",
    "DemoAssets",
    "DemoGeneratedBatch",
    "DemoIngressArtifacts",
    "DemoIngressPipeline",
    "DemoPackageGenerator",
    "DemoComparisonView",
    "DemoFactoryView",
    "DemoPresentationService",
    "DemoScheduleView",
    "ComparisonPresentationQuery",
    "SchedulePresentationQuery",
    "UrgentOrderCommand",
    "UrgentReplanOrchestrator",
    "UrgentReplanResult",
    "create_demo_app",
    "create_demo_runtime",
    "load_demo_assets",
]
