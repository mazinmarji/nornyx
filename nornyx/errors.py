from dataclasses import dataclass


@dataclass
class Diagnostic:
    level: str
    code: str
    message: str
    path: str | None = None
    hint: str | None = None

    def to_dict(self) -> dict:
        data = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.path:
            data["path"] = self.path
        if self.hint:
            data["hint"] = self.hint
        return data
