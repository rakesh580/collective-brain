from app.ingestion.base import BaseConnector
from app.ingestion.discord_connector import DiscordConnector
from app.ingestion.git_connector import GitConnector
from app.ingestion.markdown_connector import MarkdownConnector
from app.ingestion.slack_connector import SlackConnector
from app.ingestion.task_connector import TaskConnector

_REGISTRY: dict[str, type[BaseConnector]] = {
    "git": GitConnector,
    "slack": SlackConnector,
    "discord": DiscordConnector,
    "markdown": MarkdownConnector,
    "tasks": TaskConnector,
}


def get_connector(source_type: str, **kwargs) -> BaseConnector:
    cls = _REGISTRY.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source type: {source_type}. Available: {list(_REGISTRY.keys())}")
    return cls(**kwargs)


def register_connector(source_type: str, connector_cls: type[BaseConnector]):
    _REGISTRY[source_type] = connector_cls
