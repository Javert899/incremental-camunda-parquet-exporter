docker-compose down
rm -rRf /opt/files && wget www.alessandroberti.it/files.tar && tar xvf files.tar && mv files /opt/files
rm -rRf /opt/extraction_consts && mkdir /opt/extraction_consts
docker-compose up -d postgres
sleep 7
docker-compose up -d camunda
sleep 7
docker-compose up -d pm4pyws
sleep 7
docker-compose up camunda-exporter
sleep 7

