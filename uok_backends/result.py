class ActivationResult:
    def __init__(self, ok, message="", details="", applied_keyd=False, rolled_back=False):
        self.ok = ok
        self.message = message
        self.details = details
        self.applied_keyd = applied_keyd
        self.rolled_back = rolled_back

    def __bool__(self):
        return self.ok

    @classmethod
    def ok_result(cls, message="", applied_keyd=False):
        return cls(True, message=message, applied_keyd=applied_keyd)

    @classmethod
    def fail(cls, message, details="", rolled_back=False):
        return cls(False, message=message, details=details, rolled_back=rolled_back)
