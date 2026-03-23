from __future__ import annotations
from pydantic import BaseModel
import copy


class ParameterSet(BaseModel, frozen=True):
    """Defines a single parameter variation for batch simulation."""
    name: str = "default"
    rng_seed: int = 42
    max_turns: int = 72
    use_llm: bool = False  # False = RuleBasedFallback mode

    # Commander personality overrides: {commander_id: {trait: value}}
    personality_overrides: dict[str, dict[str, float]] = {}

    # Unit strength multipliers: {unit_id: multiplier}
    strength_multipliers: dict[str, float] = {}

    # Unit position overrides: {unit_id: {"q": int, "r": int}}
    position_overrides: dict[str, dict[str, int]] = {}

    # Strategy hint for LLM prompt (only used if use_llm=True)
    strategy_prompt_suffix: str = ""


def apply_to_scenario(scenario_data: dict, params: ParameterSet) -> dict:
    """Apply parameter overrides to a copy of scenario data. Original is not modified."""
    data = copy.deepcopy(scenario_data)

    # Apply strength multipliers
    for side_data in data.get("forces", {}).values():
        for unit in side_data.get("units", []):
            uid = unit["id"]
            if uid in params.strength_multipliers:
                unit["strength"] = min(1.0, unit.get("strength", 1.0) * params.strength_multipliers[uid])

    # Apply position overrides
    for side_data in data.get("forces", {}).values():
        for unit in side_data.get("units", []):
            uid = unit["id"]
            if uid in params.position_overrides:
                unit["position"] = params.position_overrides[uid]

    # Apply personality overrides to commanders
    for side_data in data.get("forces", {}).values():
        for cmd in side_data.get("commanders", []):
            cid = cmd["id"]
            if cid in params.personality_overrides:
                traits = cmd.get("personality_traits", {})
                traits.update(params.personality_overrides[cid])
                cmd["personality_traits"] = traits

    return data


def generate_parameter_grid(
    base: ParameterSet,
    variations: dict[str, list],
) -> list[ParameterSet]:
    """Generate parameter sets from a grid of variations.

    Example:
        generate_parameter_grid(
            base=ParameterSet(name="base"),
            variations={
                "rng_seed": [1, 2, 3],
                "strength_multipliers": [{"B1": 0.8}, {"B1": 1.2}],
            }
        )
    Returns list of ParameterSets, one per combination.
    """
    from itertools import product

    keys = list(variations.keys())
    if not keys:
        return [base]

    value_lists = [variations[k] for k in keys]
    param_sets = []

    for i, combo in enumerate(product(*value_lists)):
        overrides = {}
        for k, v in zip(keys, combo):
            overrides[k] = v
        ps = base.model_copy(update={
            "name": f"{base.name}_var{i}",
            **overrides,
        })
        param_sets.append(ps)

    return param_sets
