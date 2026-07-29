class Notifier:

    def notify(self, opportunity):

        print()

        print("=" * 60)

        print("NOVA OPORTUNIDADE")

        print(opportunity["question"])

        print("ROI:", opportunity["roi"])

        print("Profit:", opportunity["profit"])

        print("=" * 60)


notifier = Notifier()