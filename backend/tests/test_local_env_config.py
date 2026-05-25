from app.core.config import Settings


def test_settings_loads_local_env_override_file() -> None:
    assert Settings.model_config["env_file"] == ("../.env", "../.env.local")
