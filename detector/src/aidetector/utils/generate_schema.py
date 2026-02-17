import json

from aidetector.utils.config import Config
from openai.types import Metadata
from pydantic import TypeAdapter


def main() -> None:
    config = (TypeAdapter(Config).json_schema(), "../config/config.schema.json")
    metadata = (TypeAdapter(Metadata).json_schema(), "../config/metadata.schema.json")

    for schema, output_path in [config, metadata]:
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Generated JSON schema: {output_path}")


if __name__ == "__main__":
    main()
