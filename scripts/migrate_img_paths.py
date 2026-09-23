"""Migra img_foto / img_escudo de TEXT (base64) a VARCHAR(255) (ruta)."""
from sqlalchemy import create_engine, text

from app.config import settings

stmts = [
    """
    UPDATE jugador SET img_foto = NULL
    WHERE img_foto IS NOT NULL
      AND (img_foto LIKE 'data:%' OR char_length(img_foto) > 255)
    """,
    """
    UPDATE datos_equipo SET img_escudo = NULL
    WHERE img_escudo IS NOT NULL
      AND (img_escudo LIKE 'data:%' OR char_length(img_escudo) > 255)
    """,
    "ALTER TABLE jugador ALTER COLUMN img_foto TYPE VARCHAR(255)",
    "ALTER TABLE datos_equipo ALTER COLUMN img_escudo TYPE VARCHAR(255)",
]


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
            print("OK:", " ".join(stmt.split())[:80])
        rows = conn.execute(
            text(
                """
                SELECT table_name, column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE column_name IN ('img_foto', 'img_escudo')
                ORDER BY 1, 2
                """
            )
        ).fetchall()
        for row in rows:
            print(row)


if __name__ == "__main__":
    main()
