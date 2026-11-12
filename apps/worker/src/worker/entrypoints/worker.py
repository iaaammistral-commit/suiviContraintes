"""Point d'entree du worker Mistral Workflows."""
import asyncio

import mistralai.workflows as workflows


async def main() -> None:
    classes = workflows.discover_all_workflows_in_package("worker.workflows")
    await workflows.run_worker(classes)


if __name__ == "__main__":
    asyncio.run(main())
