FROM quay.io/jupyter/scipy-notebook:python-3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

USER ${NB_UID}

# Extra data-science deps on top of scipy-notebook's defaults
RUN pip install --no-cache-dir \
        psycopg[binary]==3.2.* \
        sqlalchemy==2.* \
        prophet==1.1.* \
        plotly==5.* \
        seaborn==0.13.* \
        ipywidgets==8.*

WORKDIR /home/jovyan/work
EXPOSE 8888
