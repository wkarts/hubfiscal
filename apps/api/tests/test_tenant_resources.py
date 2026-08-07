from hubfiscal.core.resources import ALL_RESOURCES, DEFAULT_ACCESS_PROFILES, TENANT_RESOURCE_PRESETS, preset_resources
from hubfiscal.worker import celery_app


def test_complete_preset_enables_all_resources() -> None:
    assert preset_resources("complete") == ALL_RESOURCES
    assert set(TENANT_RESOURCE_PRESETS["fiscal_core"]["resources"]) < set(ALL_RESOURCES)
    assert preset_resources("unknown-preset") == ALL_RESOURCES


def test_default_profiles_have_expected_access() -> None:
    profiles = {profile["key"]: profile for profile in DEFAULT_ACCESS_PROFILES}
    assert profiles["tenant_owner"]["permissions"] == ["*"]
    assert profiles["tenant_owner"]["enabled_resources"] == ALL_RESOURCES
    assert "companies" in profiles["fiscal_manager"]["enabled_resources"]
    assert "users" not in profiles["auditor"]["enabled_resources"]


def test_celery_does_not_require_remote_control_queues() -> None:
    assert celery_app.conf.worker_enable_remote_control is False
    assert celery_app.conf.broker_connection_retry_on_startup is True
    assert celery_app.conf.worker_cancel_long_running_tasks_on_connection_loss is True
