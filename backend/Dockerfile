FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install QGIS and dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    gnupg \
    lsb-release \
    ca-certificates \
    && wget -qO - https://qgis.org/downloads/qgis-2022.gpg.key | gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/qgis-archive.gpg --import \
    && chmod a+r /etc/apt/trusted.gpg.d/qgis-archive.gpg \
    && add-apt-repository "deb https://qgis.org/ubuntu $(lsb_release -c -s) main" \
    && apt-get update \
    && apt-get install -y \
        qgis \
        python3-qgis \
        python3-qgis-common \
        qgis-providers \
        qgis-providers-common \
        python3-pip \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    rasterio \
    geopandas \
    shapely \
    matplotlib \
    seaborn \
    scikit-learn \
    pandas \
    numpy \
    pyproj \
    fastapi \
    uvicorn \
    --break-system-packages

WORKDIR /app
COPY services/ /app/services/

ENV QT_QPA_PLATFORM=offscreen
ENV DISPLAY=:99
ENV PYTHONPATH="${PYTHONPATH}:/usr/lib/python3/dist-packages"

RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &\nsleep 2\nexec "$@"' > /entrypoint.sh && \
chmod +x /app/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["python3", "services/qgis_mapping.py"]
