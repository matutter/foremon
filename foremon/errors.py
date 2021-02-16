
class ForemonError(Exception):

    def __init__(self, message, code=1):
        super().__init__(message, code)

    @property
    def message(self) -> str:
        return self.args[0]

    @property
    def code(self) -> int:
        return self.args[1]
