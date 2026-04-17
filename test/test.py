import json
import sqlite3


def main() -> None:
    conn = sqlite3.connect("test_example.db")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dict_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL
        )
        """
    )

    sample_dict = {
        "title": "A Minimal SQLite Example",
        "author": "Alice",
        "year": 2026,
    }

    conn.execute(
        "INSERT INTO dict_store (data) VALUES (?)",
        (json.dumps(sample_dict, ensure_ascii=False),),
    )
    conn.commit()

    row = conn.execute(
        "SELECT data FROM dict_store ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    loaded_dict = json.loads(row[0])
    print("读取到的字典:", loaded_dict)


if __name__ == "__main__":
    main()
