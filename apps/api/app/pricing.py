import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Price:
    provider: str
    model: str
    version: str
    input_per_million_tokens: float
    output_per_million_tokens: float


def _pricing_dir() -> Path:
    return Path(__file__).resolve().parent / "pricing_data"


def find_price(provider: str, model: str) -> Price | None:
    data_dir = _pricing_dir()
    if not data_dir.exists():
        return None
    matches: list[Price] = []
    for path in data_dir.glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("provider") == provider and data.get("model") == model:
            matches.append(
                Price(
                    provider=provider,
                    model=model,
                    version=f"{data.get('effective_from')}:{path.name}",
                    input_per_million_tokens=float(data["input_per_million_tokens"]),
                    output_per_million_tokens=float(data["output_per_million_tokens"]),
                )
            )
    return sorted(matches, key=lambda p: p.version)[-1] if matches else None


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> tuple[float | None, str | None]:
    price = find_price(provider, model)
    if price is None:
        return None, None
    cost = (input_tokens / 1_000_000 * price.input_per_million_tokens) + (
        output_tokens / 1_000_000 * price.output_per_million_tokens
    )
    return round(cost, 6), price.version
