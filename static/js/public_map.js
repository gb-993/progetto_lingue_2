function initPublicMap() {
    const mapContainer = document.getElementById('world-map');
    
    // Se non c'è il div della mappa in questa pagina, ci fermiamo
    if (!mapContainer) return;

    // Sicurezza: se la mappa è già stata inizializzata (es. ricaricamenti HTMX), non duplicarla
    if (mapContainer._leaflet_id) return;

    // 1. INIZIALIZZA LA MAPPA A PRESCINDERE DAI DATI
    const map = L.map('world-map', {
        scrollWheelZoom: false // Evita zoom accidentali scrollando la pagina
    }).setView([20, 0], 2);

    // 2. AGGIUNGE IL PLANISFERO (Base di CARTO)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // 3. RECUPERA I DATI DEI SEGNAPOSTO
    const dataElement = document.getElementById('map-data');
    if (!dataElement) return;

    const rawData = dataElement.textContent;
    
    // Se non ci sono dati, la mappa rimane vuota ma visibile
    if (!rawData || rawData.trim() === "[]" || rawData.trim() === "") return;

    const languages = JSON.parse(rawData);

    // 4. GENERATORE DI COLORI
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

    // 5. CREAZIONE DEI MARKER
    languages.forEach(lang => {
        const familyColor = getColorForFamily(lang.family);
        
        const customIcon = L.divIcon({
            className: '',
            html: `<div class="custom-marker" style="background-color: ${familyColor};"></div>`,
            iconSize: [12, 12],
            iconAnchor: [6, 6] 
        });

        const marker = L.marker([lang.lat, lang.lng], { icon: customIcon }).addTo(map);
        
        marker.bindPopup(`
            <div style="font-family: sans-serif; min-width: 150px;">
                <strong style="color: #d14124; font-size: 1.1rem;">${lang.name}</strong> 
                <span style="color: #666; font-size: 0.85rem;">(${lang.id})</span><br>
                <span style="font-size: 0.9rem; color: #444; display: block; margin-top: 5px;">
                    Family: <b>${lang.family}</b>
                </span>
            </div>
        `);
    });
}

// Lancia la mappa al caricamento normale della pagina
document.addEventListener("DOMContentLoaded", initPublicMap);

// Lancia la mappa se la pagina viene caricata dinamicamente da HTMX
document.body.addEventListener("htmx:afterSwap", function() {
    initPublicMap();
});