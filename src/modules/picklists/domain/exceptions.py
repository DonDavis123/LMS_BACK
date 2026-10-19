class PicklistOptionInUseError(ValueError):
    """The option is still used by records, so it cannot simply be deleted.

    Subclasses ``ValueError`` so callers that only know the generic
    "ValueError -> HTTP 400" convention keep working; the view catches this
    one first to answer 409 with the usage count.
    """

    def __init__(self, message: str, usage_count: int):
        super().__init__(message)
        self.usage_count = usage_count
