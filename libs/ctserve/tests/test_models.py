from ctserve.models import models_from_env


def test_models_from_env_reads_url_and_version():
    env = {
        "CT_MODEL_CATEGORIZER_URL": "http://c/v1/models/categorizer:predict",
        "CT_MODEL_CATEGORIZER_VERSION": "3",
        "CT_MODEL_ETA_URL": "http://e/v1/models/eta:predict",
        "OTHER": "x",
    }
    m = models_from_env(env)
    assert set(m) == {"categorizer", "eta"}
    assert m["categorizer"].version == "3" and m["eta"].version == "0"
    assert m["eta"].url.endswith("eta:predict")
