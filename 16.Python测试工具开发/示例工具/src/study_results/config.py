"""配置是值；不在模块导入时读取环境或文件。"""

from dataclasses import dataclass

from .errors import ConfigError
from .models import STATUSES


@dataclass(frozen=True)
class Config:
    statuses: tuple[str, ...] = STATUSES
    max_records: int = 1000

    def __post_init__(self):
        if type(self.max_records) is not int or not 1 <= self.max_records <= 10000:
            raise ConfigError("max_records must be an integer within 1..10000")
        if type(self.statuses) is not tuple or any(type(value) is not str for value in self.statuses):
            raise ConfigError("statuses must be a tuple of status names")
        if len(set(self.statuses)) != len(self.statuses) or any(value not in STATUSES for value in self.statuses):
            raise ConfigError("statuses contains duplicates or unknown names")


def resolve_config(file_values=None, environ=None, overrides=None):
    values = {"statuses": STATUSES, "max_records": 1000}

    def merge(layer, *, skip_none=False):
        if type(layer) is not dict or not layer.keys() <= values.keys():
            raise ConfigError("configuration contains unknown fields or is not an object")
        for key, value in layer.items():
            if skip_none and value is None:
                continue
            if key == "statuses":
                if type(value) is not list or any(type(item) is not str for item in value):
                    raise ConfigError("statuses must be an array of names")
                candidate = tuple(value)
                Config(statuses=candidate)
                values[key] = tuple(name for name in STATUSES if name in candidate)
            else:
                Config(max_records=value)
                values[key] = value

    merge({} if file_values is None else file_values)
    environment = {} if environ is None else environ
    if "STUDY_RESULTS_MAX_RECORDS" in environment:
        text = environment["STUDY_RESULTS_MAX_RECORDS"]
        if type(text) is not str:
            raise ConfigError("STUDY_RESULTS_MAX_RECORDS must be integer text")
        try:
            maximum = int(text, 10)
        except ValueError as error:
            raise ConfigError("STUDY_RESULTS_MAX_RECORDS must be integer text") from error
        merge({"max_records": maximum})
    merge({} if overrides is None else overrides, skip_none=True)
    return Config(**values)
