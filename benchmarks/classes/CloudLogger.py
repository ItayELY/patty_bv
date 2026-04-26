import time
import boto3
from botocore.exceptions import ClientError

LOG_GROUP = "patty"
ERROR_STREAM = "errors"


class CloudLogger:
    def __init__(self, experiment):
        self.client = boto3.client("logs")

        self.streamName = experiment
        self.errorStreamName = f"{experiment}-{ERROR_STREAM}"

        self.sequence_tokens = {}

        self.__create_log_group()
        self.__create_log_stream(self.streamName)
        self.__create_log_stream(self.errorStreamName)

    def log(self, message):
        self.__put(
            stream=self.streamName,
            message=message
        )

    def error(self, error):
        self.__put(
            stream=self.errorStreamName,
            message=error
        )

    # ---------------- internal ---------------- #

    def __create_log_group(self):
        try:
            self.client.create_log_group(logGroupName=LOG_GROUP)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise

    def __create_log_stream(self, name):
        try:
            self.client.create_log_stream(
                logGroupName=LOG_GROUP,
                logStreamName=name
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise

    def __put(self, stream, message):
        event = {
            "timestamp": int(time.time() * 1000),
            "message": str(message),
        }

        kwargs = {
            "logGroupName": LOG_GROUP,
            "logStreamName": stream,
            "logEvents": [event],
        }

        if stream in self.sequence_tokens:
            kwargs["sequenceToken"] = self.sequence_tokens[stream]

        response = self.client.put_log_events(**kwargs)
        self.sequence_tokens[stream] = response["nextSequenceToken"]
