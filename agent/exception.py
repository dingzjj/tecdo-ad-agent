class ComfyUIError(Exception):
    pass


class CreateVideoError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class QwenT2IError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
