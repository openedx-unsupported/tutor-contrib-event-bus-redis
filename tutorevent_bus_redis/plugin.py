from __future__ import annotations

import os
import os.path
from glob import glob

import click
import pkg_resources
from tutor import hooks

from .__about__ import __version__

########################################
# CONFIGURATION
########################################
# FIXME: Update this to a saner config structure less likely to break, and able
# to activate and deactivate individual events more easily.
PRODUCER_CONFIG = """{
    'org.openedx.content_authoring.xblock.published.v1': {
        'content-authoring-xblock-lifecycle':
        {'event_key_field': 'xblock_info.usage_key', 'enabled': False},
    'content-authoring-xblock-published':
        {'event_key_field': 'xblock_info.usage_key', 'enabled': False},
    },
    'org.openedx.content_authoring.xblock.deleted.v1': {
        'content-authoring-xblock-lifecycle':
        {'event_key_field': 'xblock_info.usage_key', 'enabled': False},
    },
    'org.openedx.learning.auth.session.login.completed.v1': {
        'user-login': {'event_key_field': 'user.pii.username', 'enabled': True},
    },
}
"""

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        # Add your new settings that have default values here.
        # Each new setting is a pair: (setting_name, default_value).
        # Prefix your setting names with 'EVENT_BUS_REDIS_'.
        ("EVENT_BUS_REDIS_VERSION", __version__),

        # Possible values are "kafka", "redis", or None to disable the
        # event bus
        ("EVENT_BUS_BACKEND", "kafka"),

        # Settings for producing events
        ("EVENT_BUS_SEND_CATALOG_INFO_SIGNAL", True),
        (
            # FIXME: We should only install the one that's configured
            "OPENEDX_EXTRA_PIP_REQUIREMENTS",
            [
                "edx-event-bus-redis==0.3.2",
                "edx-event-bus-kafka==v5.6.0",
                "openedx-events==v9.5.1",
                "confluent_kafka[avro,schema-registry]",
            ],
        ),
        ("EVENT_BUS_PRODUCER_CONFIG", PRODUCER_CONFIG),

        ######################################
        # redis backend settings
        # Version of https://github.com/openedx/event-bus-redis to install
        # This is what follows 'pip install' so you can use official versions
        # or install from forks / branches / PRs here
        ("EVENT_BUS_REDIS_RELEASE", "edx-event-bus-redis=='0.3.2'"),

        # If true, this will run a separate instance of redis just for the
        # event bus to prevent resource conflicts with other services
        # TODO: Implement this
        # ("RUN_DEDICATED_REDIS_BUS_SERVER", True),

        # Prefix for topics sent over the event bus
        ("EVENT_BUS_REDIS_TOPIC_PREFIX", "openedx"),

        # Producer class which can send events to redis streams.
        ("EVENT_BUS_REDIS_PRODUCER", "edx_event_bus_redis.create_producer"),

        # Consumer class which can consume events from redis streams.
        ("EVENT_BUS_REDIS_CONSUMER", "edx_event_bus_redis.RedisEventConsumer"),

        # If the consumer encounters this many consecutive errors, exit with an error. This is intended to be used in a
        # context where a management system (such as Kubernetes) will relaunch the consumer automatically.
        # Default is "None", which means the consumer will never relaunch.
        ("EVENT_BUS_REDIS_CONSUMER_CONSECUTIVE_ERRORS_LIMIT", 0),

        # How long the consumer should wait for new entries in a stream.
        # As we are running the consumer in a while True loop, changing this setting doesn't make much difference expect
        # for changing number of monitoring messages while waiting for new events.
        # https://redis.io/commands/xread/#blocking-for-data
        ("EVENT_BUS_REDIS_CONSUMER_POLL_TIMEOUT", 60),

        # Limits stream size to approximately this number
        ("EVENT_BUS_REDIS_STREAM_MAX_LEN", 10_000),

        ######################################
        # Kafka backend settings
        # TODO: Move hard coded settings from local-docker-compose-services here
        # Version of https://github.com/openedx/event-bus-kafka to install
        # This is what follows 'pip install' so you can use official versions
        # or install from forks / branches / PRs here
        ("EVENT_BUS_KAFKA_RELEASE", "edx-event-bus-kafka=='v5.6.0'"),

        # This will run schema-manager, zookeeper and kafka. Set to False if you
        # are using a 3rd party to host Kafka or managing it outside of Tutor.
        ("RUN_KAFKA_SERVER", True),

        # This will run kafka-control-center. This consumes a lot of resources,
        # you can turn it off separately from the required services. Requires
        # RUN_KAFKA_SERVER to be True as well.
        ("RUN_KAFKA_UI", True),

        ("EVENT_BUS_KAFKA_SCHEMA_REGISTRY_URL", "http://schema-registry:18081"),
        ("EVENT_BUS_KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
        ("EVENT_BUS_KAFKA_PRODUCER", "edx_event_bus_kafka.create_producer"),
        ("EVENT_BUS_KAFKA_CONSUMER", "edx_event_bus_kafka.KafkaEventConsumer"),
        ("EVENT_BUS_KAFKA_TOPIC_PREFIX", "dev"),
    ]
)

