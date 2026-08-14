from director_demo.schemas import ShotPlan


def test_shot_numbers_must_be_sequential() -> None:
    payload = {
        "title": "Test",
        "logline": "A test.",
        "characters": [],
        "locations": [],
        "global_style": [],
        "shots": [],
    }
    assert ShotPlan.model_validate(payload).shots == []
