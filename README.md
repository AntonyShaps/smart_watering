# smart_watering

Current config runs both postgrsql and pgadming with docker-compose

To ingest data upload_data.ipynb is needed to be run (this will be replaced)

postgresql:

    - POSTGRES_USER=root

    - POSTGRES_PASSWORD=root

    - POSTGRES_DB=sensors_data


pgadmin:

    - PGADMIN_DEFAULT_EMAIL=admin@admin.com
    
    - PGADMIN_DEFAULT_PASSWORD=root
