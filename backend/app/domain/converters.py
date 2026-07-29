from app.domain.opportunity import Opportunity


class OpportunityConverter:

    def from_dict(self, data):

        return Opportunity(

            question=data["question"],

            buy_yes_platform=data["buy_yes_platform"],

            buy_no_platform=data["buy_no_platform"],

            yes_price=data["yes_price"],

            no_price=data["no_price"],

            cost=data["cost"],

            edge=data["edge"],

            roi=data["roi"],

            profit=data["profit"],

            spread=data["spread"],

            confidence=data["confidence"]

        )

    def to_dict(self, opportunity):

        return opportunity.__dict__


opportunity_converter = OpportunityConverter()