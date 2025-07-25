class AIError(Exception):
    """
    AI错误
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class HumanError(Exception):
    """
    用户错误
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
