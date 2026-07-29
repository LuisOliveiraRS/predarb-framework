import asyncio

from app.realtime.connection_manager import connection_manager
from app.realtime.messages import RealtimeMessage


class Publisher:
    """
    Responsável por publicar mensagens
    para todos os clientes conectados
    via WebSocket.
    """

    def _dispatch(self, coroutine):
        """
        Executa uma coroutine tanto em um loop já ativo
        quanto cria um novo loop quando necessário.
        """

        try:

            loop = asyncio.get_running_loop()

            loop.create_task(coroutine)

        except RuntimeError:

            asyncio.run(coroutine)

    # ======================================================
    # Opportunities
    # ======================================================

    def publish_opportunity(self, opportunity):

        self._dispatch(

            connection_manager.broadcast(

                RealtimeMessage.opportunity(

                    opportunity

                )

            )

        )

    # ======================================================
    # Markets
    # ======================================================

    def publish_market(self, market):

        self._dispatch(

            connection_manager.broadcast(

                RealtimeMessage.market(

                    market

                )

            )

        )

    # ======================================================
    # Orders
    # ======================================================

    def publish_order(self, order):

        self._dispatch(

            connection_manager.broadcast(

                RealtimeMessage.order(

                    order

                )

            )

        )

    # ======================================================
    # Positions
    # ======================================================

    def publish_position(self, position):

        self._dispatch(

            connection_manager.broadcast(

                RealtimeMessage.position(

                    position

                )

            )

        )

    # ======================================================
    # Portfolio
    # ======================================================

    def publish_portfolio(self, portfolio):

        self._dispatch(

            connection_manager.broadcast(

                RealtimeMessage.portfolio(

                    portfolio

                )

            )

        )


publisher = Publisher()