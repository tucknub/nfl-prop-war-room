from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fantasy.cloudflare_config import (
    DATABASE_ID_PLACEHOLDER,
    EXPECTED_COMPATIBILITY_DATE,
    EXPECTED_D1_BINDING,
    EXPECTED_D1_DATABASE_NAME,
    EXPECTED_MAIN,
    EXPECTED_MIGRATIONS_DIR,
    EXPECTED_SECRET_NAME,
    EXPECTED_WORKER_NAME,
    UnsafeFantasyCloudflareConfig,
    canonical_d1_database_id,
    render_fantasy_hq_wrangler,
    write_rendered_wrangler,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = REPO_ROOT / "workers" / "fantasy-hq" / "wrangler.template.jsonc"
TEST_DATABASE_ID = "11111111-2222-4333-8444-555555555555"


def test_template_contains_only_one_resource_placeholder_and_no_secret_value() -> None:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    config = json.loads(text)

    assert text.count(DATABASE_ID_PLACEHOLDER) == 1
    assert config["name"] == EXPECTED_WORKER_NAME
    assert config["main"] == EXPECTED_MAIN
    assert config["compatibility_date"] == EXPECTED_COMPATIBILITY_DATE
    assert config["workers_dev"] is True
    assert config["secrets"] == {"required": [EXPECTED_SECRET_NAME]}
    assert EXPECTED_SECRET_NAME not in config.get("vars", {})
    assert config["d1_databases"] == [
        {
            "binding": EXPECTED_D1_BINDING,
            "database_name": EXPECTED_D1_DATABASE_NAME,
            "database_id": DATABASE_ID_PLACEHOLDER,
            "migrations_dir": EXPECTED_MIGRATIONS_DIR,
        }
    ]


def test_renderer_substitutes_canonical_uuid_and_preserves_invariants() -> None:
    rendered = render_fantasy_hq_wrangler(
        TEMPLATE_PATH.read_text(encoding="utf-8"),
        TEST_DATABASE_ID.upper(),
    )
    config = json.loads(rendered)

    assert DATABASE_ID_PLACEHOLDER not in rendered
    assert config["d1_databases"][0]["database_id"] == TEST_DATABASE_ID
    assert config["secrets"] == {"required": [EXPECTED_SECRET_NAME]}
    assert EXPECTED_SECRET_NAME not in config.get("vars", {})


def test_renderer_refuses_missing_duplicate_or_nil_placeholder() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    with pytest.raises(UnsafeFantasyCloudflareConfig):
        render_fantasy_hq_wrangler(template.replace(DATABASE_ID_PLACEHOLDER, "x"), TEST_DATABASE_ID)
    with pytest.raises(UnsafeFantasyCloudflareConfig):
        render_fantasy_hq_wrangler(template + DATABASE_ID_PLACEHOLDER, TEST_DATABASE_ID)
    with pytest.raises(UnsafeFantasyCloudflareConfig):
        render_fantasy_hq_wrangler(template, "00000000-0000-0000-0000-000000000000")


def test_database_id_validation_rejects_non_uuid_and_whitespace() -> None:
    for value in ["", "not-a-uuid", f" {TEST_DATABASE_ID}", f"{TEST_DATABASE_ID} "]:
        with pytest.raises(UnsafeFantasyCloudflareConfig):
            canonical_d1_database_id(value)


def test_renderer_rejects_drift_in_secret_binding_or_worker_contract() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    mutations = [
        template.replace('"propwar-fantasy-hq"', '"wrong-worker"', 1),
        template.replace('"./index.mjs"', '"./wrong.mjs"'),
        template.replace('"FANTASY_DB"', '"DB"'),
        template.replace('"FANTASY_PERSISTENCE_TOKEN"', '"OTHER_SECRET"'),
        template.replace('"../../migrations"', '"./migrations"'),
    ]
    for mutated in mutations:
        with pytest.raises(UnsafeFantasyCloudflareConfig):
            render_fantasy_hq_wrangler(mutated, TEST_DATABASE_ID)


def test_atomic_writer_creates_generated_config_without_secret_material(tmp_path: Path) -> None:
    output = tmp_path / "wrangler.generated.jsonc"
    result = write_rendered_wrangler(
        template_path=TEMPLATE_PATH,
        output_path=output,
        database_id=TEST_DATABASE_ID,
    )

    assert result == output
    config = json.loads(output.read_text(encoding="utf-8"))
    assert config["d1_databases"][0]["database_id"] == TEST_DATABASE_ID
    assert config["secrets"] == {"required": [EXPECTED_SECRET_NAME]}
    assert not list(tmp_path.glob("*.tmp"))


def test_migrations_directory_resolves_to_repository_migrations_folder() -> None:
    resolved = (TEMPLATE_PATH.parent / EXPECTED_MIGRATIONS_DIR).resolve()
    assert resolved == (REPO_ROOT / "migrations").resolve()
    assert (resolved / "0001_fantasy_hq_persistence.sql").is_file()
