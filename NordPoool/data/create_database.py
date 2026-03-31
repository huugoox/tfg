from pathlib import Path
import sqlite3


def create_database():
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    db_path = project_root / "data" / "thesis_database.db"
    schema_path = project_root / "sql" / "thesis_schema.sql"

    print(f"Script path:   {script_path}")
    print(f"Project root:  {project_root}")
    print(f"DB path:       {db_path}")
    print(f"Schema path:   {schema_path}")

    if not schema_path.exists():
        raise FileNotFoundError(f"No se encontró el schema: {schema_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print("\nBase creada. Verificando contenido SQLite...")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tablas encontradas:", tables)
    finally:
        conn.close()

    with open(db_path, "rb") as f:
        header = f.read(16)
    print("Cabecera archivo:", header)


if __name__ == "__main__":
    create_database()