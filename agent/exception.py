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


class Wan2_1_T2IError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class SDXL_MV_AdapterError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
