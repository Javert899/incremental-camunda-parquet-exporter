Incremental process Mining exporter for the Camunda workflow management system (supported by PostgreSQL database)

This extractor, after doing an initial extraction of the event log from the Camunda database, updates it periodically
with the new events inserted into the database.

Moreover, the BPMN diagram in Camunda can be exported (by doing copy-process-models.sh).

----------------------------------

As a test bench, it can be executed in any Linux machine where a Docker container is installed by executing the Bash
script execute.bash. The script:
- Set ups the PostgreSQL database (port 5432)
- Downloads a test Camunda environment that is automatically installed as Docker container. The environment contains
already some test data that can be used for Process Mining analysis (port 8080).
- Downloads the PM4Py Web Services and sets them up (port 80)
- Downloads this incremental Camunda extractor, and lays into execution (the event log is updated with the latest events,
with a frequency of 10 minutes).


----------------------------------

As a standalone project, it can be executed by specifying the following parameters as environment variables,
and then executing the script extract.py:

TARGET_PATH -> Specifies a path where the event log is written 
TIMESTAMP_PATH -> Specifies a path where a file containing the timestamp of the last update is written
NO_PARTITIONS -> Specifies a path where a file containing the number of partitions of the event log is written
TARGET_HOST -> Specifies the target host of the PostgreSQL database (e.g., localhost)
POSTGRES_USER -> Specifies the name of the PostgreSQL user to use to connect to the database
POSTGRES_PASSWORD -> Specifies the password of the PostgreSQL user
POSTGRES_DB -> Specifies the PostgreSQL database to connect to
SLEEP_SCHEDULE -> Specifies the update frequency of the event log (e.g. 600 seconds if the update has to occur every 10 minutes)
NUM_EVENTS_PARTITION -> Specifies the numer of events for each partition of the event log
NUM_EVENTS_CHUNK -> Specifies the size of the chunk events that is read from database, and saved into the log, at every iteration
