"""Generate JSON schema from Pydantic Config class."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from aidetector.config import Config


def main() -> None:
    """Generate config.schema.json from Pydantic Config class."""
    schema = TypeAdapter(Config).json_schema()

    # Write to detector root directory (src/aidetector -> src -> detector)
    output_path = Path(__file__).parent.parent.parent / "config.schema.json"

    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"Generated JSON schema: {output_path}")


if __name__ == "__main__":
    main()
