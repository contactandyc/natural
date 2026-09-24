# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
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


def serialize_to_yaml(module: BaseModel) -> str:
    """Serializes the Natural IR module into a clean, audited YAML string."""
    # mode="json" converts Enums to raw strings ("PARAMETER") and decimals to primitives
    data = module.model_dump(mode="json", exclude_none=True)
    return yaml.dump(
        data,
        Dumper=CleanDumper,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
