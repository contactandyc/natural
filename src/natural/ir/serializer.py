# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from enum import Enum
import yaml
from pydantic import BaseModel


class CleanDumper(yaml.SafeDumper):
    pass


def represent_none(dumper: yaml.SafeDumper, _):
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


def represent_enum(dumper: yaml.SafeDumper, data: Enum):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data.value))


CleanDumper.add_representer(type(None), represent_none)
CleanDumper.add_multi_representer(Enum, represent_enum)


def _prune_empty(val):
    """Recursively removes None, empty lists, and empty dicts for clean YAML emission."""
    if isinstance(val, dict):
        cleaned = {k: _prune_empty(v) for k, v in val.items()}
        return {k: v for k, v in cleaned.items() if v is not None and v != [] and v != {}}
    elif isinstance(val, list):
        cleaned = [_prune_empty(v) for v in val]
        return [v for v in cleaned if v is not None and v != [] and v != {}]
    return val


def serialize_to_yaml(module: BaseModel) -> str:
    """Serializes the Natural IR module into a clean, audited YAML string."""
    data = module.model_dump(mode="json", exclude_none=True)
    pruned_data = _prune_empty(data)
    return yaml.dump(
        pruned_data,
        Dumper=CleanDumper,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
