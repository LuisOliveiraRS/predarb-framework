from app.pipeline.pipeline_stage import PipelineStage
from app.market.comparator_service import comparator_service


class CompareStage(PipelineStage):

    def process(self, context):

        context.opportunities = comparator_service.compare(
            context.markets
        )

        return context