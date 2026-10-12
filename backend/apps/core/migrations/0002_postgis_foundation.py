from django.db import migrations


POSTGIS_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE accounts_user
    ADD COLUMN IF NOT EXISTS location geography(Point, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN longitude IS NULL OR latitude IS NULL THEN NULL
            ELSE ST_SetSRID(
                ST_MakePoint(longitude::double precision, latitude::double precision),
                4326
            )::geography
        END
    ) STORED;

CREATE INDEX IF NOT EXISTS accounts_user_location_gix
    ON accounts_user USING GIST (location);

ALTER TABLE neighborhoods_neighborhood
    ADD COLUMN IF NOT EXISTS boundary geometry(MultiPolygon, 4326);

ALTER TABLE neighborhoods_neighborhood
    ADD COLUMN IF NOT EXISTS centroid geography(Point, 4326)
    GENERATED ALWAYS AS (
        CASE
            WHEN centroid_longitude IS NULL OR centroid_latitude IS NULL THEN NULL
            ELSE ST_SetSRID(
                ST_MakePoint(
                    centroid_longitude::double precision,
                    centroid_latitude::double precision
                ),
                4326
            )::geography
        END
    ) STORED;

CREATE INDEX IF NOT EXISTS neighborhoods_boundary_gix
    ON neighborhoods_neighborhood USING GIST (boundary);

CREATE INDEX IF NOT EXISTS neighborhoods_centroid_gix
    ON neighborhoods_neighborhood USING GIST (centroid);

ALTER TABLE incidents_incident
    ADD COLUMN IF NOT EXISTS location geography(Point, 4326)
    GENERATED ALWAYS AS (
        ST_SetSRID(
            ST_MakePoint(longitude::double precision, latitude::double precision),
            4326
        )::geography
    ) STORED;

CREATE INDEX IF NOT EXISTS incidents_location_gix
    ON incidents_incident USING GIST (location);

ALTER TABLE sos_sosalert
    ADD COLUMN IF NOT EXISTS current_location geography(Point, 4326)
    GENERATED ALWAYS AS (
        ST_SetSRID(
            ST_MakePoint(
                current_longitude::double precision,
                current_latitude::double precision
            ),
            4326
        )::geography
    ) STORED;

CREATE INDEX IF NOT EXISTS sos_alert_current_location_gix
    ON sos_sosalert USING GIST (current_location);
"""

REVERSE_SQL = """
DROP INDEX IF EXISTS sos_alert_current_location_gix;
DROP INDEX IF EXISTS incidents_location_gix;
DROP INDEX IF EXISTS neighborhoods_centroid_gix;
DROP INDEX IF EXISTS neighborhoods_boundary_gix;
DROP INDEX IF EXISTS accounts_user_location_gix;

ALTER TABLE sos_sosalert DROP COLUMN IF EXISTS current_location;
ALTER TABLE incidents_incident DROP COLUMN IF EXISTS location;
ALTER TABLE neighborhoods_neighborhood DROP COLUMN IF EXISTS centroid;
ALTER TABLE neighborhoods_neighborhood DROP COLUMN IF EXISTS boundary;
ALTER TABLE accounts_user DROP COLUMN IF EXISTS location;
"""


def install_postgis_foundation(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(POSTGIS_SQL)


def remove_postgis_foundation(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("accounts", "0001_initial"),
        ("neighborhoods", "0001_initial"),
        ("incidents", "0001_initial"),
        ("sos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            install_postgis_foundation,
            reverse_code=remove_postgis_foundation,
        )
    ]

