import boto3 # type: ignore
from typing import List, Tuple

def get_cost_data(ce, start: str, end: str, group_by_service: bool = False) -> dict:
    args = {
        "TimePeriod": {"Start": start, "End": end},
        "Granularity": "MONTHLY",
        "Metrics": ["BlendedCost"]
    }
    if group_by_service:
        args["GroupBy"] = [{"Type": "DIMENSION", "Key": "SERVICE"}]

    return ce.get_cost_and_usage(**args)

def extract_total_amount(data: dict) -> float:
    return float(data["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"])

def extract_service_breakdown(data: dict, top_n: int = 5) -> List[Tuple[str, float]]:
    groups = data["ResultsByTime"][0]["Groups"]
    return sorted(
        [
            (group["Keys"][0], float(group["Metrics"]["BlendedCost"]["Amount"]))
            for group in groups
        ],
        key=lambda x: x[1], reverse=True
    )[:top_n]
