class ExposureManager:

    def __init__(self):

        self.max_total = 0.50

        self.max_single = 0.05

    def validate(self, opportunity):

        total = opportunity["stake"]["total"]

        if total > 500:

            return False

        return True


exposure_manager = ExposureManager()