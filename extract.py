import os
import shutil
import psycopg2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import math
import time
import datetime
import sqlite3


# requires postgresql-common and libpq-dev


class Shared:
    target_host = os.environ['TARGET_HOST'] if 'TARGET_HOST' in os.environ else 'localhost'
    target_path = os.environ['TARGET_PATH'] if 'TARGET_PATH' in os.environ else 'target'
    timestamp_path = os.environ['TIMESTAMP_PATH'] if 'TIMESTAMP_PATH' in os.environ else 'timestamp.dump'
    no_partitions = os.environ['NO_PARTITIONS'] if 'NO_PARTITIONS' in os.environ else 'no_part.dump'
    postgres_user = os.environ['POSTGRES_USER'] if 'POSTGRES_USER' in os.environ else 'camunda'
    postgres_password = os.environ['POSTGRES_PASSWORD'] if 'POSTGRES_PASSWORD' in os.environ else 'camunda'
    postgres_db = os.environ['POSTGRES_DB'] if 'POSTGRES_DB' in os.environ else 'process-engine'
    sleep_schedule = os.environ['SLEEP_SCHEDULE'] if 'SLEEP_SCHEDULE' in os.environ else 600
    desidered_number_of_events_per_partition = os.environ[
        'NUM_EVENTS_PARTITION'] if 'NUM_EVENTS_PARTITION' in os.environ else 10000
    # the following has the priority over the desidered number of events per partition, if defined
    # it is also written to a file
    desidered_number_of_partitions = os.environ['NUM_PARTITIONS'] if 'NUM_PARTITIONS' in os.environ else None
    num_events_chunk = os.environ['NUM_EVENTS_CHUNK'] if 'NUM_EVENTS_CHUNK' in os.environ else 10000
    pm4pyws_db_event_logs = os.environ['PM4PYWS_DB_ELOG'] if 'PM4PYWS_DB_ELOG' in os.environ else 'event_logs.db'


def initialize_target_path():
    if not os.path.exists(Shared.target_path):
        os.mkdir(Shared.target_path)


def initialize_timestamp_path():
    if not os.path.exists(Shared.timestamp_path):
        F = open(Shared.timestamp_path, "w")
        F.write("1000\n")
        F.close()


def read_timestamp_path():
    return float(open(Shared.timestamp_path, "r").readline())


def write_timestamp(tim):
    F = open(Shared.timestamp_path, "w")
    F.write(str(float(tim)) + "\n")
    F.close()


def read_no_part():
    if os.path.exists(Shared.no_partitions):
        return int(open(Shared.no_partitions, "r").readline())
    return None


def write_no_part(no):
    F = open(Shared.no_partitions, "w")
    F.write(str(int(no)) + "\n")
    F.close()


def write_partitions(partitions):
    for process in partitions:
        process_path = os.path.join(Shared.target_path, process) + ".parquet"
        if not os.path.exists(process_path):
            os.mkdir(process_path)
        for partition in partitions[process]:
            target_path = os.path.join(process_path, partition) + ".parquet"
            df = pd.DataFrame(partitions[process][partition])
            if os.path.exists(target_path):
                df0 = pq.read_pandas(target_path).to_pandas()
                df = pd.concat([df0, df])
            table = pa.Table.from_pandas(df)
            pq.write_table(table, target_path)


def extract_events_from_db():
    print(time.time(), "start extraction")
    conn = psycopg2.connect(
        "dbname='" + Shared.postgres_db + "' user='" + Shared.postgres_user + "' host='" + Shared.target_host + "' password='" + Shared.postgres_password + "'")
    cur = conn.cursor()
    table_schema = []
    cur.execute(
        "select column_name, data_type, character_maximum_length from INFORMATION_SCHEMA.COLUMNS where table_name = 'act_hi_actinst'")
    rows = cur.fetchall()
    for row in rows:
        table_schema.append(row[0])
    this_timestamp = read_timestamp_path()
    this_timestamp2 = datetime.datetime.fromtimestamp(this_timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")
    print("this_timestamp2", this_timestamp2)
    Shared.desidered_number_of_partitions = read_no_part()
    cur.execute("SELECT * FROM public.act_hi_actinst WHERE start_time_ > '" + this_timestamp2 + "'")
    rows = cur.fetchall()
    if Shared.desidered_number_of_partitions is None:
        len_rows = len(rows)
        print("len_rows = " + str(len_rows))
        Shared.desidered_number_of_partitions = math.ceil(len_rows / Shared.desidered_number_of_events_per_partition)
        print("desidered_number_of_partitions =" + str(Shared.desidered_number_of_partitions))
        write_no_part(Shared.desidered_number_of_partitions)
    partitions = {}
    max_timestamp = -1
    no_chunks = 1
    no_events = 0
    for index, row in enumerate(rows):
        no_events = no_events + 1
        if index > 0 and index % Shared.num_events_chunk == 0:
            print("writing chunk " + str(no_chunks))
            write_partitions(partitions)
            partitions = None
            partitions = {}
            no_chunks = no_chunks + 1
        this_row = {table_schema[i]: row[i] for i in range(len(row))}
        process = this_row["proc_def_key_"]
        if not process in partitions:
            partitions[process] = {}
        this_row["case:concept:name"] = str(this_row["proc_inst_id_"])
        this_row["concept:name"] = this_row["act_name_"]
        this_row["time:timestamp"] = this_row["start_time_"]
        partition = str(abs(hash(this_row["case:concept:name"])) % Shared.desidered_number_of_partitions)
        # this_row["@@partition"] = abs(hash(this_row["case:concept:name"]))
        if "assignee_" in this_row:
            this_row["org:resource"] = this_row["assignee_"]
        max_timestamp = max(max_timestamp, this_row["time:timestamp"].timestamp())

        if not partition in partitions[process]:
            partitions[process][partition] = []
        partitions[process][partition].append(this_row)

    print("writing chunk " + str(no_chunks))
    write_partitions(partitions)

    print("total number of events extracted: " + str(no_events))

    if max_timestamp > -1:
        write_timestamp(max_timestamp)
        update_db_event_logs()


def update_db_event_logs():
    if os.path.exists(Shared.pm4pyws_db_event_logs):
        conn = sqlite3.connect(Shared.pm4pyws_db_event_logs)
        curs = conn.cursor()
        curs.execute("DELETE FROM EVENT_LOGS")

        content = os.listdir(Shared.target_path)

        for log_file in content:
            log_name = log_file.split(".parquet")[0]
            log_path = os.path.join(Shared.target_path, log_file)
            curs.execute("INSERT INTO EVENT_LOGS VALUES ('" + log_name + "','" + log_path + "',0,1,0)")

        conn.commit()
        conn.close()


if __name__ == "__main__":
    initialize_target_path()
    initialize_timestamp_path()
    while True:
        extract_events_from_db()
        time.sleep(Shared.sleep_schedule)
