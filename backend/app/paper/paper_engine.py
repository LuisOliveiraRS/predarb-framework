from app.paper.paper_order_executor import paper_order_executor
from app.paper.paper_statistics import paper_statistics
from app.paper.paper_trade_history import paper_trade_history
from app.exchanges.exchange_manager import exchange_manager


class PaperEngine:
    """
    Executa todas as ordens em ambiente simulado.
    """

    def execute(self, opportunities):

        for opportunity in opportunities:

            for order in opportunity.get("orders", []):

                exchange_manager.execute(order)

        return paper_statistics.report(
            paper_trade_history.all()
        )


paper_engine = PaperEngine()