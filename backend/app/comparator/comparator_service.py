from app.market.comparators.cross_platform import (
    cross_platform_comparator,
)


class ComparatorService:

    """
    Serviço central responsável por comparar mercados.
    """

    def compare(self, markets):

        return cross_platform_comparator.compare(markets)


comparator_service = ComparatorService()