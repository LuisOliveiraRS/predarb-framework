from app.ai import AIEngine, DatasetBuilder


def test_dataset_train_activate_remains_advisory():
    rows = []
    for index in range(12):
        successful = bool(index % 2)
        rows.append(
            {
                "roi": 18 if successful else 4,
                "profit": 0.16 if successful else 0.03,
                "spread": 0.01,
                "edge": 0.15 if successful else 0.03,
                "confidence": 0.95 if successful else 0.55,
                "match_score": 0.96,
                "risk": {"score": 20 if successful else 70},
                "liquidity": {"available": 4_000},
                "slippage": {"rate": 0.007},
                "success": successful,
            }
        )

    dataframe = DatasetBuilder().build(rows, drop_unlabeled=True)
    engine = AIEngine()
    training = engine.train(
        dataframe,
        test_size=0.25,
        activate=True,
        persist_metadata=False,
    )

    assert training.status == "TRAINED"
    assert engine.predictor.model_version == training.version
    assert engine.status(include_trainer=False)["execution_authorized"] is False
