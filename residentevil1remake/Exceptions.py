from Options import OptionError

class RE1ROptionError(OptionError):
    def __init__(self, msg):
        msg = f"There was a problem with your RE1R YAML options. {msg}"

        super().__init__(msg)

