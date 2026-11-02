"""稳定的工具错误类别，不依赖错误文本决定调用方分支。"""


class ToolError(Exception):
    pass


class ConfigError(ToolError, ValueError):
    pass


class InputError(ToolError, ValueError):
    def __init__(self, message, *, line=None):
        super().__init__(message)
        self.line = line


class ReportError(ToolError, OSError):
    pass


class Cancelled(ToolError):
    pass
