function initPublicMap() {
    const mapContainer = document.getElementById('world-map');
    if (!mapContainer || mapContainer.innerHTML !== "") return; // Evita doppie inizializzazioni

// 1. RECUPERA I DATI
    const dataElement = document.getElementById('map-data');
    if (!dataElement) return;
    const rawData = dataElement.textContent;
        if (!rawData || rawData.trim() === "") return; 

    const languages = JSON.parse(rawData);

    // 2. FUNZIONE COLORE (identica alla tua)
    function getColorForFamily(family) {
        let hash = 0;
        for (let i = 0; i < family.length; i++) {
            hash = family.charCodeAt(i) + ((hash << 5) - hash);
        }
        let color = '#';
        for (let i = 0; i < 3; i++) {
            let value = (hash >> (i * 8)) & 0xFF;
            value = Math.min(255, value + 50); 
            color += ('00' + value.toString(16)).substr(-2);
        }
        return color;
    }

    // 3. CREA I PUNTI (FEATURES)
    const features = languages.map(lang => {
        const feature = new ol.Feature({
            geometry: new ol.geom.Point(ol.proj.fromLonLat([lang.lng, lang.lat])),
            name: lang.name,
            id: lang.id,
            family: lang.family
        });

        // Stile personalizzato per ogni punto
        feature.setStyle(new ol.style.Style({
            image: new ol.style.Circle({
                radius: 6,
                fill: new ol.style.Fill({ color: getColorForFamily(lang.family) }),
                stroke: new ol.style.Stroke({ color: '#ffffff', width: 1.5 })
            })
        }));
        return feature;
    });

    // 4. INIZIALIZZA LA MAPPA
    const vectorSource = new ol.source.Vector({ features: features });
    const vectorLayer = new ol.layer.Vector({ source: vectorSource });

    const map = new ol.Map({
        target: 'world-map',
        layers: [
            new ol.layer.Tile({
                source: new ol.source.XYZ({
                    url: 'https://{a-d}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
                    attributions: '&copy; OpenStreetMap contributors &copy; CARTO'
                })
            }),
            vectorLayer
        ],
        view: new ol.View({
            center: ol.proj.fromLonLat([0, 20]),
            zoom: 2
        }),
        interactions: ol.interaction.defaults.defaults({
            mouseWheelZoom: false // Disabilita zoom con rotella come nel tuo originale
        })
    });

    // 5. GESTIONE POPUP (Overlay)
    const container = document.createElement('div');
    container.className = 'ol-popup'; // Dovrai aggiungere un po' di CSS per renderlo carino
    const content = document.createElement('div');
    container.appendChild(content);
    
    const overlay = new ol.Overlay({
        element: container,
        autoPan: true,
        autoPanAnimation: { duration: 250 }
    });
    map.addOverlay(overlay);

    map.on('singleclick', function (evt) {
        const feature = map.forEachFeatureAtPixel(evt.pixel, f => f);
        if (feature) {
            const coordinates = feature.getGeometry().getCoordinates();
            content.innerHTML = `
                <div style="font-family: sans-serif; min-width: 150px; background:white; padding:10px; border-radius:5px; border:1px solid #ccc;">
                    <strong style="color: #d14124; font-size: 1.1rem;">${feature.get('name')}</strong> 
                    <span style="color: #666; font-size: 0.85rem;">(${feature.get('id')})</span><br>
                    <span style="font-size: 0.9rem; color: #444; display: block; margin-top: 5px;">
                        Family: <b>${feature.get('family')}</b>
                    </span>
                </div>`;
            overlay.setPosition(coordinates);
        } else {
            overlay.setPosition(undefined);
        }
    });
}

document.addEventListener("DOMContentLoaded", initPublicMap);
document.body.addEventListener("htmx:afterSwap", initPublicMap);