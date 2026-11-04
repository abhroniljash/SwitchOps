"""
Switch ROI & Telemetry: Implements SandboxAQ Switch ROI observability principles,
tracking token usage, latency, MTTR reduction, and dollar engineering value saved.
"""

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ROIMetrics:
    incident_id: str
    baseline_manual_mttr_minutes: float = 45.0
    actual_resolution_seconds: float = 78.0
    hourly_engineer_rate: float = 150.0  # $150/hr for senior SRE
    downtime_cost_per_minute: float = 250.0  # Average e-commerce checkout downtime cost
    tokens_consumed: int = 2480
    llm_cost_usd: float = 0.006

    @property
    def mttr_reduction_percent(self) -> float:
        actual_minutes = self.actual_resolution_seconds / 60.0
        return round(((self.baseline_manual_mttr_minutes - actual_minutes) / self.baseline_manual_mttr_minutes) * 100, 1)

    @property
    def engineer_time_saved_dollars(self) -> float:
        hours_saved = (self.baseline_manual_mttr_minutes - (self.actual_resolution_seconds / 60.0)) / 60.0
        return round(hours_saved * self.hourly_engineer_rate, 2)

    @property
    def downtime_revenue_saved_dollars(self) -> float:
        minutes_saved = self.baseline_manual_mttr_minutes - (self.actual_resolution_seconds / 60.0)
        return round(minutes_saved * self.downtime_cost_per_minute, 2)

    @property
    def total_value_delivered_usd(self) -> float:
        return round(self.engineer_time_saved_dollars + self.downtime_revenue_saved_dollars, 2)

    @property
    def roi_multiplier(self) -> float:
        if self.llm_cost_usd <= 0:
            return 1000.0
        return round(self.total_value_delivered_usd / self.llm_cost_usd, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "baseline_manual_mttr_minutes": self.baseline_manual_mttr_minutes,
            "actual_resolution_seconds": self.actual_resolution_seconds,
            "mttr_reduction_percent": self.mttr_reduction_percent,
            "engineer_time_saved_dollars": self.engineer_time_saved_dollars,
            "downtime_revenue_saved_dollars": self.downtime_revenue_saved_dollars,
            "total_value_delivered_usd": self.total_value_delivered_usd,
            "tokens_consumed": self.tokens_consumed,
            "llm_cost_usd": self.llm_cost_usd,
            "roi_multiplier": self.roi_multiplier,
        }


class ROITelemetryTracker:
    """Tracks cumulative ROI metrics for Switch-enabled workflows."""

    def __init__(self):
        self.records: List[ROIMetrics] = []

    def record_incident_resolution(
        self,
        incident_id: str,
        duration_seconds: float,
        tokens_consumed: int = 2480
    ) -> ROIMetrics:
        # LLM pricing approximation (~$0.0025 per 1k tokens blended)
        llm_cost = round((tokens_consumed / 1000.0) * 0.0025, 4)
        metric = ROIMetrics(
            incident_id=incident_id,
            actual_resolution_seconds=round(duration_seconds, 1),
            tokens_consumed=tokens_consumed,
            llm_cost_usd=llm_cost
        )
        self.records.append(metric)
        return metric

    def get_aggregate_summary(self) -> Dict[str, Any]:
        total_incidents = len(self.records)
        if total_incidents == 0:
            return {
                "total_incidents_resolved": 0,
                "total_dollars_saved": 0.0,
                "average_mttr_reduction": "0%",
                "average_resolution_time": "0s",
            }

        total_saved = sum(r.total_value_delivered_usd for r in self.records)
        avg_reduction = sum(r.mttr_reduction_percent for r in self.records) / total_incidents
        avg_res_time = sum(r.actual_resolution_seconds for r in self.records) / total_incidents

        return {
            "total_incidents_resolved": total_incidents,
            "total_dollars_saved": round(total_saved, 2),
            "average_mttr_reduction": f"{round(avg_reduction, 1)}%",
            "average_resolution_time": f"{round(avg_res_time, 1)}s",
        }
