from dusk.models import AttioStatus, DuskDecision, RiskLevel

_DEFAULTS = {"subject": "Anthropic", "score": 75, "confidence": 0.9, "reasoning": "ok"}


def make_decision(**kwargs) -> DuskDecision:
    return DuskDecision(**{**_DEFAULTS, **kwargs})


def test_risk_level_high():
    assert make_decision(score=70).risk_level == RiskLevel.HIGH
    assert make_decision(score=100).risk_level == RiskLevel.HIGH


def test_risk_level_medium():
    assert make_decision(score=40).risk_level == RiskLevel.MEDIUM
    assert make_decision(score=69).risk_level == RiskLevel.MEDIUM


def test_risk_level_low():
    assert make_decision(score=0).risk_level == RiskLevel.LOW
    assert make_decision(score=39).risk_level == RiskLevel.LOW


def test_to_dict_has_required_keys():
    d = make_decision()
    result = d.to_dict()
    required = (
        "id",
        "subject",
        "score",
        "confidence",
        "reasoning",
        "risk_level",
        "output",
        "trace",
    )
    for key in required:
        assert key in result


def test_to_dict_output_shape():
    d = make_decision(score=80, confidence=0.85)
    output = d.to_dict()["output"]
    assert isinstance(output, dict)
    assert output["score"] == 80
    assert output["confidence"] == 0.85


def test_to_dict_trace_shape():
    d = make_decision(score=30)
    trace = d.to_dict()["trace"]
    assert isinstance(trace, dict)
    assert trace["risk_level"] == "low"
    assert trace["status"] == AttioStatus.NOT_PUSHED.value


def test_from_dict_round_trip():
    original = make_decision(score=65, risk_flags=["competitive_market"])
    restored = DuskDecision.from_dict(original.to_dict())
    assert restored.subject == original.subject
    assert restored.score == original.score
    assert restored.risk_flags == original.risk_flags
    assert restored.id == original.id


def test_from_dict_ignores_bad_attio_status():
    data: dict[str, object] = {
        "subject": "X",
        "score": 50,
        "confidence": 0.5,
        "reasoning": "ok",
        "attio_status": "bad",
    }
    d = DuskDecision.from_dict(data)
    assert d.attio_status == AttioStatus.NOT_PUSHED
