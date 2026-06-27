"""Behavioral detections. Each detection inspects packets for one attack pattern."""

from dusk.detections.base import Detection, DetectionResult
from dusk.detections.boundary import BoundaryDetection
from dusk.detections.sweep import SweepDetection

__all__ = [
    "BoundaryDetection",
    "Detection",
    "DetectionResult",
    "SweepDetection",
]
