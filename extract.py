import os
import shutil
import psycopg2
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# requires postgresql-common and libpq-dev


class Shared:
    target_host = os.environ['TARGET_HOST'] if 'TARGET_HOST' in os.environ else 'localhost'
    target_path = os.environ['TARGET_PATH'] if 'TARGET_PATH' in os.environ else 'target'
    timestamp_path = os.environ['TIMESTAMP_PATH'] if 'TIMESTAMP_PATH' in os.environ else 'timestamp.dump'
    no_events_partition_path = os.environ['NO_EV_PART_PATH'] if 'NO_EV_PART_PATH' in os.environ else 'no_ev.dump'
    postgres_user = os.environ['POSTGRES_USER'] if 'POSTGRES_USER' in os.environ else 'camunda'
    postgres_password = os.environ['POSTGRES_PASSWORD'] if 'POSTGRES_PASSWORD' in os.environ else 'camunda'
    postgres_db = os.environ['POSTGRES_DB'] if 'POSTGRES_DB' in os.environ else 'process-engine'
    sleep_schedule = os.environ['SLEEP_SCHEDULE'] if 'SLEEP_SCHEDULE' in os.environ else 60
    desidered_number_of_events_per_partition = os.environ['NUM_EVENTS_PARTITION'] if 'NUM_EVENTS_PARTITION' in os.environ else 10
    # the following has the priority over the desidered number of events per partition, if defined
    # it is also written to a file
    desidered_number_of_partitions = os.environ['NUM_PARTITIONS'] if 'NUM_PARTITIONS' in os.environ else None
    num_events_chunk = os.environ['NUM_EVENTS_CHUNK'] if 'NUM_EVENTS_CHUNK' in os.environ else 10


def initialize_target_path():
    if not os.path.exists(Shared.target_path):
        os.mkdir(Shared.target_path)


def initialize_timestamp_path():
    if not os.path.exists(Shared.timestamp_path):
        F = open(Shared.timestamp_path, "w")
        F.write("1000\n")
        F.close()


def read_timestamp_path():
    return int(open(Shared.timestamp_path, "r").readline())


def read_no_ev_part_path():
    if os.path.exists(Shared.no_events_partition_path):
        return int(open(Shared.no_events_partition_path, "r").readline())
    return None


def write_partitions(partitions):
    for partition in partitions:
        target_path = os.path.join(Shared.target_path, partition) + ".parquet"
        df = pd.DataFrame(partitions[partition])
        if os.path.exists(target_path):
            df0 = pq.read_pandas(target_path).to_pandas()
            df = pd.concat([df0, df])
        table = pa.Table.from_pandas(df)
        pq.write_table(table, target_path)


def extract_events_from_db():
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
    cur.execute("SELECT * FROM public.act_hi_actinst")
    rows = cur.fetchall()
    if Shared.desidered_number_of_partitions is None:
        len_rows = len(rows)
        print("len_rows = " + str(len_rows))
        Shared.desidered_number_of_partitions = len_rows / Shared.desidered_number_of_events_per_partition
        print("desidered_number_of_partitions =" + str(Shared.desidered_number_of_partitions))
    partitions = {}
    max_timestamp = -1
    no_chunks = 1
    for index, row in enumerate(rows):
        if index > 0 and index % Shared.num_events_chunk == 0:
            print("writing chunk "+str(no_chunks))
            write_partitions(partitions)
            partitions = None
            partitions = {}
            no_chunks = no_chunks + 1
        this_row = {table_schema[i]: row[i] for i in range(len(row))}
        this_row["case:concept:name"] = str(this_row["proc_inst_id_"])
        this_row["concept:name"] = this_row["act_name_"]
        this_row["time:timestamp"] = this_row["start_time_"]
        partition = str(abs(hash(this_row["case:concept:name"])) % Shared.desidered_number_of_partitions)
        #this_row["@@partition"] = abs(hash(this_row["case:concept:name"]))
        max_timestamp = max(max_timestamp, this_row["time:timestamp"].timestamp())

        if not partition in partitions:
            partitions[partition] = []
        partitions[partition].append(this_row)

    print("writing chunk " + str(no_chunks))
    write_partitions(partitions)


if __name__ == "__main__":
    initialize_target_path()
    initialize_timestamp_path()
    extract_events_from_db()
