from app.execution.execution_engine import ExecutionEngine
from app.pipeline.pipeline_builder import PipelineBuilder


def test_live_execution_is_disabled_by_default():
    called = []

    def executor(order):
        called.append(order)
        return {"accepted": True}

    engine = ExecutionEngine(executor=executor)
    report = engine.execute({"id": "order-1"})

    assert report["status"] == "DISABLED"
    assert report["executed"] is False
    assert called == []


def test_live_pipeline_execution_stage_is_disabled_by_default():
    pipeline = PipelineBuilder().build_live()
    execution_stage = next(
        stage
        for stage in pipeline.stages
        if stage.__class__.__name__ == "ExecutionStage"
    )

    assert execution_stage.enabled is False