hooks.Filters.CONFIG_UNIQUE.add_items(
    [
        # Add settings that don't have a reasonable default for all users here.
        # For instance: passwords, secret keys, etc.
        # Each new setting is a pair: (setting_name, unique_generated_value).
        # Prefix your setting names with 'EVENT_BUS_REDIS_'.
        # For example:
        ### ("EVENT_BUS_REDIS_SECRET_KEY", "{{ 24|random_string }}"),
    ]
)

hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        # Danger zone!
        # Add values to override settings from Tutor core or other plugins here.
        # Each override is a pair: (setting_name, new_value). For example:
        ### ("PLATFORM_NAME", "My platform"),
    ]
)


########################################
# INITIALIZATION TASKS
########################################

# To add a custom initialization task, create a bash script template under:
# tutorevent_bus_redis/templates/event-bus-redis/jobs/init/
# and then add it to the MY_INIT_TASKS list. Each task is in the format:
# ("<service>", ("<path>", "<to>", "<script>", "<template>"))
MY_INIT_TASKS: list[tuple[str, tuple[str, ...]]] = [
    # For example, to add LMS initialization steps, you could add the script template at:
    # tutorevent_bus_redis/templates/event-bus-redis/jobs/init/lms.sh
    # And then add the line:
    ### ("lms", ("event-bus-redis", "jobs", "init", "lms.sh")),
]


# For each task added to MY_INIT_TASKS, we load the task template
# and add it to the CLI_DO_INIT_TASKS filter, which tells Tutor to
# run it as part of the `init` job.
for service, template_path in MY_INIT_TASKS:
    full_path: str = pkg_resources.resource_filename(
        "tutorevent_bus_redis", os.path.join("templates", *template_path)
    )
    with open(full_path, encoding="utf-8") as init_task_file:
        init_task: str = init_task_file.read()
    hooks.Filters.CLI_DO_INIT_TASKS.add_item((service, init_task))


########################################
# DOCKER IMAGE MANAGEMENT
########################################


# Images to be built by `tutor images build`.
# Each item is a quadruple in the form:
#     ("<tutor_image_name>", ("path", "to", "build", "dir"), "<docker_image_tag>", "<build_args>")
hooks.Filters.IMAGES_BUILD.add_items(
    [
        # To build `myimage` with `tutor images build myimage`,
        # you would add a Dockerfile to templates/event-bus-redis/build/myimage,
        # and then write:
        ### (
        ###     "myimage",
        ###     ("plugins", "event-bus-redis", "build", "myimage"),
        ###     "docker.io/myimage:{{ EVENT_BUS_REDIS_VERSION }}",
        ###     (),
        ### ),
    ]
)


