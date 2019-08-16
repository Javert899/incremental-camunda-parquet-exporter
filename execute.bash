rm -rRf /opt/files && wget www.alessandroberti.it/files.tar && tar xvf files.tar && mv files /opt/files
rm -rRf /opt/extraction_consts && mkdir /opt/extraction_consts
docker-compose up