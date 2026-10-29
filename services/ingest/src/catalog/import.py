import asyncio
from src.catalog.importer import main

# CLI entrypoint: python -m src.catalog.import GAME_ID TROPHIES_HTML [GUIDE_HTML]
if __name__ == "__main__":
    asyncio.run(main())
