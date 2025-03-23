# smart_watering

Current config runs both postgrsql and pgadming with docker-compose

To ingest data upload_data.ipynb is needed to be run (this will be replaced)(UPDATED SEE BELOW)

To ingest simulated data run the following:

    docker-compose up

In backend folder run:     

    uvicorn main:app --host 0.0.0.0 --port 8000

    python3 simulation.py


postgresql:

    - POSTGRES_USER=root

    - POSTGRES_PASSWORD=root

    - POSTGRES_DB=sensors_data


pgadmin:

    - PGADMIN_DEFAULT_EMAIL=admin@admin.com

    - PGADMIN_DEFAULT_PASSWORD=root
