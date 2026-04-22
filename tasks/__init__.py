"""Background jobs for periodic collection + weather snapshots.

We run them inside the FastAPI process via an asyncio task (see
`tasks.scheduler.start`) rather than Celery/beat, because on Render one
web service is enough for the current load and a second worker service
would double the hosting cost without a payoff yet.
"""

from .scheduler import start, stop

__all__ = ["start", "stop"]
