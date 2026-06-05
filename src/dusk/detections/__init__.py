"""Behavioral detections. Each detection inspects packets for one attack pattern."""

from dusk.detections.base import Detection, DetectionResult
from dusk.detections.sweep import SweepDetection

__all__ = ["Detection", "DetectionResult", "SweepDetection"]
