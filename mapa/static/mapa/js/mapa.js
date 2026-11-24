// Coordenadas centrales de Bogotá
const bogota = [4.6097, -74.0817];

// Crear el mapa
const mapa = L.map('mapa').setView(bogota, 11);

// Mapa base
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
}).addTo(mapa);


// Obtener la ruta del archivo JSON
const rutaLocalidades = document
    .getElementById('mapa')
    .dataset.localidadesUrl;

    // Obtener la ruta de los seguimientos
const rutaSeguimientos = document
    .getElementById('mapa')
    .dataset.seguimientosUrl;
    // Obtener las estadísticas de las localidades desde Django
const localidadesEstadisticas = JSON.parse(
    document.getElementById('localidades-data').textContent
);


// Normalizar nombres para comparar localidades
function normalizarNombre(nombre) {
    return (nombre || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();
}


// Mostrar información de una localidad en el panel
function mostrarInformacionLocalidad(nombre) {

    const localidad = localidadesEstadisticas.find(item =>
        normalizarNombre(item.n_localidad) === normalizarNombre(nombre)
    );

    const contenedor = document.getElementById('detalle-seleccion');

    // Limpiar la información anterior
    contenedor.replaceChildren();

    if (!localidad) {
        contenedor.textContent = 'No se encontró información de esta localidad.';
        return;
    }

    const titulo = document.createElement('h3');
    titulo.textContent = localidad.n_localidad;

    const poblacion = document.createElement('p');
    poblacion.textContent =
        'Población: ' +
        Number(localidad.poblacion || 0).toLocaleString('es-CO');

    const seguimientos = document.createElement('p');
    seguimientos.textContent =
        'Seguimientos: ' + localidad.total_seguimientos;

    const tasa = document.createElement('p');
    tasa.textContent =
        'Tasa de reportes: ' +
        Number(localidad.tasa_reportes || 0).toLocaleString('es-CO') +
        ' por cada 10.000 habitantes';

    contenedor.append(titulo, poblacion, seguimientos, tasa);
}


// Mostrar información de un seguimiento en el panel
function mostrarInformacionSeguimiento(seguimiento) {

    const contenedor = document.getElementById('detalle-seleccion');

    contenedor.replaceChildren();

    const titulo = document.createElement('h3');
    titulo.textContent = seguimiento.titulo || 'Sin título';

    const animal = document.createElement('p');
    animal.textContent =
        'Animal: ' + (seguimiento.animal_nombre || 'No especificado');

    const estado = document.createElement('p');
    estado.textContent =
        'Estado: ' + (seguimiento.estado_seguimiento || 'No especificado');

    const localidad = document.createElement('p');
    localidad.textContent =
        'Localidad: ' + (seguimiento.n_localidad || 'No especificada');

    const boton = document.createElement('a');
    boton.className = 'boton';
    boton.textContent = 'Ver detalles';

    boton.href = URL_DETALLE_SEGUIMIENTO.replace(
        '/0/',
        `/${seguimiento.id_seguimiento}/`
    );

    contenedor.append(titulo, animal, estado, localidad, boton);
}


// Colores de los marcadores según el estado
const coloresEstados = {
    perdido: '#E53935',
    encontrado: '#ffdd00',
    en_busqueda: '#FB8C00',
    en_refugio: '#8E44AD',
    reunido: '#1E88E5',
    adoptado: '#2E7D32'
};


// Generar una posición aproximada dentro de una localidad
function generarPosicion(bounds, indice, total) {

    const centro = bounds.getCenter();

    const columnas = Math.ceil(Math.sqrt(total));
    const filas = Math.ceil(total / columnas);

    const columna = indice % columnas;
    const fila = Math.floor(indice / columnas);

    const pasoLat = bounds.getNorth() - bounds.getSouth();
    const pasoLng = bounds.getEast() - bounds.getWest();

    const lat = centro.lat +
        ((fila / Math.max(filas, 1)) - 0.5) * pasoLat * 0.5;

    const lng = centro.lng +
        ((columna / Math.max(columnas, 1)) - 0.5) * pasoLng * 0.5;

    return [lat, lng];
}

// Comprobar si un punto está dentro de un anillo
function puntoDentroAnillo(punto, anillo) {

    const x = punto[0];
    const y = punto[1];

    let dentro = false;

    for (
        let i = 0, j = anillo.length - 1;
        i < anillo.length;
        j = i++
    ) {
        const xi = anillo[i][0];
        const yi = anillo[i][1];

        const xj = anillo[j][0];
        const yj = anillo[j][1];

        const intersecta =
            ((yi > y) !== (yj > y)) &&
            (x < (xj - xi) * (y - yi) / (yj - yi) + xi);

        if (intersecta) {
            dentro = !dentro;
        }
    }

    return dentro;
}


// Comprobar si un punto pertenece a una localidad
function puntoDentroLocalidad(punto, geometria) {

    return geometria.coordinates.some(poligono =>
        puntoDentroAnillo(punto, poligono[0])
    );
}


// Generar una posición aproximada, preferiblemente cerca del centro
function generarPosicionValida(bounds, geometria) {

    const centro = bounds.getCenter();

    const alto = bounds.getNorth() - bounds.getSouth();
    const ancho = bounds.getEast() - bounds.getWest();

    // Intentar primero en una zona más cercana al centro
    for (let intento = 0; intento < 1500; intento++) {

        const lat = centro.lat +
            (Math.random() - 0.5) * alto * 0.45;

        const lng = centro.lng +
            (Math.random() - 0.5) * ancho * 0.45;

        if (puntoDentroLocalidad([lng, lat], geometria)) {
            return [lat, lng];
        }
    }

    // Si no encuentra una posición central,
    // ampliar el área de búsqueda
    for (let intento = 0; intento < 1500; intento++) {

        const lat = bounds.getSouth() +
            Math.random() * alto;

        const lng = bounds.getWest() +
            Math.random() * ancho;

        if (puntoDentroLocalidad([lng, lat], geometria)) {
            return [lat, lng];
        }
    }

    // Último recurso: centro de la localidad
    return [centro.lat, centro.lng];
}



// Cargar las localidades
fetch(rutaLocalidades)
    .then(response => {
        if (!response.ok) {
            throw new Error('No se pudo cargar el archivo de localidades');
        }

        return response.json();
    })
    .then(datos => {

        // Convertir Esri JSON a GeoJSON
        const geojson = {
            type: 'FeatureCollection',

            features: datos.features.map(feature => ({
                type: 'Feature',

                properties: feature.attributes,

                geometry: {
                    type: 'MultiPolygon',

                    coordinates: feature.geometry.rings.map(ring => [
                        ring
                    ])
                }
            }))
        };


        // Dibujar las localidades
        const capaLocalidades = L.geoJSON(geojson, {

            style: {
                color: '#8A2C46',
                weight: 2,
                opacity: 0.9,
                fillColor: '#E39CB6',
                fillOpacity: 0.12
            },

            onEachFeature: function (feature, layer) {

                const nombre = feature.properties.LocNombre;

                layer.bindPopup(`
                    <div class="popup-localidad">
                        <h3>${nombre}</h3>
                    </div>
                `);

                // Mostrar información al seleccionar una localidad
layer.on('click', function () {
    mostrarInformacionLocalidad(nombre);
});




                layer.on('mouseover', function () {
                    layer.setStyle({
                        weight: 3,
                        fillOpacity: 0.3
                    });
                });

                layer.on('mouseout', function () {
                    capaLocalidades.resetStyle(layer);
                });
            }

        }).addTo(mapa);

        // Ajustar el mapa para mostrar todas las localidades
        mapa.fitBounds(capaLocalidades.getBounds());


        // Cargar los seguimientos desde Django
fetch(rutaSeguimientos)
    .then(response => {
        if (!response.ok) {
            throw new Error('No se pudieron cargar los seguimientos');
        }

        return response.json();
    })
    .then(seguimientos => {

        // Normalizar nombres para comparar las localidades
        function normalizarNombre(nombre) {
            return (nombre || '')
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase()
                .trim();
        }

        // Recorrer cada localidad del mapa
        capaLocalidades.eachLayer(localidad => {

            const nombreLocalidad = normalizarNombre(
                localidad.feature.properties.LocNombre
            );

            // Buscar los seguimientos de esta localidad
            const seguimientosLocalidad = seguimientos.filter(
                seguimiento =>
                    normalizarNombre(seguimiento.n_localidad) === nombreLocalidad
            );

            // Crear un marcador por cada seguimiento
            seguimientosLocalidad.forEach(seguimiento => {

                const posicion = generarPosicionValida(
                    localidad.getBounds(),
                    localidad.feature.geometry
                );

                const estado = (seguimiento.estado_seguimiento || '')
                    .toLowerCase()
                    .trim()
                    .replace(/\s+/g, '_');

                const color = coloresEstados[estado] || '#777777';

                const marcador = L.circleMarker(posicion, {
                    radius: 6,
                    color: '#FFFFFF',
                    weight: 1.5,
                    fillColor: color,
                    fillOpacity: 0.95
                }).addTo(mapa);

                marcador.bindPopup(`
                    <div class="popup-seguimiento">
                        <h3>${seguimiento.titulo || 'Sin título'}</h3>
                        <p><strong>Animal:</strong> ${seguimiento.animal_nombre || 'No especificado'}</p>
                        <p><strong>Estado:</strong> ${seguimiento.estado_seguimiento || 'No especificado'}</p>
                        <p><strong>Localidad:</strong> ${seguimiento.n_localidad}</p>
                    </div>
                `);

                // Actualizar el panel al seleccionar un marcador
marcador.on('click', function () {
    mostrarInformacionSeguimiento(seguimiento);
});

            });

        });

    })
    .catch(error => {
        console.error('Error al cargar los seguimientos:', error);
    });

    })
    .catch(error => {
        console.error('Error al cargar las localidades:', error);
    });