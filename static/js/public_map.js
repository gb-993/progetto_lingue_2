document.addEventListener("DOMContentLoaded", function() {
    // 1. Recupera il JSON dal tag nascosto nell'HTML
    const dataElement = document.getElementById('map-data');
    if (!dataElement) return; // Se non c'è la mappa, ferma lo script

    const rawData = dataElement.textContent;
    if (!rawData || rawData.trim() === "[]") return;

    const languages = JSON.parse(rawData);

    // 2. Inizializza la mappa centrata tra Europa e Africa
    const map = L.map('world-map', {
        scrollWheelZoom: false // Evita zoom accidentali scrollando la pagina
    }).setView([20, 0], 2);

    // 3. Aggiunge i "tiles" (il disegno del planisfero chiaro di CARTO)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // 4. Generatore di colori automatico basato sul nome della famiglia
    function getColorForFamily(family) {
        let hash = 0;
        for (let i = 0; i < family.length; i++) {
            hash = family.charCodeAt(i) + ((hash << 5) - hash);
        }
        let color = '#';
        for (let i = 0; i < 3; i++) {
            let value = (hash >> (i * 8)) & 0xFF;
            value = Math.min(255, value + 50); // Schiarisce un po' per contrastare i pin neri/scuri
            color += ('00' + value.toString(16)).substr(-2);
        }
        return color;
    }

    // 5. Creazione dei marker
    languages.forEach(lang => {
        const familyColor = getColorForFamily(lang.family);
        
        // Icona HTML circolare personalizzata
        const customIcon = L.divIcon({
            className: '',
            html: `<div class="custom-marker" style="background-color: ${familyColor};"></div>`,
            iconSize: [12, 12],
            iconAnchor: [6, 6] 
        });

        // Aggiunge marker e popup
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
});