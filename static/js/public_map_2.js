function initPublicMap() {
    const mapContainer = document.getElementById('world-map');
    if (!mapContainer || mapContainer.innerHTML !== "") return; 

    // 1. RECUPERA I DATI
    const dataElement = document.getElementById('map-data');
    if (!dataElement) return;
    const rawData = dataElement.textContent;
    if (!rawData || rawData.trim() === "") return;
    const languages = JSON.parse(rawData);

    // 2. FUNZIONE COLORE 
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

    // 3. CREA I PUNTI
    const features = languages.map(lang => {
        const feature = new ol.Feature({
            geometry: new ol.geom.Point(ol.proj.fromLonLat([lang.lng, lang.lat])),
            name: lang.name,
            id: lang.id,
            family: lang.top_level_family 
        });

        // Colora in base alla TOP LEVEL FAMILY
        feature.setStyle(new ol.style.Style({
            image: new ol.style.Circle({
                radius: 6,
                fill: new ol.style.Fill({ color: getColorForFamily(lang.top_level_family) }),
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
                    attributions: '&copy; OpenStreetMap contributors &copy; CARTO',
                    crossOrigin: 'anonymous'
                })
            }),
            vectorLayer
        ],
        view: new ol.View({
            center: ol.proj.fromLonLat([0, 20]),
            zoom: 2
        }),
        interactions: ol.interaction.defaults.defaults({
            mouseWheelZoom: false 
        })
    });

    // 5. GESTIONE POPUP
    const container = document.createElement('div');
    container.className = 'ol-popup'; 
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
                <div style="font-family: sans-serif; min-width: 150px; background:white; padding:10px; border-radius:5px; border:1px solid #ccc; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                    <strong style="color: #d14124; font-size: 1.1rem;">${feature.get('name')}</strong> 
                    <span style="color: #666; font-size: 0.85rem;">(${feature.get('id')})</span><br>
                    <span style="font-size: 0.9rem; color: #444; display: block; margin-top: 5px;">
                        Top Family: <b>${feature.get('family')}</b>
                    </span>
                </div>`;
            overlay.setPosition(coordinates);
        } else {
            overlay.setPosition(undefined);
        }
    });

// 6. LOGICA DI ESPORTAZIONE IN PNG
    const exportBtn = document.getElementById('export-map-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            map.once('rendercomplete', function () {
                const mapCanvas = document.createElement('canvas');
                const size = map.getSize();
                mapCanvas.width = size[0];
                mapCanvas.height = size[1];
                const mapContext = mapCanvas.getContext('2d');
                
                Array.prototype.forEach.call(
                    document.querySelectorAll('.ol-layer canvas'),
                    function (canvas) {
                        if (canvas.width > 0) {
                            const opacity = canvas.parentNode.style.opacity;
                            mapContext.globalAlpha = opacity === '' ? 1 : Number(opacity);
                            const transform = canvas.style.transform;
                            
                            let matrix;
                            if (transform) {
                                // Se c'è una trasformazione CSS (es. panning attivo)
                                matrix = transform
                                    .match(/^matrix\(([^\(]*)\)$/)[1]
                                    .split(',')
                                    .map(Number);
                            } else {
                                // Fallback sicuro se transform è vuoto (evita il crash del .match)
                                matrix = [
                                    parseFloat(canvas.style.width) / canvas.width || 1,
                                    0,
                                    0,
                                    parseFloat(canvas.style.height) / canvas.height || 1,
                                    0,
                                    0
                                ];
                            }
                            
                            CanvasRenderingContext2D.prototype.setTransform.apply(mapContext, matrix);
                            mapContext.drawImage(canvas, 0, 0);
                        }
                    }
                );
                
                try {
                    // Scarica l'immagine
                    const link = document.getElementById('image-download');
                    link.href = mapCanvas.toDataURL('image/png');
                    link.click();
                } catch (err) {
                    console.error("Errore durante l'esportazione della mappa (CORS o Tainted Canvas):", err);
                    alert("Impossibile esportare la mappa per restrizioni di sicurezza del browser (CORS). Controlla la console.");
                }
            });
            map.renderSync(); 
        });
    }
}

document.addEventListener("DOMContentLoaded", initPublicMap);
document.body.addEventListener("htmx:afterSwap", initPublicMap);