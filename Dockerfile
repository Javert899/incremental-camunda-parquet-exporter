FROM python:3.6

RUN apt-get update
RUN apt-get -y upgrade
RUN apt-get -y install nano vim git python3-tk zip unzip ftp postgresql-common libpq-dev
RUN pip install pyarrow==0.13.0 pandas>=0.24.1 psycopg2

COPY . /

RUN cd /opt && mkdir files
RUN cd /opt && mkdir extraction_consts

ENTRYPOINT ["python", "main.py"]