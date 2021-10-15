import click
import logging
import sys
import marshmallow.exceptions
import twisted.internet.error
from prometheus_client import twisted
from ruamel.yaml import YAML, YAMLError
from alibabacloud_credentials.exceptions import CredentialException
from prometheus_client.core import REGISTRY
from prometheus_client.twisted import MetricsResource
from twisted.web.server import Site, GzipEncoderFactory
from twisted.web.resource import Resource, EncodingResourceWrapper
from twisted.internet import reactor
from .config import ConfigSchema
from .collector import AliyunCollector
from .utils import OneLineExceptionFormatter

logger = logging.getLogger(__name__)


@click.command()
@click.option("--config", "-c", default="config.yaml")
@click.option("--port", "-p", default=9107)
def main(config, port):
    # 配置logger
    root_logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        OneLineExceptionFormatter(
            "time:%(asctime)s\tname:%(name)s\tlevel:%(levelname)s\tthreadName:%(threadName)s\tmessage:%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
    )
    root_logger.addHandler(console_handler)

    # 读入配置并使用marshmallow定义的模式验证、转换为python对象
    yaml=YAML(typ='safe')
    try:
        with open(config, "r") as file:
            config_file = yaml.load(file)
        schema = ConfigSchema()
        config = schema.load(config_file)
        root_logger.setLevel(config.log_level.upper())
        collector = AliyunCollector(config)
    except FileNotFoundError as e:
        logger.fatal(e)
        sys.exit(1)
    except YAMLError as e:
        message = str(e).replace('\n', '|')
        logger.fatal(f"Configure file load error! Error: {message}")
        sys.exit(1)
    except marshmallow.exceptions.ValidationError as e:
        logger.fatal(f"Configure file validate failed! Error: {e.messages}")
        sys.exit(1)
    except CredentialException as e:
        logger.fatal(e)
        sys.exit(1)
    except Exception as e:
        logger.fatal(f"Unexcepted error! Error: {e}")

    REGISTRY.register(collector)

    try:
        root = Resource()
        wrapped = EncodingResourceWrapper(MetricsResource(), [GzipEncoderFactory()])
        root.putChild(b'metrics', wrapped)

        factory = Site(root)
        reactor.listenTCP(port, factory)
        logger.warning(f"Staring server...")
        reactor.run()
    except (twisted.internet.error.CannotListenError, twisted.internet.error.BindError) as e:
        logger.fatal("Twisted启动失败", exc_info=e)
        sys.exit(1)