# Images to be pulled as part of `tutor images pull`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PULL.add_items(
    [
        # To pull `myimage` with `tutor images pull myimage`, you would write:
        ### (
        ###     "myimage",
        ###     "docker.io/myimage:{{ EVENT_BUS_REDIS_VERSION }}",
        ### ),
    ]
)


# Images to be pushed as part of `tutor images push`.
# Each item is a pair in the form:
#     ("<tutor_image_name>", "<docker_image_tag>")
hooks.Filters.IMAGES_PUSH.add_items(
    [
        # To push `myimage` with `tutor images push myimage`, you would write:
        ### (
        ###     "myimage",
        ###     "docker.io/myimage:{{ EVENT_BUS_REDIS_VERSION }}",
        ### ),
    ]
)


########################################
# TEMPLATE RENDERING
# (It is safe & recommended to leave
#  this section as-is :)
########################################

hooks.Filters.ENV_TEMPLATE_ROOTS.add_items(
    # Root paths for template files, relative to the project root.
    [
        pkg_resources.resource_filename("tutorevent_bus_redis", "templates"),
    ]
)

hooks.Filters.ENV_TEMPLATE_TARGETS.add_items(
    # For each pair (source_path, destination_path):
    # templates at ``source_path`` (relative to your ENV_TEMPLATE_ROOTS) will be
    # rendered to ``source_path/destination_path`` (relative to your Tutor environment).
    # For example, ``tutorevent_bus_redis/templates/event-bus-redis/build``
    # will be rendered to ``$(tutor config printroot)/env/plugins/event-bus-redis/build``.
    [
        ("event-bus-redis/build", "plugins"),
        ("event-bus-redis/apps", "plugins"),
    ],
)


########################################
# PATCH LOADING
# (It is safe & recommended to leave
#  this section as-is :)
########################################

# For each file in tutorevent_bus_redis/patches,
# apply a patch based on the file's name and contents.
for path in glob(
    os.path.join(
        pkg_resources.resource_filename("tutorevent_bus_redis", "patches"),
        "*",
    )
):
    with open(path, encoding="utf-8") as patch_file:
        hooks.Filters.ENV_PATCHES.add_item((os.path.basename(path), patch_file.read()))


########################################
# CUSTOM JOBS (a.k.a. "do-commands")
########################################

# A job is a set of tasks, each of which run inside a certain container.
# Jobs are invoked using the `do` command, for example: `tutor local do importdemocourse`.
# A few jobs are built in to Tutor, such as `init` and `createuser`.
# You can also add your own custom jobs:

# To add a custom job, define a Click command that returns a list of tasks,
# where each task is a pair in the form ("<service>", "<shell_command>").
# For example:
### @click.command()
### @click.option("-n", "--name", default="plugin developer")
### def say_hi(name: str) -> list[tuple[str, str]]:
###     """
###     An example job that just prints 'hello' from within both LMS and CMS.
###     """
###     return [
###         ("lms", f"echo 'Hello from LMS, {name}!'"),
###         ("cms", f"echo 'Hello from CMS, {name}!'"),
###     ]


# Then, add the command function to CLI_DO_COMMANDS:
## hooks.Filters.CLI_DO_COMMANDS.add_item(say_hi)

# Now, you can run your job like this:
#   $ tutor local do say-hi --name="Open edX"


#######################################
# CUSTOM CLI COMMANDS
#######################################

# Your plugin can also add custom commands directly to the Tutor CLI.
# These commands are run directly on the user's host computer
# (unlike jobs, which are run in containers).

# To define a command group for your plugin, you would define a Click
# group and then add it to CLI_COMMANDS:


### @click.group()
### def event-bus-redis() -> None:
###     pass


### hooks.Filters.CLI_COMMANDS.add_item(event-bus-redis)


# Then, you would add subcommands directly to the Click group, for example:


### @event-bus-redis.command()
### def example_command() -> None:
###     """
###     This is helptext for an example command.
###     """
###     print("You've run an example command.")


# This would allow you to run:
#   $ tutor event-bus-redis example-command
