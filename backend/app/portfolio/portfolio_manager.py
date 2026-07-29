from datetime import datetime

from app.portfolio.bankroll import bankroll

from app.portfolio.exposure import exposure_manager

from app.portfolio.models import Position

from app.positions.position_repository import position_repository


class PortfolioManager:

    def process(self, opportunities):

        approved = []

        for opportunity in opportunities:

            stake = opportunity["stake"]["total"]

            if not exposure_manager.validate(opportunity):

                continue

            if not bankroll.allocate(stake):

                continue

            position = Position(

                id=position_repository.count() + 1,

                market=opportunity["question"],

                platform_yes=opportunity["buy_yes_platform"],

                platform_no=opportunity["buy_no_platform"],

                stake=stake,

                expected_profit=opportunity["profit"],

                roi=opportunity["roi"],

                opened_at=datetime.now()

            )

            position_repository.add(position)

            opportunity["position_id"] = position.id

            opportunity["portfolio"] = {

                "approved": True,

                "bankroll": bankroll.available,

                "locked": bankroll.locked,

                "utilization": bankroll.utilization

            }

            approved.append(opportunity)

        return approved


portfolio_manager = PortfolioManager()