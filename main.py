import time
import click
import docker
import boto3
from botocore.config import Config
from docker.errors import ImageNotFound, APIError
from botocore.exceptions import ClientError, UnknownServiceError
from botocore.errorfactory import BaseClientExceptions


DOCKER_CLI = docker.from_env()

ALLOWED_REGIONS = click.Choice([
    "us-east-1", "us-west-1", "eu-central-1", "eu-central-2", # ...
])


def validate_image_exists(ctx, param, value):
    try:
        DOCKER_CLI.images.pull(value)
    except ImageNotFound:
        raise click.BadParameter("Image not found")
    except APIError:
        raise click.BadParameter("Unexpected error on docker host side")
    return value


def decorate_bash_command(ctx, param, value):
    if "python -c " in value:
        raise click.BadParameter("Use `-u` flag with python to unbuffer stdout")
    return ["/bin/sh", "-c", value]


def validate_aws_credentials(ctx, param, value):
    try:
        boto3.client("sts",
            aws_access_key_id=ctx.params["aws_access_key_id"],
            aws_secret_access_key=value,
            region_name=ctx.params["aws_region"],
        ).get_caller_identity()
    except ClientError:
        raise click.BadParameter("Wrong AWS credentials")
    except UnknownServiceError:
        raise click.BadParameter("Unexpected error on AWS host side")
    return value


class CloudWatchHandler:
    def __init__(self, group_name, stream_name, **kwargs):
        self._client = boto3.client("logs", **kwargs)
        self._group_name, self._stream_name = group_name, stream_name
        self._create_targets()

    def _create_targets(self):
        """ Create corresponding AWS CloudWatch group and stream if does not exist."""
        try:
            self._client.create_log_group(logGroupName=self._group_name)
        except self._client.exceptions.ResourceAlreadyExistsException:
            ...
        except:
            raise click.UsageError("Unexpected error on AWS host side")
        try:
            self._client.create_log_stream(
                logGroupName=self._group_name,
                logStreamName=self._stream_name
            )
        except self._client.exceptions.ResourceAlreadyExistsException:
            ...
        except:
            raise click.UsageError("Unexpected error on AWS host side")

    def log(self, message):
        """ Send stdout to AWS CloudWatch """
        message = str(message.strip())
        try:
            self._client.put_log_events(
                logGroupName=self._group_name,
                logStreamName=self._stream_name,
                logEvents=[
                    {
                        'timestamp': int(time.time()),
                        'message': message
                    },
                ],
            )
            print(message)
        except BaseClientExceptions:
            raise click.UsageError("Unexpected error on AWS host side")


@click.command()
@click.option("--docker-image", required=True, callback=validate_image_exists)
@click.option("--bash-command", required=True, callback=decorate_bash_command)
@click.option("--aws-region", required=True, type=ALLOWED_REGIONS)
@click.option("--aws-access-key-id", required=True)
@click.option("--aws-secret-access-key", required=True, callback=validate_aws_credentials)
@click.option("--aws-cloudwatch-group", required=True)
@click.option("--aws-cloudwatch-stream", required=True)
def main(
    docker_image,
    bash_command,
    aws_region,
    aws_access_key_id,
    aws_secret_access_key,
    aws_cloudwatch_group,
    aws_cloudwatch_stream,
):
    container = DOCKER_CLI.containers.run(
        docker_image, bash_command, detach=True
    )
    logger = CloudWatchHandler(
        aws_cloudwatch_group,
        aws_cloudwatch_stream,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region,
    )
    for line in container.logs(stream=True):
        logger.log(line)


if __name__ == "__main__":
    main()
