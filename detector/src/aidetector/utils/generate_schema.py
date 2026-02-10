"""Generate JSON schema from Pydantic Config class."""

import json

from pydantic import TypeAdapter

from aidetector.utils.config import Config


def main() -> None:
    schema = TypeAdapter(Config).json_schema()
    output_path = "../config/config.schema.json"

    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"Generated JSON schema: {output_path}")


if __name__ == "__main__":
    main()
